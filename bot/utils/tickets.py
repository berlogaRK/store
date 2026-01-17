from datetime import datetime
from aiogram import Bot


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

    rub_line = f"\n💵 В рублях: *{price_rub} ₽*" if price_rub is not None else ""

    return (
        "🆕 *НОВАЯ ОПЛАТА*\n"
        f"🕒 Время: *{paid_time}*\n\n"
        f"🧾 Тикет: *#{ticket_id}*\n"
        f"📦 Товар: *{product_title}*\n"
        f"💰 Сумма: *{amount} {asset}*{rub_line}\n\n"
        f"👤 Покупатель: @{buyer_username or '—'}\n"
        f"🆔 User ID: [{buyer_id}](tg://user?id={buyer_id})"
    )


def build_ticket_status_message(ticket_id: str) -> str:
    return (
        f"🧾 *#{ticket_id}*\n"
        "Статус: ⏳ *В процессе*"
    )


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
    # 1️⃣ Карточка тикета
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
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )

    # 2️⃣ Статус тикета (менеджеры РЕДАКТИРУЮТ вручную)
    await bot.send_message(
        chat_id=chat_id,
        text=build_ticket_status_message(ticket_id),
        parse_mode="Markdown",
    )
