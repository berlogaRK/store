import asyncio
from aiogram import Bot, Dispatcher

from bot.config import load_config
from bot.handlers.start import router as start_router
from bot.handlers.catalog import router as catalog_router
from bot.services.crypto_pay import crypto_pay
from bot.handlers import payments

from bot.middlewares.users import UserTrackingMiddleware

async def main():
    cfg = load_config()
    bot = Bot(token=cfg.token)
    dp = Dispatcher()

    dp.message.middleware(UserTrackingMiddleware())
    dp.callback_query.middleware(UserTrackingMiddleware())

    dp.include_router(start_router)
    dp.include_router(catalog_router)
    dp.include_router(payments.router)

    await asyncio.gather(
        dp.start_polling(bot),
        crypto_pay.start_polling(),
    )
if __name__ == "__main__":
    asyncio.run(main())