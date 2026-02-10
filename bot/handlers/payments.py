import asyncio
import json
import uuid
from datetime import datetime

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from bot.config import TICKETS_CHAT_ID, PAYMENTS_ENABLED
from bot.data.products import get_product
from bot.keyboards.callbacks import PayCb
from bot.keyboards.payments import pay_invoice_kb, purchase_done_kb
from bot.payments.methods import PAYMENT_METHODS
from bot.payments.rates_cache import convert, quantize_amount
from bot.promos import promo_service
from bot.promos.state import USER_PROMO
from bot.services.crypto_pay import crypto_pay
from bot.users import user_service
from bot.utils.notify import notify_managers
from bot.utils.tickets import send_ticket_to_group

from bot.payments.platega_orders import PlategaOrders, PendingPlategaOrder

# === PG payments (PostgreSQL primary; JSON остается как временный fallback) ===
import asyncpg
from bot.payments.pg_storage import PgPaymentsStorage, PaymentCreate


_PG_POOL: asyncpg.Pool | None = None


def set_pg_pool(pool: asyncpg.Pool) -> None:
    """Прокидываем asyncpg pool из main.py (в PROD)."""
    global _PG_POOL
    _PG_POOL = pool


def _pg_payments() -> PgPaymentsStorage | None:
    return PgPaymentsStorage(_PG_POOL) if _PG_POOL else None


router = Router()
platega_orders = PlategaOrders()

# простая память для активных рублёвых платежей (ускоритель; НЕ источник истины)
_PENDING_PLATEGA: dict[str, dict] = {}


def _compute_price_with_promo(user_id: int, product) -> tuple[int, str | None]:
    price_rub = product.price_rub
    promo_code = None

    state = USER_PROMO.get(user_id)
    if state and state.product_id == product.id and state.final_price_rub is not None:
        price_rub = state.final_price_rub
        promo_code = state.promo_code

    return price_rub, promo_code


async def _finalize_purchase(
    bot,
    ticket_id: str | None = None,
    buyer_id: int = 0,
    buyer_username: str | None = None,
    product_id: str = "",
    amount_asset: str = "",
    asset: str = "",
    final_price_rub: int | None = None,
    promo_code: str | None = None,
):
    product = get_product(product_id)

    if not ticket_id:
        ticket_id = uuid.uuid4().hex[:8].upper()

    # ✅ (пункт 2) если username не пришёл (например, из вебхука) — пробуем достать у Telegram
    if not buyer_username and buyer_id:
        try:
            chat = await bot.get_chat(buyer_id)
            buyer_username = getattr(chat, "username", None)
        except Exception:
            pass

    await bot.send_message(
        buyer_id,
        "✅ *Оплата прошла успешно!*\n\n"
        f"📦 *Товар:* {product.title if product else 'Неизвестно'}\n"
        f"🧾 *Тикет:* #{ticket_id}\n\n"
        "👨‍💻 Наш менеджер свяжется с вами для подключения подписки.\n\n"
        "Если долго не отвечают — напишите в поддержку.",
        parse_mode="Markdown",
        reply_markup=purchase_done_kb(),
    )

    paid_time = datetime.now().strftime("%d.%m.%Y %H:%M")

    manager_text = (
        "🆕 НОВАЯ ОПЛАТА\n"
        f"🕒 Время: {paid_time}\n\n"
        f"🧾 Тикет: #{ticket_id}\n"
        f"📦 Товар: {product.title if product else 'Неизвестно'}\n"
        f"💰 Сумма: {amount_asset} {asset} "
        f"(≈ {final_price_rub if final_price_rub else (product.price_rub if product else '—')} ₽)\n"
    )

    if promo_code:
        manager_text += f"Промокод: {promo_code}\n"

    manager_text += (
        f"\n👤 Покупатель: @{buyer_username or '—'}\n"
        f"🆔 User ID: {buyer_id}"
    )

    await notify_managers(bot, manager_text)

    await send_ticket_to_group(
        bot=bot,
        chat_id=TICKETS_CHAT_ID,
        ticket_id=ticket_id,
        product_title=product.title if product else "Неизвестно",
        amount=str(amount_asset),
        asset=str(asset),
        buyer_id=buyer_id,
        buyer_username=buyer_username,
        price_rub=final_price_rub if final_price_rub else (product.price_rub if product else None),
    )

    if promo_code:
        await promo_service.mark_used(promo_code, buyer_id)

    USER_PROMO.pop(buyer_id, None)

    amount_rub = final_price_rub or (product.price_rub if product else 0)
    # В PROD у нас есть pool → обновим users в PG; в test/фоллбэке уйдёт в JSON.
    await user_service.add_purchase(buyer_id, amount_rub, pool=_PG_POOL)


async def _poll_platega_status(tx_id: str, bot):
    """
    Проверяем /transaction/{id} пока не станет CONFIRMED / CANCELED / CHARGEBACK.
    Успешный — CONFIRMED, неуспешный — CANCELED, возврат — CHARGEBACK.
    """
    meta = _PENDING_PLATEGA.get(tx_id)
    if not meta:
        meta = platega_orders.get(tx_id)
        if not meta:
            return

    ticket_id = meta["ticket_id"]
    buyer_id = meta["buyer_id"]
    buyer_username = meta.get("buyer_username")
    product_id = meta["product_id"]
    promo_code = meta.get("promo_code")
    final_price_rub = meta.get("final_price_rub")
    message_chat_id = meta.get("message_chat_id")
    message_id = meta.get("message_id")

    # 30 минут, проверка раз в 5 секунд
    for _ in range(30 * 60 // 5):
        try:
            from bot.services.platega_pay import platega_pay  # lazy import
            st = await platega_pay.get_transaction(tx_id)
        except Exception:
            await asyncio.sleep(5)
            continue

        status = (st.get("status") or "").upper()

        if status == "CONFIRMED":
            if message_chat_id and message_id:
                try:
                    await bot.delete_message(message_chat_id, message_id)
                except TelegramBadRequest:
                    pass

            # ✅ (пункт 1) идемпотентность: финализируем только если мы первые отметили paid
            pg = _pg_payments()
            if pg:
                try:
                    first = await pg.mark_paid(uuid.UUID(str(tx_id)))
                except Exception:
                    # если не смогли залочить — лучше не дублировать
                    return

                if not first:
                    # уже финализировали (например, через вебхук)
                    _PENDING_PLATEGA.pop(tx_id, None)
                    platega_orders.pop(tx_id)
                    return

            await _finalize_purchase(
                bot=bot,
                ticket_id=ticket_id,
                buyer_id=buyer_id,
                buyer_username=buyer_username,
                product_id=product_id,
                amount_asset=str(final_price_rub or 0),
                asset="RUB",
                final_price_rub=final_price_rub,
                promo_code=promo_code,
            )

            _PENDING_PLATEGA.pop(tx_id, None)
            platega_orders.pop(tx_id)
            return

        if status in ("CANCELED", "CHARGEBACK"):
            pg = _pg_payments()
            if pg:
                try:
                    await pg.mark_expired(uuid.UUID(str(tx_id)))
                except Exception:
                    pass

            try:
                await bot.send_message(
                    buyer_id,
                    "Платёж не завершён (отменён/возврат). Попробуйте ещё раз."
                )
            except Exception:
                pass

            _PENDING_PLATEGA.pop(tx_id, None)
            platega_orders.pop(tx_id)
            return

        await asyncio.sleep(5)

    _PENDING_PLATEGA.pop(tx_id, None)
    try:
        await bot.send_message(
            buyer_id,
            "⌛️ Ссылка на оплату устарела.\n\n"
            "Если вы *уже оплатили* — ничего делать не нужно, мы проверим оплату автоматически.\n"
            "Если не оплачивали — откройте товар и создайте новый платёж.\n\n"
            "По всем вопросам смело обращайтесь в поддержку!",
            parse_mode="Markdown",
        )
    except Exception:
        pass


@router.callback_query(PayCb.filter())
async def pay_handler(cq: CallbackQuery, callback_data: PayCb):
    # === Вариант A: в test-режиме платежи отключены ===
    if not PAYMENTS_ENABLED:
        await cq.answer("💤 Оплаты отключены в тестовом режиме.", show_alert=True)
        return

    method = PAYMENT_METHODS.get(callback_data.method)

    if not method:
        await cq.answer("Неизвестный способ оплаты", show_alert=True)
        return

    if not method.enabled:
        await cq.answer(method.disabled_text, show_alert=True)
        return

    product = get_product(callback_data.product_id)
    if not product:
        await cq.message.answer("Товар не найден", show_alert=True)
        return

    method = PAYMENT_METHODS.get(callback_data.method)
    if not method:
        await cq.message.answer("Неизвестный способ оплаты", show_alert=True)
        return

    if not method.enabled:
        await cq.answer(method.disabled_text or "Способ оплаты недоступен", show_alert=True)
        return

    price_rub, promo_code = _compute_price_with_promo(cq.from_user.id, product)

    # === RUB (Platega) ===
    if method.code == "rub":
        ticket_id = uuid.uuid4().hex[:8].upper()

        payload = json.dumps({
            "ticket_id": ticket_id,
            "product_id": product.id,
            "buyer_id": cq.from_user.id,
            "buyer_username": cq.from_user.username,
            "promo_code": promo_code,
            "final_price_rub": price_rub,
        })

        return_url = "https://t.me/berloga_programmistov"
        failed_url = "https://t.me/berloga_programmistov"

        from bot.services.platega_pay import platega_pay  # lazy import
        resp = await platega_pay.create_sbp_payment(
            amount_rub=price_rub,
            description=f"{product.title} | Ticket #{ticket_id}",
            payload=payload,
            return_url=return_url,
            failed_url=failed_url,
            payment_method=2,
        )

        tx_id = resp.get("transactionId")
        pay_url = resp.get("redirect")

        if not tx_id or not pay_url:
            await cq.answer("Не удалось создать платёж. Попробуйте ещё раз.", show_alert=True)
            return

        platega_orders.put(
            tx_id,
            PendingPlategaOrder(
                ticket_id=ticket_id,
                buyer_id=cq.from_user.id,
                buyer_username=cq.from_user.username,
                product_id=product.id,
                promo_code=promo_code,
                final_price_rub=price_rub,
                created_at=datetime.utcnow().isoformat(),
            )
        )

        _PENDING_PLATEGA[tx_id] = {
            "ticket_id": ticket_id,
            "buyer_id": cq.from_user.id,
            "buyer_username": cq.from_user.username,
            "product_id": product.id,
            "promo_code": promo_code,
            "final_price_rub": price_rub,
            "message_chat_id": cq.message.chat.id if cq.message else None,
            "message_id": cq.message.message_id if cq.message else None,
        }

        # создаём запись в PostgreSQL (pending)
        pg = _pg_payments()
        if pg:
            try:
                await pg.create_payment(
                    PaymentCreate(
                        order_id=uuid.UUID(str(tx_id)),
                        ticket_id=ticket_id,
                        user_id=cq.from_user.id,
                        product_id=product.id,
                        promo_code=promo_code,
                        final_price_rub=price_rub,
                        payment_method="sbp",
                    )
                )
            except Exception:
                pass

        asyncio.create_task(_poll_platega_status(tx_id, cq.bot))

        caption = (
            f"💳 *Оплата через {method.title}*\n\n"
            f"📦 Товар: *{product.title}*\n"
        )
        if promo_code:
            caption += (
                f"🏷 Промокод: *{promo_code}*\n"
                f"💰 Сумма: *{price_rub} ₽* *(со скидкой)*\n\n"
            )
        else:
            caption += f"💰 Сумма: *{price_rub} ₽*\n\n"

        caption += (
            "_Ссылка действительна ~15 минут_\n\n"
            "Нажимая «Оплатить», вы соглашаетесь с [условиями сервиса](https://telegra.ph/Dokumenty-servisa-IT-Berloga-Store-01-20).\n"
        )

        await cq.message.edit_caption(
            caption=caption,
            reply_markup=pay_invoice_kb(pay_url, product.id),
            parse_mode="Markdown",
        )
        return

    # === CRYPTO (CryptoBot) ===
    asset = method.asset

    try:
        amount_crypto = await convert(float(price_rub), "RUB", asset)
        amount_crypto = quantize_amount(amount_crypto, asset)
    except Exception:
        await cq.answer("Не удалось получить курс. Попробуйте ещё раз.", show_alert=True)
        return

    # Наш order_id для таблицы payments (UUID)
    order_id = uuid.uuid4()

    payload = json.dumps({
        "order_id": str(order_id),
        "product_id": product.id,
        "buyer_id": cq.from_user.id,
        "buyer_username": cq.from_user.username,
        "promo_code": promo_code,
        "final_price_rub": price_rub,
    })

    invoice = await crypto_pay.create_invoice(
        amount=float(amount_crypto),
        asset=asset,
        description=product.title,
        payload=payload,
        expires_in=1800,
    )

    # создаём запись в PostgreSQL (pending)
    pg = _pg_payments()
    if pg:
        try:
            await pg.create_payment(
                PaymentCreate(
                    order_id=order_id,
                    ticket_id=str(getattr(invoice, "invoice_id", "")),
                    user_id=cq.from_user.id,
                    product_id=product.id,
                    promo_code=promo_code,
                    final_price_rub=price_rub,
                    payment_method="crypto",
                )
            )
        except Exception:
            pass

    invoice.poll(message=cq.message)

    caption = (
        f"💳 *Оплата через {method.title}*\n\n"
        f"📦 Товар: *{product.title}*\n"
    )

    if promo_code:
        caption += (
            f"🏷 Промокод: *{promo_code}*\n"
            f"💰 Сумма: *{amount_crypto} {asset}* *(≈ {price_rub} ₽ со скидкой)*\n\n"
        )
    else:
        caption += (
            f"💰 Сумма: *{amount_crypto} {asset}* *(≈ {product.price_rub} ₽)*\n\n"
        )

    caption += (
        "_Курс обновляется каждые 30 сек_\n"
        "_Ссылка действительна в течение 30 минут_\n\n"
        "Нажимая «Оплатить», вы соглашаетесь с [условиями сервиса](https://telegra.ph/Dokumenty-servisa-IT-Berloga-Store-01-20).\n"
    )

    await cq.message.edit_caption(
        caption=caption,
        reply_markup=pay_invoice_kb(invoice.bot_invoice_url, product.id),
        parse_mode="Markdown",
    )


@crypto_pay.invoice_paid()
async def on_invoice_paid(invoice, message):
    data = json.loads(invoice.payload)

    buyer_id = data["buyer_id"]
    buyer_username = data.get("buyer_username")
    product_id = data["product_id"]
    promo_code = data.get("promo_code")
    final_price_rub = data.get("final_price_rub")
    order_id = data.get("order_id")

    # ✅ (пункт 1) для крипты тоже: не дублить финализацию
    pg = _pg_payments()
    if pg and order_id:
        try:
            first = await pg.mark_paid(uuid.UUID(str(order_id)))
            if not first:
                return
        except Exception:
            return

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    await _finalize_purchase(
        bot=message.bot,
        buyer_id=buyer_id,
        buyer_username=buyer_username,
        product_id=product_id,
        amount_asset=str(invoice.amount),
        asset=str(invoice.asset),
        final_price_rub=final_price_rub,
        promo_code=promo_code,
    )
