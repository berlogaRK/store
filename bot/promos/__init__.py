from pathlib import Path

from bot.promos.service import PromoService
from bot.promos.storage import JsonPromoStorage
from bot.promos.pg_storage import PgPromoStorage

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

# JSON fallback (временно)
json_storage = JsonPromoStorage(
    promos_path=str(DATA_DIR / "promos.json"),
    usage_path=str(DATA_DIR / "promo_usage.json"),
)

_pg_pool = None


def set_pg_pool(pool):
    global _pg_pool
    _pg_pool = pool


class PromoStorageProxy:
    """
    PG primary → JSON fallback
    """

    def __init__(self):
        self.pg = None

    def _pg(self):
        if self.pg is None and _pg_pool:
            self.pg = PgPromoStorage(_pg_pool)
        return self.pg

    async def get_promo(self, code):
        if self._pg():
            promo = await self.pg.get_promo(code)
            if promo:
                return promo
        return await json_storage.get_promo(code)

    async def get_usage(self, code):
        if self._pg():
            return await self.pg.get_usage(code)
        return await json_storage.get_usage(code)

    async def increment_usage(self, code, user_id):
        if self._pg():
            await self.pg.increment_usage(code, user_id)
            return
        await json_storage.increment_usage(code, user_id)


promo_service = PromoService(PromoStorageProxy())
