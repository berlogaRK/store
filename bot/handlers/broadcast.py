from __future__ import annotations

import asyncio
from dataclasses import dataclass

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import MANAGERS
from bot.keyboards.callbacks import BroadcastCb
from bot.users import user_service

router = Router()

MANAGER_IDS = set(MANAGERS)

# ~20 сообщений/сек — с запасом от лимита Telegram (30/сек на рассылку)
SEND_DELAY = 0.05
# как часто обновлять прогресс в чате админа
PROGRESS_EVERY = 100


@dataclass
class PendingBroadcast:
    chat_id: int
    message_id: int


# админы, от которых ждём пост (память процесса)
AWAITING_POST: set[int] = set()
# пост, ожидающий подтверждения, по админу
PENDING: dict[int, PendingBroadcast] = {}
# защита от параллельных рассылок
_running = False
# ссылка на фоновую задачу, чтобы её не убрал GC
_task: asyncio.Task | None = None


def _awaiting_post(message: Message) -> bool:
    if message.from_user is None or message.from_user.id not in AWAITING_POST:
        return False
    # команды постом не считаем — пусть обрабатываются обычными хендлерами
    if message.text and message.text.startswith("/"):
        return False
    return True


@router.message(Command("broadcast"), F.from_user.id.in_(MANAGER_IDS))
async def broadcast_cmd(message: Message):
    if _running:
        await message.answer("⏳ Рассылка уже идёт, дождитесь её завершения.")
        return

    PENDING.pop(message.from_user.id, None)
    AWAITING_POST.add(message.from_user.id)
    await message.answer(
        "Пришлите пост для рассылки одним сообщением — "
        "текст, фото или видео с подписью. Уйдёт юзерам как есть.\n\n"
        "Отмена — /cancel"
    )


@router.message(Command("cancel"), F.from_user.id.in_(MANAGER_IDS))
async def broadcast_cancel(message: Message):
    if message.from_user.id not in AWAITING_POST and message.from_user.id not in PENDING:
        # менеджер отменяет не рассылку (например, ввод промокода) —
        # пропускаем к следующим роутерам
        raise SkipHandler
    AWAITING_POST.discard(message.from_user.id)
    PENDING.pop(message.from_user.id, None)
    await message.answer("Рассылка отменена.")


@router.message(_awaiting_post)
async def broadcast_receive_post(message: Message):
    admin_id = message.from_user.id
    AWAITING_POST.discard(admin_id)

    pool = getattr(message.bot, "db_pool", None)
    try:
        ids = await user_service.get_broadcast_ids(pool=pool)
    except Exception as e:
        await message.reply(
            f"❌ Не удалось получить список юзеров из БД: {type(e).__name__}: {e}"
        )
        return

    if not ids:
        await message.reply("В базе нет получателей — рассылать некому.")
        return

    PENDING[admin_id] = PendingBroadcast(
        chat_id=message.chat.id,
        message_id=message.message_id,
    )

    warn = ""
    if message.media_group_id:
        warn = "\n⚠️ Это альбом: в рассылку уйдёт только первое вложение."

    kb = InlineKeyboardBuilder()
    kb.button(
        text=f"✅ Отправить ({len(ids)} чел.)",
        callback_data=BroadcastCb(action="confirm", msg_id=message.message_id).pack(),
    )
    kb.button(
        text="❌ Отмена",
        callback_data=BroadcastCb(action="cancel", msg_id=message.message_id).pack(),
    )
    kb.adjust(1)

    await message.reply(
        f"Пост выше уйдёт {len(ids)} получателям.{warn}\n\nЗапустить рассылку?",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(BroadcastCb.filter(), F.from_user.id.in_(MANAGER_IDS))
async def broadcast_confirm(cq: CallbackQuery, callback_data: BroadcastCb):
    admin_id = cq.from_user.id
    pending = PENDING.get(admin_id)

    if callback_data.action == "cancel":
        PENDING.pop(admin_id, None)
        await cq.answer("Отменено")
        await cq.message.edit_text("Рассылка отменена.")
        return

    if pending is None or pending.message_id != callback_data.msg_id:
        await cq.answer(
            "Этот пост уже неактуален. Начните заново: /broadcast",
            show_alert=True,
        )
        return

    if _running:
        await cq.answer("Рассылка уже идёт", show_alert=True)
        return

    PENDING.pop(admin_id, None)
    await cq.answer()
    status = await cq.message.edit_text("🚀 Рассылка запущена…")
    global _task
    _task = asyncio.create_task(_run_broadcast(cq.message.bot, pending, status))


async def _send_copy(bot: Bot, user_id: int, post: PendingBroadcast) -> None:
    for attempt in (1, 2):
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=post.chat_id,
                message_id=post.message_id,
            )
            return
        except TelegramRetryAfter as e:
            if attempt == 2:
                raise
            await asyncio.sleep(e.retry_after + 1)


async def _run_broadcast(bot: Bot, post: PendingBroadcast, status: Message):
    global _running
    _running = True

    pool = getattr(bot, "db_pool", None)
    sent = 0
    blocked = 0
    failed = 0
    total = 0

    try:
        ids = await user_service.get_broadcast_ids(pool=pool)
        total = len(ids)

        for i, user_id in enumerate(ids, start=1):
            try:
                await _send_copy(bot, user_id, post)
                sent += 1
            except TelegramForbiddenError:
                # юзер заблокировал бота — больше не рассылаем ему
                blocked += 1
                await user_service.mark_blocked(user_id, pool=pool)
            except TelegramBadRequest as e:
                failed += 1
                if "chat not found" in str(e).lower():
                    await user_service.mark_blocked(user_id, pool=pool)
            except Exception as e:
                failed += 1
                print(f"[broadcast] {user_id}: {type(e).__name__}: {e}")

            if i % PROGRESS_EVERY == 0:
                try:
                    await status.edit_text(f"📤 Рассылка: {i}/{total}…")
                except Exception:
                    pass

            await asyncio.sleep(SEND_DELAY)
    finally:
        _running = False

    report = (
        "✅ Рассылка завершена\n\n"
        f"Получателей: {total}\n"
        f"Доставлено: {sent}\n"
        f"Заблокировали бота: {blocked}\n"
        f"Другие ошибки: {failed}"
    )
    try:
        await status.edit_text(report)
    except Exception:
        await bot.send_message(status.chat.id, report)
