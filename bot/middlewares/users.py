from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any

from bot.users import user_service


class UserTrackingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable,
        event: TelegramObject,
        data: Dict[str, Any]
    ):
        user = data.get("event_from_user")
        if user:
            # Обычно dp.workflow_data попадает в data, так что db_pool часто уже тут.
            pool = data.get("db_pool")

            # на всякий случай (если вдруг не прокинулось)
            if pool is None:
                dp = data.get("dispatcher")
                if dp is not None:
                    try:
                        pool = dp["db_pool"]
                    except Exception:
                        pool = None

            await user_service.track(user, pool=pool)

        return await handler(event, data)
