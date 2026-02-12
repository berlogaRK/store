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

    async def try_set_ref(self, user_id: int, ref_id: int, pool: asyncpg.Pool | None = None) -> bool:
        if pool is None:
            return await self.storage.try_set_ref(user_id, ref_id)

        try:
            return await PgUserStorage(pool).try_set_ref(user_id, ref_id)
        except Exception:
            return await self.storage.try_set_ref(user_id, ref_id)

    async def get_profile(self, user_id: int, pool: asyncpg.Pool | None = None) -> dict:
        if pool is None:
            return await self.storage.get_profile(user_id)

        try:
            data = await PgUserStorage(pool).get_profile(user_id)
            return data or {}
        except Exception:
            return await self.storage.get_profile(user_id)

    async def count_invited(self, ref_id: int, pool: asyncpg.Pool | None = None) -> int:
        if pool is None:
            return await self.storage.count_invited(ref_id)

        try:
            return await PgUserStorage(pool).count_invited(ref_id)
        except Exception:
            return await self.storage.count_invited(ref_id)

    async def add_bonus(self, user_id: int, amount: int, pool=None):
        if amount <= 0:
            return

        if pool is None:
            return await self.storage.add_bonus(user_id, amount)

        try:
            return await PgUserStorage(pool).add_bonus(user_id, amount)
        except Exception:
            return await self.storage.add_bonus(user_id, amount)

    async def deduct_bonus(self, user_id: int, amount: int, pool=None):
        if amount <= 0:
            return

        if pool is None:
            return await self.storage.deduct_bonus(user_id, amount)

        try:
            return await PgUserStorage(pool).deduct_bonus(user_id, amount)
        except Exception:
            return await self.storage.deduct_bonus(user_id, amount)
