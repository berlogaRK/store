from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()
MANAGER_1_ID = int(os.getenv("MANAGER_1_ID"))
MANAGER_2_ID = int(os.getenv("MANAGER_2_ID"))
TICKETS_CHAT_ID = int(os.getenv("TICKETS_CHAT_ID"))

MANAGERS = [
    MANAGER_1_ID,   # robertokkkk
    MANAGER_2_ID,   # raxlin4ik
]

DEV_MODE = True

@dataclass
class Config:
    token: str
    crypto_pay_token: str


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN")
    crypto_token = os.getenv("CRYPTO_PAY_TOKEN")

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set")
    if not crypto_token:
        raise RuntimeError("CRYPTO_PAY_TOKEN is not set")

    return Config(
        token=bot_token,
        crypto_pay_token=crypto_token,
    )
