import os
import asyncio

from aiogram import Bot, Dispatcher

from bot.config import load_config
from bot.handlers.start import router as start_router
from bot.handlers.catalog import router as catalog_router
from bot.handlers import payments, info

from bot.middlewares.users import UserTrackingMiddleware

from bot.services.crypto_pay import crypto_pay
from bot.webhooks.platega_webhook import start_platega_webhook_server

from bot.db.pool import PgConfig, create_pool


async def main():
    cfg = load_config()

    bot = Bot(token=cfg.token)
    dp = Dispatcher()

    # --- PostgreSQL pool ---
    pg_cfg = PgConfig(
        host=os.getenv("PG_HOST"),
        port=int(os.getenv("PG_PORT", "5432")),
        database=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASS"),
        sslmode=os.getenv("PG_SSLMODE", "disable"),
    )

    pool = await create_pool(pg_cfg)
    dp["db_pool"] = pool

    # тест (потом уберём)
    await pool.execute("select 1;")
    print("PG: OK")

    # === ВАЖНО: прокидываем pool в payments ===
    payments.set_pg_pool(pool)

    # --- middlewares ---
    dp.message.middleware(UserTrackingMiddleware())
    dp.callback_query.middleware(UserTrackingMiddleware())

    # --- routers ---
    dp.include_router(start_router)
    dp.include_router(catalog_router)
    dp.include_router(payments.router)
    dp.include_router(info.router)

    # --- run ---
    try:
        await asyncio.gather(
            dp.start_polling(bot),
            crypto_pay.start_polling(),
            # === ВАЖНО: передаём pool в webhook ===
            start_platega_webhook_server(
                bot,
                pg_pool=pool,
                host="0.0.0.0",
                port=8080,
            ),
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
