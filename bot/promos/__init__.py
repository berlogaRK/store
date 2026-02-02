from pathlib import Path

from bot.promos.service import PromoService
from bot.promos.storage import JsonPromoStorage

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

# JSON fallback (временно / для test-режима)
json_storage = JsonPromoStorage(
    promos_path=str(DATA_DIR / "promos.json"),
    usage_path=str(DATA_DIR / "promo_usage.json"),
)

_pg_pool = None


def set_pg_pool(pool) -> None:
    global _pg_pool
    _pg_pool = pool


class PromoStorageProxy:
    def __init__(self):
        self._pg_storage = None

    def _pg(self):
        # Ленивая инициализация, чтобы в test-режиме вообще не трогать PG-код.
        if self._pg_storage is None and _pg_pool is not None:
            from bot.promos.pg_storage import PgPromoStorage  # lazy import
            self._pg_storage = PgPromoStorage(_pg_pool)
        return self._pg_storage

    async def get_promo(self, code):
        pg = self._pg()
        if pg:
            promo = await pg.get_promo(code)
            if promo:
                return promo
        return await json_storage.get_promo(code)

    async def get_usage(self, code):
        pg = self._pg()
        if pg:
            return await pg.get_usage(code)
        return await json_storage.get_usage(code)

    async def increment_usage(self, code, user_id):
        pg = self._pg()
        if pg:
            await pg.increment_usage(code, user_id)
            return
        await json_storage.increment_usage(code, user_id)


promo_service = PromoService(PromoStorageProxy())
