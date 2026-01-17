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
            await user_service.track(user)

        return await handler(event, data)
