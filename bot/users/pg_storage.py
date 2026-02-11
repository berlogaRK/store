from __future__ import annotations

import asyncpg


class PgUserStorage:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def upsert_user(self, user) -> None:
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
            await conn.execute(sql, user.id, user.username, user.first_name, user.last_name)

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

    async def try_set_ref(self, user_id: int, ref_id: int) -> bool:
        if user_id == ref_id:
            return False

        sql = """
        UPDATE users
        SET ref = $2
        WHERE id = $1
        AND ref IS NULL
        AND total_spent_rub = 0;
        """

        async with self.pool.acquire() as conn:
            result = await conn.execute(sql, user_id, ref_id)

        # result будет типа: "UPDATE 1"
        return result.endswith("1")
    
    async def get_profile(self, user_id: int) -> dict | None:
        sql = """
        SELECT id, username, first_name, last_name, total_purchases, total_spent_rub, ref
        FROM users
        WHERE id = $1;
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(sql, user_id)

        return dict(row) if row else None

    async def count_invited(self, ref_id: int) -> int:
        sql = "SELECT COUNT(*) FROM users WHERE ref = $1;"
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(sql, ref_id)
        return int(count or 0)
