import asyncio
import json
import uuid
from datetime import datetime

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from bot.config import TICKETS_CHAT_ID
from bot.data.products import get_product
from bot.keyboards.callbacks import PayCb
from bot.keyboards.payments import pay_invoice_kb, purchase_done_kb
from bot.payments.methods import PAYMENT_METHODS
from bot.payments.rates_cache import convert, quantize_amount
from bot.promos import promo_service
from bot.promos.state import USER_PROMO
from bot.services.crypto_pay import crypto_pay
from bot.services.platega_pay import platega_pay
from bot.users import user_service
from bot.utils.notify import notify_managers
from bot.utils.tickets import send_ticket_to_group

router = Router()

# простая память для активных рублёвых платежей (на первое время)
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
    buyer_id: int,
    buyer_username: str | None,
    product_id: str,
    amount_asset: str,
    asset: str,
    final_price_rub: int | None,
    promo_code: str | None,
):
    product = get_product(product_id)
    ticket_id = uuid.uuid4().hex[:8].upper()

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
    f"🆔 User ID: [{buyer_id}](tg://user?id={buyer_id})"
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
    await user_service.add_purchase(buyer_id, amount_rub)


async def _poll_platega_status(tx_id: str, bot):
    """
    Проверяем /transaction/{id} пока не станет CONFIRMED / CANCELED / CHARGEBACK.
    По докам успешный — CONFIRMED, неуспешный — CANCELED, возврат — CHARGEBACK. :contentReference[oaicite:5]{index=5}
    """
    meta = _PENDING_PLATEGA.get(tx_id)
    if not meta:
        return

    buyer_id = meta["buyer_id"]
    buyer_username = meta.get("buyer_username")
    product_id = meta["product_id"]
    promo_code = meta.get("promo_code")
    final_price_rub = meta.get("final_price_rub")
    message_chat_id = meta.get("message_chat_id")
    message_id = meta.get("message_id")

    # 15 минут (как expiresIn в примере), проверка раз в 5 секунд
    for _ in range(15 * 60 // 5):
        try:
            st = await platega_pay.get_transaction(tx_id)
        except Exception:
            await asyncio.sleep(5)
            continue

        status = (st.get("status") or "").upper()

        if status == "CONFIRMED":
            # можно удалить сообщение с кнопкой оплаты (если есть)
            if message_chat_id and message_id:
                try:
                    await bot.delete_message(message_chat_id, message_id)
                except TelegramBadRequest:
                    pass

            await _finalize_purchase(
                bot=bot,
                buyer_id=buyer_id,
                buyer_username=buyer_username,
                product_id=product_id,
                amount_asset=str(final_price_rub or 0),
                asset="RUB",
                final_price_rub=final_price_rub,
                promo_code=promo_code,
            )
            _PENDING_PLATEGA.pop(tx_id, None)
            return

        if status in ("CANCELED", "CHARGEBACK"):
            # можно уведомить пользователя
            try:
                await bot.send_message(buyer_id, "Платёж не завершён (отменён/возврат). Попробуйте ещё раз.")
            except Exception:
                pass
            _PENDING_PLATEGA.pop(tx_id, None)
            return

        await asyncio.sleep(5)

    # таймаут
    _PENDING_PLATEGA.pop(tx_id, None)
    try:
        await bot.send_message(buyer_id, "Время оплаты истекло. Откройте товар и создайте новый платёж.")
    except Exception:
        pass


@router.callback_query(PayCb.filter())
async def pay_handler(cq: CallbackQuery, callback_data: PayCb):
    # await cq.answer() пока карта еу не работает так сделаем, потом вернем
    method = PAYMENT_METHODS.get(callback_data.method)

    if not method:
        await cq.answer("Неизвестный способ оплаты", show_alert=True)
        return

    if not method.enabled:
        await cq.answer(method.disabled_text, show_alert=True)
        return
    # пока еу карта не работает, так оставим блок кода



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
        payload = json.dumps({
            "product_id": product.id,
            "buyer_id": cq.from_user.id,
            "buyer_username": cq.from_user.username,
            "promo_code": promo_code,
            "final_price_rub": price_rub,
        })

        # можно поставить любые public URL
        return_url = "https://t.me/berloga_programmistov"
        failed_url = "https://t.me/berloga_programmistov"

        resp = await platega_pay.create_sbp_payment(
            amount_rub=price_rub,
            description=product.title,
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

        # сохраним в память и запустим polling
        _PENDING_PLATEGA[tx_id] = {
            "buyer_id": cq.from_user.id,
            "buyer_username": cq.from_user.username,
            "product_id": product.id,
            "promo_code": promo_code,
            "final_price_rub": price_rub,
            "message_chat_id": cq.message.chat.id if cq.message else None,
            "message_id": cq.message.message_id if cq.message else None,
        }
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
            caption += (
                f"💰 Сумма: *{price_rub} ₽*\n\n"
            )

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

    # === CRYPTO (как было) ===
    asset = method.asset

    try:
        amount_crypto = await convert(float(price_rub), "RUB", asset)
        amount_crypto = quantize_amount(amount_crypto, asset)
    except Exception:
        await cq.answer("Не удалось получить курс. Попробуйте ещё раз.", show_alert=True)
        return

    payload = json.dumps({
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
