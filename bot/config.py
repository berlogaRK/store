from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()
MANAGER_1_ID = int(os.getenv("MANAGER_1_ID"))
MANAGER_2_ID = int(os.getenv("MANAGER_2_ID"))
TICKETS_CHAT_ID = int(os.getenv("TICKETS_CHAT_ID"))

MANAGERS = [MANAGER_1_ID, MANAGER_2_ID]

DEV_MODE = True

@dataclass
class Config:
    token: str
    crypto_pay_token: str
    platega_merchant_id: str
    platega_secret: str


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN")
    crypto_token = os.getenv("CRYPTO_PAY_TOKEN")
    platega_merchant_id = os.getenv("PLATEGA_MERCHANT_ID")
    platega_secret = os.getenv("PLATEGA_SECRET")

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set")
    if not crypto_token:
        raise RuntimeError("CRYPTO_PAY_TOKEN is not set")
    if not platega_merchant_id:
        raise RuntimeError("PLATEGA_MERCHANT_ID is not set")
    if not platega_secret:
        raise RuntimeError("PLATEGA_SECRET is not set")

    return Config(
        token=bot_token,
        crypto_pay_token=crypto_token,
        platega_merchant_id=platega_merchant_id,
        platega_secret=platega_secret,
    )
