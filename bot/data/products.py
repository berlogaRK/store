from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Price:
    amount: Decimal
    asset: str


@dataclass(frozen=True)
class Product:
    id: str
    title: str
    description: str
    price_rub: int
    image_path: str | None = None


PRODUCTS = [
    Product(
        id="gpt_plus_1m",
        title="Подписка ChatGPT Plus на месяц",
        description=(
        "После покупки запросим почту и подключим подписку.\n\n"
        "[Подробное описание товара](https://t.me/itberloga_store/4)"
        ),
        price_rub=1499,
        image_path="assets/chatgpt.jpg",
    ),
    Product(
        id="gpt_plus_25d",
        title="Подписка ChatGPT Plus на 25 Дней",
        description=(
        "После покупки запросим почту и подключим подписку.\n\n"
        "[Подробное описание товара](https://t.me/itberloga_store/4)"
        ),
        price_rub=1299,
        image_path="assets/chatgpt.jpg",
    ),
        Product(
        id="google_gemini",
        title="Подписка Gemini Plus на месяц",
        description=(
        "После покупки запросим необходимые данные и подключим подписку.\n\n"
        "[Подробное описание товара](https://t.me/itberloga_store/5)"
        ),
        price_rub=1099,
        image_path="assets/gemini.jpg",
    )
]


def get_product(pid: str) -> Product | None:
    return next((p for p in PRODUCTS if p.id == pid), None)
