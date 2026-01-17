from aiogram import Bot
from bot.config import MANAGERS


async def notify_managers(bot: Bot, text: str):
    for manager_id in MANAGERS:
        try:
            await bot.send_message(manager_id, text, parse_mode="Markdown", disable_web_page_preview=True,)
        except Exception as e:
            print(f"Failed to notify manager {manager_id}: {e}")
