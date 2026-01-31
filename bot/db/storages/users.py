from __future__ import annotations

import asyncpg
from dataclasses import dataclass


@dataclass(frozen=True)
class TgUserData:
    id: int
    username: str | None
    first_name: str | None
    last_name: str | None


class UsersStorage:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def upsert_and_touch(self, u: TgUserData) -> None:
        # first_seen оставляем при первом создании,
        # last_seen обновляем всегда
        sql = """
        INSERT INTO users (id, username, first_name, last_name, first_seen, last_seen)
        VALUES ($1, $2, $3, $4, now(), now())
        ON CONFLICT (id) DO UPDATE
        SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            last_seen = now();
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, u.id, u.username, u.first_name, u.last_name)

    async def add_purchase(self, user_id: int, amount_rub: int) -> None:
        sql = """
        UPDATE users
        SET total_purchases = total_purchases + 1,
            total_spent_rub = total_spent_rub + $2,
            last_seen = now()
        WHERE id = $1;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, user_id, amount_rub)
