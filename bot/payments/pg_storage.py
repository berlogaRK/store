# bot/payments/pg_storage.py
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Literal

import asyncpg


PaymentMethod = Literal["sbp", "crypto"]
PaymentStatus = Literal["pending", "paid", "expired"]


@dataclass(frozen=True)
class PaymentCreate:
    order_id: uuid.UUID
    ticket_id: Optional[str]          # тикет (для Platega ваш 8-символьный), для crypto можно None/строка
    user_id: int
    product_id: str
    promo_code: Optional[str]
    final_price_rub: int
    payment_method: PaymentMethod
    status: PaymentStatus = "pending"
    created_at: Optional[datetime] = None


class PgPaymentsStorage:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def create_payment(self, p: PaymentCreate) -> None:
        created_at = p.created_at or datetime.now(timezone.utc)

        sql = """
        INSERT INTO payments (
            order_id, ticket_id, user_id, product_id, promo_code,
            final_price_rub, payment_method, status, created_at
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        ON CONFLICT (order_id) DO NOTHING
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                sql,
                p.order_id,
                p.ticket_id,
                p.user_id,
                p.product_id,
                p.promo_code,
                p.final_price_rub,
                p.payment_method,
                p.status,
                created_at,
            )

    async def mark_paid(self, order_id: uuid.UUID) -> bool:
        sql = """
        UPDATE payments
        SET status='paid'
        WHERE order_id=$1 AND status <> 'paid'
        """
        async with self.pool.acquire() as conn:
            res = await conn.execute(sql, order_id)
        # res: "UPDATE <n>"
        return res.split()[-1].isdigit() and int(res.split()[-1]) > 0

    async def mark_expired(self, order_id: uuid.UUID) -> bool:
        sql = """
        UPDATE payments
        SET status='expired'
        WHERE order_id=$1 AND status <> 'paid'
        """
        async with self.pool.acquire() as conn:
            res = await conn.execute(sql, order_id)
        return res.split()[-1].isdigit() and int(res.split()[-1]) > 0

    async def get_status(self, order_id: uuid.UUID) -> Optional[str]:
        sql = "SELECT status FROM payments WHERE order_id=$1"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(sql, order_id)
