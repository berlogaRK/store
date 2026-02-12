from aiogram.filters.callback_data import CallbackData


class NavCb(CallbackData, prefix="nav"):
    page: str
    payload: str | None = None


class BackCb(CallbackData, prefix="back"):
    """Явная навигация назад: куда вернуться (page + payload)."""
    page: str
    payload: str | None = None


class BuyCb(CallbackData, prefix="buy"):
    product_id: str


class PayCb(CallbackData, prefix="pay"):
    method: str
    product_id: str


class PromoCb(CallbackData, prefix="promo"):
    action: str  # "enter" | "clear"
    product_id: str


class NewPurchaseCb(CallbackData, prefix="new_purchase"):
    pass


class PayGroupCb(CallbackData, prefix="pay_group"):
    group: str
    product_id: str

class BonusCb(CallbackData, prefix="bonus"):
    action: str  
    product_id: str
