def home_text() -> str:
    ...

def catalog_text() -> str:
    ...

def product_text(title, description, price_text: str):
    return (
        f"📦 *{title}*\n\n"
        f"{description}\n\n"
        f"💰 Цена: {price_text}"
    )

def profile_text(
    user_id: int,
    username: str | None,
    first_name: str | None,
    ref_id: int | None,
    invited_count: int,
):
    name = first_name or username or "пользователь"

    ref_line = f"{ref_id}" if ref_id else "—"

    return (
        f"👤 *Профиль*\n\n"
        f"Привет, {name}! (ID: `{user_id}`)\n\n"
        f"Доступные бонусы: \n\n"
        f"Вас пригласил: `{ref_line}`\n"
        f"Приглашено друзей: *{invited_count}*\n\n"
        f"[Для чего нужен профиль?](https://t.me/itberloga_store/8)"
    )
