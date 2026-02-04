import os
import asyncio

from aiogram import Bot, Dispatcher

from bot.config import load_config, APP_ENV, IS_PROD, PAYMENTS_ENABLED
from bot.handlers.start import router as start_router
from bot.handlers.catalog import router as catalog_router
from bot.handlers import payments, info

from bot.middlewares.users import UserTrackingMiddleware

from bot.services.crypto_pay import crypto_pay
from bot.webhooks.platega_webhook import start_platega_webhook_server

from bot.db.pool import PgConfig, create_pool

from bot.promos import set_pg_pool as set_promos_pg_pool


async def main():
    cfg = load_config()

    bot = Bot(token=cfg.token)
    dp = Dispatcher()

    pool = None

    # --- PostgreSQL pool (только в PROD) ---
    if IS_PROD:
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

        # тест соединения (потом уберём)
        await pool.execute("select 1;")
        print("PG: OK")

        # прокидываем pool в сервисы
        payments.set_pg_pool(pool)
        set_promos_pg_pool(pool)
    else:
        print(f"APP_ENV={APP_ENV} → DB отключена (работаем на JSON), платежи: {'ON' if PAYMENTS_ENABLED else 'OFF'}")

    # --- middlewares ---
    dp.message.middleware(UserTrackingMiddleware())
    dp.callback_query.middleware(UserTrackingMiddleware())

    # --- routers ---
    dp.include_router(start_router)
    dp.include_router(catalog_router)
    dp.include_router(payments.router)
    dp.include_router(info.router)

    try:
        # Платежные фоновые задачи — только в PROD и только если платежи включены.
        if IS_PROD and PAYMENTS_ENABLED:
            asyncio.create_task(crypto_pay.start_polling())
            asyncio.create_task(
                start_platega_webhook_server(
                    bot,
                    pg_pool=pool,
                    host="0.0.0.0",
                    port=8080,
                )
            )

                # --- устойчивый polling (переживает дисконнекты Telegram) ---
        while True:
            try:
                await dp.start_polling(bot)
            except (asyncio.CancelledError, KeyboardInterrupt):
                # корректное завершение приложения
                raise
            except Exception as e:
                # любые временные сетевые ошибки (ServerDisconnectedError и т.п.)
                print(f"[polling] error: {type(e).__name__}: {e}")
                await asyncio.sleep(2)


    finally:
        if pool is not None:
            await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
