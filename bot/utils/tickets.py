from datetime import datetime
import html

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def ticket_actions_kb(buyer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть профиль (ID)", url=f"tg://user?id={buyer_id}")]
        ]
    )


def build_ticket_message(
    *,
    ticket_id: str,
    product_title: str,
    amount: str,
    asset: str,
    buyer_id: int,
    buyer_username: str | None,
    price_rub: int | None = None,
) -> str:
    paid_time = datetime.now().strftime("%d.%m.%Y %H:%M")

    safe_ticket = html.escape(str(ticket_id))
    safe_title = html.escape(product_title or "—")
    safe_amount = html.escape(str(amount))
    safe_asset = html.escape(str(asset))

    rub_line = f"\n💵 В рублях: <b>{html.escape(str(price_rub))} ₽</b>" if price_rub is not None else ""

    if buyer_username:
        safe_un = html.escape(buyer_username.strip().lstrip("@"))
        buyer_line = f"👤 Покупатель: @{safe_un}\n"
    else:
        buyer_line = "👤 Покупатель: @—\n"

    return (
        "🆕 <b>НОВАЯ ОПЛАТА</b>\n"
        f"🕒 Время: <b>{html.escape(paid_time)}</b>\n\n"
        f"🧾 Тикет: <b>#{safe_ticket}</b>\n"
        f"📦 Товар: <b>{safe_title}</b>\n"
        f"💰 Сумма: <b>{safe_amount} {safe_asset}</b>{rub_line}\n\n"
        f"{buyer_line}"
        f"🆔 User ID: <code>{buyer_id}</code>"
    )


def build_ticket_status_message(ticket_id: str) -> str:
    safe_ticket = html.escape(str(ticket_id))
    return f"🧾 <b>#{safe_ticket}</b>\nСтатус: ⏳ <b>В процессе</b>"


async def send_ticket_to_group(
    *,
    bot: Bot,
    chat_id: int,
    ticket_id: str,
    product_title: str,
    amount: str,
    asset: str,
    buyer_id: int,
    buyer_username: str | None,
    price_rub: int | None = None,
):
    # 1️⃣ Карточка тикета + кнопка по ID
    await bot.send_message(
        chat_id=chat_id,
        text=build_ticket_message(
            ticket_id=ticket_id,
            product_title=product_title,
            amount=amount,
            asset=asset,
            buyer_id=buyer_id,
            buyer_username=buyer_username,
            price_rub=price_rub,
        ),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=ticket_actions_kb(buyer_id),
    )

    # 2️⃣ Статус тикета
    await bot.send_message(
        chat_id=chat_id,
        text=build_ticket_status_message(ticket_id),
        parse_mode="HTML",
    )
