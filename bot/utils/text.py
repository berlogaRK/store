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