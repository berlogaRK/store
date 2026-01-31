from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import asyncpg

from bot.promos.model import PromoCode, PromoType


class PgPromoStorage:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_promo(self, code: str) -> Optional[PromoCode]:
        sql = """
        SELECT
            code,
            type,
            value,
            active,
            expires_at,
            max_uses,
            per_user_limit,
            allowed_products
        FROM promos
        WHERE code = $1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(sql, code.upper())

        if not row:
            return None

        return PromoCode(
            code=row["code"],
            type=PromoType(row["type"]),
            value=int(row["value"]),
            active=row["active"],
            expires_at=row["expires_at"],
            max_uses=row["max_uses"],
            per_user_limit=row["per_user_limit"],
            allowed_products=row["allowed_products"],
        )

    async def get_usage(self, code: str) -> dict:
        sql = """
        SELECT user_id
        FROM promo_usages
        WHERE promo_code = $1
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, code.upper())

        usage = {"total_uses": len(rows), "users": {}}
        for r in rows:
            uid = str(r["user_id"])
            usage["users"][uid] = usage["users"].get(uid, 0) + 1

        return usage

    async def increment_usage(self, code: str, user_id: int) -> None:
        sql = """
        INSERT INTO promo_usages (promo_code, user_id, used_at)
        VALUES ($1, $2, $3)
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                sql,
                code.upper(),
                user_id,
                datetime.now(timezone.utc),
            )
