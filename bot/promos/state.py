from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class PromoState:
    product_id: str
    promo_code: Optional[str] = None
    final_price_rub: Optional[int] = None
    discount_rub: Optional[int] = None


# выбранный промокод по пользователю (память процесса)
USER_PROMO: Dict[int, PromoState] = {}

# ожидание ввода промокода (какой товар сейчас "в контексте")
AWAITING_PROMO_FOR_PRODUCT: Dict[int, str] = {}
