from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.keyboards.callbacks import PayCb, NavCb, NewPurchaseCb, PromoCb, PayGroupCb
from bot.payments.methods import PAYMENT_METHODS



def payment_groups_kb(product_id: str, has_promo: bool = False):
    kb = InlineKeyboardBuilder()

    kb.button(
        text="Crypto",
        callback_data=PayGroupCb(group="crypto", product_id=product_id).pack()
    )

    rub = PAYMENT_METHODS.get("rub")
    if rub:
        text = rub.title + (" 🔒" if not rub.enabled else "")
        kb.button(text=text, callback_data="noop")

    if has_promo:
        kb.button(
            text="❌ Убрать промокод",
            callback_data=PromoCb(action="clear", product_id=product_id).pack()
        )
    else:
        kb.button(
            text="🏷 Промокод",
            callback_data=PromoCb(action="enter", product_id=product_id).pack()
        )

    kb.button(text="⬅ Назад", callback_data=NavCb(page="catalog").pack())
    kb.button(text="🏠 Главная", callback_data=NavCb(page="home").pack())

    kb.adjust(1, 1, 1, 2)
    return kb.as_markup()



def crypto_methods_kb(product_id: str):
    kb = InlineKeyboardBuilder()

    for code in ("ton", "usdt"):
        method = PAYMENT_METHODS.get(code)
        if not method:
            continue

        kb.button(
            text=method.title,
            callback_data=PayCb(method=method.code, product_id=product_id).pack()
        )

    kb.button(
        text="⬅ Назад",
        callback_data=NavCb(page="payment_groups", payload=product_id).pack()
    )

    kb.adjust(1)
    return kb.as_markup()



# def payment_methods_kb(product_id: str, has_promo: bool = False):
#     kb = InlineKeyboardBuilder()

#     # кнопки способов оплаты
#     for method in PAYMENT_METHODS.values():
#         text = method.title
#         if not method.enabled:
#             text += " 🔒"

#         kb.button(
#             text=text,
#             callback_data=PayCb(
#                 method=method.code,
#                 product_id=product_id
#             ).pack()
#         )

#     # кнопка промокода
#     if has_promo:
#         kb.button(
#             text="❌ Убрать промокод",
#             callback_data=PromoCb(
#                 action="clear",
#                 product_id=product_id
#             ).pack()
#         )
#     else:
#         kb.button(
#             text="🏷 Промокод",
#             callback_data=PromoCb(
#                 action="enter",
#                 product_id=product_id
#             ).pack()
#         )

#     # навигация
#     kb.button(text="⬅ Назад", callback_data=NavCb(page="catalog").pack())
#     kb.button(text="🏠 Главная", callback_data=NavCb(page="home").pack())

#     # сетка:
#     # 1 — способы оплаты (каждый в своей строке)
#     # 1 — промокод
#     # 2 — навигация
#     kb.adjust(1, 1, 2)
#     return kb.as_markup()


def pay_invoice_kb(pay_url: str, product_id: str):
    kb = InlineKeyboardBuilder()

    kb.button(text="💳 Оплатить", url=pay_url)
    kb.button(text="⬅ Назад", callback_data=NavCb(page="product", payload=product_id).pack())

    kb.adjust(1, 1)
    return kb.as_markup()


def purchase_done_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Новая покупка", callback_data=NewPurchaseCb().pack())
    kb.adjust(1)
    return kb.as_markup()