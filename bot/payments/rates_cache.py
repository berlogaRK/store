import asyncio
import time
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple

from bot.services.crypto_pay import crypto_pay

_TTL_SECONDS = 30

_lock = asyncio.Lock()
_cached_at = 0.0
_rates: Dict[Tuple[str, str], float] = {}


def _now() -> float:
    return time.monotonic()


async def _refresh_rates() -> None:
    """
    Обновляет кеш курсов из Crypto Pay.
    get_exchange_rates() -> список объектов ExchangeRate (source, target, rate).
    """
    global _cached_at, _rates

    rates_list = await crypto_pay.get_exchange_rates()  # :contentReference[oaicite:1]{index=1}

    new_map: Dict[Tuple[str, str], float] = {}
    for r in rates_list:
        src = getattr(r, "source", None)
        tgt = getattr(r, "target", None)
        rate = getattr(r, "rate", None)
        if not src or not tgt or rate is None:
            continue
        try:
            new_map[(str(src).upper(), str(tgt).upper())] = float(rate)
        except Exception:
            continue

    _rates = new_map
    _cached_at = _now()


async def get_rate(source: str, target: str) -> float:
    """
    Возвращает курс: 1 source = rate target.
    Если прямого нет, пытается использовать обратный (инверсию).
    """
    src = source.upper()
    tgt = target.upper()

    async with _lock:
        if (_now() - _cached_at) > _TTL_SECONDS or not _rates:
            await _refresh_rates()

        direct = _rates.get((src, tgt))
        if direct is not None:
            return direct

        inverse = _rates.get((tgt, src))
        if inverse is not None and inverse != 0:
            return 1.0 / inverse

    raise RuntimeError(f"No exchange rate for {src}->{tgt}")


async def convert(amount: float, source: str, target: str) -> float:
    rate = await get_rate(source, target)
    return float(amount) * rate


def quantize_amount(amount: float, asset: str) -> float:
    asset = asset.upper()

    if asset == "TON":
        q = Decimal("0.01")      # ✅ сотые
    elif asset == "USDT":
        q = Decimal("0.01")      # обычно тоже сотые
    else:
        q = Decimal("0.000001")  # запасной вариант

    return float(Decimal(str(amount)).quantize(q, rounding=ROUND_HALF_UP))