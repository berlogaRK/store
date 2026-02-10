from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Category:
    id: str
    title: str

CATEGORIES: List[Category] = [
    Category(
        id="gpt",
        title="ChatGPT",
    ),
    Category(
        id="google_gemini",
        title="Google Gemini Pro",
    ),
    Category(
        id="perplexity",
        title="Perplexity Pro",
    ),
]

def get_category(cid: str) -> Category | None:
    return next((c for c in CATEGORIES if c.id == cid), None)



@dataclass(frozen=True)
class Product:
    id: str
    title: str
    description: str
    price_rub: int
    category_id: str
    image_path: str | None = None


PRODUCTS: List[Product] = [
    Product(
        id="gpt_business_1m",
        title="Подписка ChatGPT Business на месяц",
        description=(
        "После покупки запросим необходимые данные и подключим подписку.\n\n"
        "[Подробное описание товара](https://t.me/itberloga_store/4)"
        ),
        price_rub=1499,
        category_id="gpt",
        image_path="assets/chatgpt.jpg",
    ),
    Product(
        id="gpt_plus_1m",
        title="Подписка ChatGPT Plus на месяц",
        description=(
        "После покупки запросим необходимые данные и подключим подписку.\n\n"
        "[Подробное описание товара](https://t.me/itberloga_store/18)"
        ),
        price_rub=1299,
        category_id="gpt",
        image_path="assets/chatgpt.jpg",
    ),
        Product(
        id="google_gemini",
        title="Подписка Google Gemini Pro на месяц",
        description=(
        "После покупки запросим необходимые данные и подключим подписку.\n\n"
        "[Подробное описание товара](https://t.me/itberloga_store/5)"
        ),
        price_rub=1099,
        category_id="google_gemini",
        image_path="assets/gemini.jpg",
    ),
        Product(
        id="perplexity",
        title="Подписка Perplexity Pro на месяц",
        description=(
        "После покупки запросим необходимые данные и подключим подписку.\n\n"
        "[Подробное описание товара](https://t.me/itberloga_store/20)"
        ),
        price_rub=1,
        category_id="perplexity",
        image_path="assets/perplexity.jpg",
    )
]


def get_product(pid: str) -> Product | None:
    return next((p for p in PRODUCTS if p.id == pid), None)

def get_products_by_category(category_id: str) -> list[Product]:
    return [p for p in PRODUCTS if p.category_id == category_id]