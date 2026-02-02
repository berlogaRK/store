from typing import Any, Callable, TypeVar
from bot.config import PAYMENTS_ENABLED, load_config

try:
    from aiosend import CryptoPay  # type: ignore
except Exception:  # pragma: no cover
    CryptoPay = None  # type: ignore


T = TypeVar("T", bound=Callable[..., Any])


class NullCryptoPay:

    def invoice_paid(self) -> Callable[[T], T]:
        def decorator(func: T) -> T:
            return func

        return decorator

    async def start_polling(self) -> None:
        return

    async def create_invoice(self, *args, **kwargs):
        raise RuntimeError("Payments are disabled (ENABLE_PAYMENTS=false / APP_ENV=test)")

if PAYMENTS_ENABLED:
    if CryptoPay is None:
        raise RuntimeError("aiosend is not installed, but payments are enabled")

    cfg = load_config()
    if not cfg.crypto_pay_token:
        raise RuntimeError("CRYPTO_PAY_TOKEN is not set (payments are enabled)")

    crypto_pay = CryptoPay(cfg.crypto_pay_token)
else:
    crypto_pay = NullCryptoPay()
