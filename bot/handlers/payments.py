from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.keyboards.callbacks import PayCb
from bot.services.crypto_pay import crypto_pay
from bot.data.products import get_product

from bot.utils.notify import notify_managers
from datetime import datetime

import uuid
import json

from bot.payments.methods import PAYMENT_METHODS
from bot.keyboards.payments import pay_invoice_kb, purchase_done_kb

from bot.utils.tickets import send_ticket_to_group
from bot.config import TICKETS_CHAT_ID

from bot.payments.rates_cache import convert, quantize_amount

from bot.promos.state import USER_PROMO
from bot.promos import promo_service

from bot.users import user_service

router = Router()


@router.callback_query(PayCb.filter())
async def pay_crypto(cq: CallbackQuery, callback_data: PayCb):
    await cq.answer()

    product = get_product(callback_data.product_id)
    if not product:
        await cq.message.answer("❌ Товар не найден", show_alert=True)
        return

    # 1. Метод оплаты
    method = PAYMENT_METHODS.get(callback_data.method)
    if not method:
        await cq.message.answer("❌ Неизвестный способ оплаты", show_alert=True)
        return

    if not method.enabled:
        await cq.answer(
            method.disabled_text or "Этот способ оплаты пока недоступен",
            show_alert=True,
        )
        return

    asset = method.asset

    # 2. Цена с учётом промокода
    price_rub = product.price_rub
    promo_code = None

    state = USER_PROMO.get(cq.from_user.id)
    if state and state.product_id == product.id and state.final_price_rub is not None:
        price_rub = state.final_price_rub
        promo_code = state.promo_code

    # 3. Конвертация RUB -> crypto
    try:
        amount_crypto = await convert(float(price_rub), "RUB", asset)
        amount_crypto = quantize_amount(amount_crypto, asset)
    except Exception:
        await cq.answer("❌ Не удалось получить курс. Попробуйте ещё раз.", show_alert=True)
        return

    # 4. Payload invoice
    payload = json.dumps({
        "product_id": product.id,
        "buyer_id": cq.from_user.id,
        "buyer_username": cq.from_user.username,
        "promo_code": promo_code,
        "final_price_rub": price_rub,
    })

    # 5. Создание invoice
    invoice = await crypto_pay.create_invoice(
        amount=float(amount_crypto),
        asset=asset,
        description=product.title,
        payload=payload,
        expires_in=1800,
    )

    invoice.poll(message=cq.message)

    # 6. Обновляем сообщение
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
        reply_markup=pay_invoice_kb(
            invoice.bot_invoice_url,
            product.id
        ),
        parse_mode="Markdown",
    )


@crypto_pay.invoice_paid()
async def on_invoice_paid(invoice, message):
    """
    Срабатывает, когда CryptoBot подтверждает оплату
    """

    data = json.loads(invoice.payload)

    buyer_id = data["buyer_id"]
    buyer_username = data.get("buyer_username")
    product_id = data["product_id"]
    promo_code = data.get("promo_code")
    final_price_rub = data.get("final_price_rub")

    product = get_product(product_id)

    ticket_id = uuid.uuid4().hex[:8].upper()

    # сообщение покупателю
    await message.bot.send_message(
        buyer_id,
        "✅ *Оплата прошла успешно!*\n\n"
        f"📦 Товар: *{product.title if product else 'Неизвестно'}*\n"
        f"🧾 Тикет: *#{ticket_id}*\n\n"
        "👨‍💼 Наш менеджер свяжется с вами для подключения подписки.\n"
        "Если долго не отвечают — напишите в поддержку.",
        parse_mode="Markdown",
        reply_markup=purchase_done_kb(),
    )

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    # сообщение менеджерам
    paid_time = datetime.now().strftime("%d.%m.%Y %H:%M")

    manager_text = (
        "🆕 *НОВАЯ ОПЛАТА*\n"
        f"🕒 Время: *{paid_time}*\n\n"
        f"🧾 Тикет: *#{ticket_id}*\n"
        f"📦 Товар: *{product.title if product else 'Неизвестно'}*\n"
        f"💰 Сумма: *{invoice.amount} {invoice.asset}* "
        f"(≈ {final_price_rub if final_price_rub else product.price_rub if product else '—'} ₽)\n"
    )

    if promo_code:
        manager_text += f"🏷 Промокод: *{promo_code}*\n"

    manager_text += (
        f"\n👤 Покупатель: @{buyer_username or '—'}\n"
        f"🆔 User ID: [{buyer_id}](tg://user?id={buyer_id})"
    )

    await notify_managers(message.bot, manager_text)
    
    # тикет в группу
    await send_ticket_to_group(
        bot=message.bot,
        chat_id=TICKETS_CHAT_ID,
        ticket_id=ticket_id,
        product_title=product.title if product else "Неизвестно",
        amount=str(invoice.amount),
        asset=str(invoice.asset),
        buyer_id=buyer_id,
        buyer_username=buyer_username,
        price_rub=final_price_rub if final_price_rub else product.price_rub if product else None,
    )

    # фиксируем использование промокода
    if promo_code:
        await promo_service.mark_used(promo_code, buyer_id)

    # очищаем promo-state
    USER_PROMO.pop(buyer_id, None)

    # фиксируем покупку пользователя
    amount_rub = final_price_rub or (product.price_rub if product else 0)
    await user_service.add_purchase(buyer_id, amount_rub)
