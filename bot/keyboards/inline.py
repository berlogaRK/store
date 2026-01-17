from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.keyboards.callbacks import NavCb, BuyCb
from bot.data.products import PRODUCTS

REVIEWS_CHANNEL_URL = "https://t.me/itberloga_reviews"

SUPPORT_USER_URL = "https://t.me/raxlin4ik"

def home_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Каталог", callback_data=NavCb(page="catalog").pack())
    kb.button(text="Отзывы", url=REVIEWS_CHANNEL_URL)
    kb.button(text="Тех. поддержка", url=SUPPORT_USER_URL)
    kb.adjust(2, 1)
    return kb.as_markup()

def catalog_kb():
    kb = InlineKeyboardBuilder()
    for p in PRODUCTS:
        kb.button(text=p.title, callback_data=NavCb(page="product", payload=p.id).pack())
    kb.button(text="⬅ Назад", callback_data=NavCb(page="home").pack())
    kb.adjust(1)
    return kb.as_markup()

def product_kb(product_id: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="Купить", callback_data=BuyCb(product_id=product_id).pack())
    kb.button(text="⬅ Назад", callback_data=NavCb(page="catalog").pack())
    kb.button(text="🏠 Главная", callback_data=NavCb(page="home").pack())
    kb.adjust(1, 2)
    return kb.as_markup()

def only_home_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🏠 Главная", callback_data=NavCb(page="home").pack())
    return kb.as_markup()