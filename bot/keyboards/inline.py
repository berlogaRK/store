from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.callbacks import NavCb, BuyCb, BackCb
from bot.data.products import get_products_by_category, CATEGORIES

REVIEWS_CHANNEL_URL = "https://t.me/itberloga_reviews"
SUPPORT_USER_URL = "https://t.me/itberloga_manager"

PRIVACY_URL = "https://telegra.ph/Politika-konfidencialnosti-01-18-75"
TERMS_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-01-18-50"


def home_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Каталог", callback_data=NavCb(page="catalog").pack())
    kb.button(text="Отзывы", url=REVIEWS_CHANNEL_URL)
    kb.button(text="Профиль", callback_data=NavCb(page="profile").pack())
    kb.button(text="Информация", callback_data=NavCb(page="info").pack())
    kb.button(text="Тех. поддержка", url=SUPPORT_USER_URL)
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def catalog_kb():
    kb = InlineKeyboardBuilder()

    for c in CATEGORIES:
        if c.id == "chatgpt":
            # ✅ B-вариант: ChatGPT сразу открывает Business
            kb.button(
                text=c.title,
                callback_data=NavCb(page="product", payload="gpt_business_1m").pack()
            )
        else:
            kb.button(
                text=c.title,
                callback_data=NavCb(page="category", payload=c.id).pack()
            )

    kb.button(text="⬅ Назад", callback_data=NavCb(page="home").pack())
    kb.adjust(1)
    return kb.as_markup()


def category_products_kb(category_id: str):
    kb = InlineKeyboardBuilder()
    products = get_products_by_category(category_id)

    for p in products:
        kb.button(text=p.title, callback_data=NavCb(page="product", payload=p.id).pack())

    kb.button(text="⬅ Назад", callback_data=BackCb(page="catalog").pack())
    kb.adjust(1)
    return kb.as_markup()


def only_home_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🏠 Главная", callback_data=NavCb(page="home").pack())
    return kb.as_markup()


def info_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📜 Политика конфиденциальности", url=PRIVACY_URL)
    kb.button(text="📄 Пользовательское соглашение", url=TERMS_URL)
    kb.button(text="⬅ Назад", callback_data=BackCb(page="home").pack())
    kb.adjust(1)
    return kb.as_markup()


def chatgpt_plans_kb():
    """
    На всякий случай оставляем экран планов,
    но убираем Plus полностью — только Business.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="ChatGPT Business", callback_data=NavCb(page="product", payload="gpt_business_1m").pack())
    kb.button(text="⬅ Назад", callback_data=BackCb(page="catalog").pack())
    kb.adjust(1)
    return kb.as_markup()

def profile_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔗 Ссылка для друга", callback_data=NavCb(page="ref_link").pack())
    kb.button(text="⬅ Назад", callback_data=BackCb(page="home").pack())
    kb.adjust(1)
    return kb.as_markup()