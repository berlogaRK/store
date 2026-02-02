from __future__ import annotations
from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


def _str_to_bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


# === Режим приложения ===
# - APP_ENV=prod  → прод (PostgreSQL, платежи включены по умолчанию)
# - APP_ENV=test  → тест (JSON, платежи выключены по умолчанию)
APP_ENV = (os.getenv("APP_ENV") or "prod").strip().lower()
IS_PROD = APP_ENV == "prod"
IS_TEST = not IS_PROD

PAYMENTS_ENABLED = _str_to_bool(os.getenv("ENABLE_PAYMENTS"), default=IS_PROD)


def _env_int(name: str, *, required: bool = False, default: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        if required:
            raise RuntimeError(f"{name} is not set")
        return default
    try:
        return int(raw)
    except Exception as e:
        if required:
            raise RuntimeError(f"{name} must be an integer") from e
        return default


MANAGER_1_ID = _env_int("MANAGER_1_ID", required=IS_PROD)
MANAGER_2_ID = _env_int("MANAGER_2_ID", required=IS_PROD)
TICKETS_CHAT_ID = _env_int("TICKETS_CHAT_ID", required=IS_PROD)

MANAGERS = [x for x in (MANAGER_1_ID, MANAGER_2_ID) if x]

@dataclass
class Config:
    token: str
    crypto_pay_token: str | None = None
    platega_merchant_id: str | None = None
    platega_secret: str | None = None


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set")

    crypto_token = os.getenv("CRYPTO_PAY_TOKEN")
    platega_merchant_id = os.getenv("PLATEGA_MERCHANT_ID")
    platega_secret = os.getenv("PLATEGA_SECRET")

    if PAYMENTS_ENABLED:
        if not crypto_token:
            raise RuntimeError("CRYPTO_PAY_TOKEN is not set (payments are enabled)")
        if not platega_merchant_id:
            raise RuntimeError("PLATEGA_MERCHANT_ID is not set (payments are enabled)")
        if not platega_secret:
            raise RuntimeError("PLATEGA_SECRET is not set (payments are enabled)")

    return Config(
        token=bot_token,
        crypto_pay_token=crypto_token,
        platega_merchant_id=platega_merchant_id,
        platega_secret=platega_secret,
    )
