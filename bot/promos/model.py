from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing import Optional, Sequence


class PromoType(str, Enum):
    PERCENT = "percent"  # -N%
    FIXED = "fixed"      # -N rub


@dataclass(frozen=True)
class PromoCode:
    code: str
    type: PromoType
    value: int
    active: bool = True
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    per_user_limit: Optional[int] = None
    allowed_products: Optional[Sequence[str]] = None


@dataclass(frozen=True)
class PromoApplyResult:
    code: str
    original_price_rub: int
    discount_rub: int
    final_price_rub: int
    description: str
