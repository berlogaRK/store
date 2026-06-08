from dataclasses import dataclass
from typing import List
from bot.utils.media import PERPLEXITY_IMAGE, GEMINI_IMAGE, GPT_IMAGE, CLAUDE_IMAGE


@dataclass(frozen=True)
class Category:
    id: str
    title: str

CATEGORIES: List[Category] = [
    Category(
        id="gpt",
        title="ChatGPT Plus",
    ),
    Category(
        id="cld",
        title="Claude Pro",
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
        id="gpt_plus",
        title="Подписка ChatGPT Plus на месяц",
        description=(
        "После покупки запросим необходимые данные и подключим подписку.\n\n" 
        "[Подробное описание товара](https://t.me/itberloga_store/18)"
        ),
        price_rub=1899,
        category_id="gpt",
        image_path=GPT_IMAGE,
    ),
    Product(
        id="claude_pro",
        title="Подписка Claude Pro на месяц",
        description=(
        "После покупки запросим необходимые данные и подключим подписку.\n\n"
        "[Подробное описание товара](https://t.me/itberloga_store/29)"
        ),
        price_rub=2400,
        category_id="cld",
        image_path=CLAUDE_IMAGE,
    ),
    Product(
        id="google_gemini",
        title="Подписка Google Gemini Pro на месяц",
        description=(
        "После покупки запросим необходимые данные и подключим подписку.\n\n"
        "[Подробное описание товара](https://t.me/itberloga_store/5)"
        ),
        price_rub=1250,
        category_id="google_gemini",
        image_path=GEMINI_IMAGE,
    ),
    Product(
        id="perplexity",
        title="Подписка Perplexity Pro на месяц",
        description=(
        "После покупки запросим необходимые данные и подключим подписку.\n\n"
        "[Подробное описание товара](https://t.me/itberloga_store/20)"
        ),
        price_rub=1250,
        category_id="perplexity",
        image_path=PERPLEXITY_IMAGE,
    )
]


def get_product(pid: str) -> Product | None:
    return next((p for p in PRODUCTS if p.id == pid), None)

def get_products_by_category(category_id: str) -> list[Product]:
    return [p for p in PRODUCTS if p.category_id == category_id]