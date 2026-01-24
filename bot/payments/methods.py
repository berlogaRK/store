from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentMethod:
    code: str          # usdt / ton / stars
    asset: str         # USDT / TON / STARS
    title: str         # для кнопки
    enabled: bool = True
    disabled_text: str | None = None

PAYMENT_METHODS = {
    "usdt": PaymentMethod("usdt", "USDT", "💎 USDT (CryptoBot)"),
    "ton": PaymentMethod("ton", "TON", "🪙 TON (CryptoBot)"),
    "rub": PaymentMethod("rub", "RUB", "RUB (СБП)"),
    "eur": PaymentMethod("eur", "EUR", "Visa / Mastercard (Скоро)", False, "💳 Оплата картами Visa / Mastercard (EU)\n\nЭтот способ оплаты находится в разработке и скоро будет доступен.\n\nСпасибо за ожидание ❤️")
}
