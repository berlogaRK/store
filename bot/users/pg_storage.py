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
        SELECT id, username, first_name, last_name, total_purchases, total_spent_rub, ref, bonus_balance
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

    async def add_bonus(self, user_id: int, amount: int) -> None:
        sql = """
        UPDATE users
        SET bonus_balance = bonus_balance + $2
        WHERE id = $1;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, user_id, amount)

    async def deduct_bonus(self, user_id: int, amount: int) -> None:
        sql = """
        UPDATE users
        SET bonus_balance = GREATEST(bonus_balance - $2, 0)
        WHERE id = $1;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, user_id, amount)

    _ADD_IS_BLOCKED = """
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_blocked boolean NOT NULL DEFAULT false;
    """

    async def get_broadcast_ids(self) -> list[int]:
        sql = "SELECT id FROM users WHERE is_blocked = false ORDER BY id;"
        async with self.pool.acquire() as conn:
            try:
                rows = await conn.fetch(sql)
            except asyncpg.UndefinedColumnError:
                # колонки ещё нет (старая схема) — добавляем и повторяем
                await conn.execute(self._ADD_IS_BLOCKED)
                rows = await conn.fetch(sql)
        return [int(r["id"]) for r in rows]

    async def mark_blocked(self, user_id: int) -> None:
        sql = "UPDATE users SET is_blocked = true WHERE id = $1;"
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(sql, user_id)
            except asyncpg.UndefinedColumnError:
                await conn.execute(self._ADD_IS_BLOCKED)
                await conn.execute(sql, user_id)

