from aiogram.filters.callback_data import CallbackData

class NavCb(CallbackData, prefix="nav"):
    page: str
    payload: str | None = None

class BuyCb(CallbackData, prefix="buy"):
    product_id: str

class PayCb(CallbackData, prefix="pay"):
    method: str
    product_id: str

class PromoCb(CallbackData, prefix="promo"):
    action: str         # "enter" | "clear"
    product_id: str

class NewPurchaseCb(CallbackData, prefix="new_purchase"):
    pass