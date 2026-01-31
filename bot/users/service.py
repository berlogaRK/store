from __future__ import annotations

import asyncpg

from bot.users.storage import JsonUserStorage
from bot.users.pg_storage import PgUserStorage


class UserService:
    def __init__(self, storage: JsonUserStorage):
        self.storage = storage  # JSON fallback

    async def track(self, user, pool: asyncpg.Pool | None = None) -> None:
        if pool is None:
            await self.storage.upsert_user(user)
            return

        try:
            await PgUserStorage(pool).upsert_user(user)
        except Exception:
            # мягкий fallback — бот не падает
            await self.storage.upsert_user(user)

    async def add_purchase(self, user_id: int, amount_rub: int, pool: asyncpg.Pool | None = None) -> None:
        if pool is None:
            await self.storage.add_purchase(user_id, amount_rub)
            return

        try:
            await PgUserStorage(pool).add_purchase(user_id, amount_rub)
        except Exception:
            await self.storage.add_purchase(user_id, amount_rub)
