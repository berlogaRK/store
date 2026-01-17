from aiosend import CryptoPay
from bot.config import load_config

cfg = load_config()

crypto_pay = CryptoPay(cfg.crypto_pay_token)
