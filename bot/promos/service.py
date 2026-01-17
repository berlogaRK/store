from datetime import datetime, timezone

from bot.promos.model import PromoApplyResult, PromoCode, PromoType
from bot.data.products import Product
from bot.promos.storage import JsonPromoStorage


class PromoError(Exception):
    pass


class PromoService:
    def __init__(self, storage: JsonPromoStorage):
        self.storage = storage

    async def validate(self, code: str, user_id: int, product: Product) -> PromoCode:
        promo = await self.storage.get_promo(code)
        if not promo:
            raise PromoError("Промокод не найден")

        if not promo.active:
            raise PromoError("Промокод неактивен")

        if promo.expires_at is not None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if promo.expires_at < now:
                raise PromoError("Срок действия промокода истёк")

        if promo.allowed_products is not None and product.id not in promo.allowed_products:
            raise PromoError("Промокод не подходит для этого товара")

        usage = await self.storage.get_usage(promo.code)

        if promo.max_uses is not None and int(usage.get("total_uses", 0)) >= int(promo.max_uses):
            raise PromoError("Лимит использований промокода исчерпан")

        if promo.per_user_limit is not None:
            user_count = int(usage.get("users", {}).get(str(user_id), 0))
            if user_count >= int(promo.per_user_limit):
                raise PromoError("Вы уже использовали этот промокод")

        return promo

    async def apply(self, code: str, user_id: int, product: Product) -> PromoApplyResult:
        promo = await self.validate(code, user_id, product)

        original = int(product.price_rub)
        discount = 0

        if promo.type == PromoType.PERCENT:
            discount = (original * int(promo.value)) // 100
        elif promo.type == PromoType.FIXED:
            discount = int(promo.value)

        # защита от отрицательных цен
        discount = max(0, min(discount, original))
        final_price = original - discount

        desc = (
            f"-{promo.value}% по промокоду {promo.code}"
            if promo.type == PromoType.PERCENT
            else f"-{discount} ₽ по промокоду {promo.code}"
        )

        return PromoApplyResult(
            code=promo.code,
            original_price_rub=original,
            discount_rub=discount,
            final_price_rub=final_price,
            description=desc,
        )

    async def mark_used(self, code: str, user_id: int) -> None:
        await self.storage.increment_usage(code, user_id)
