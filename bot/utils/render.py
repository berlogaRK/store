from aiogram.types import Message, FSInputFile, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest


async def show_photo(
    message: Message,
    photo_path: str,
    caption: str,
    reply_markup,
    *,
    allow_answer: bool = True,
):
    """Фото-экран.

    - Навигация (callbacks): allow_answer=False → не плодим сообщения.
    - /start: allow_answer=True → отправляем первое сообщение.
    """
    photo = FSInputFile(photo_path)

    try:
        if message.photo:
            media = InputMediaPhoto(media=photo, caption=caption, parse_mode="Markdown")
            await message.edit_media(media=media, reply_markup=reply_markup)
            return
    except TelegramBadRequest:
        pass

    if allow_answer:
        await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )


async def show_text(
    message: Message,
    text: str,
    reply_markup,
    *,
    allow_answer: bool = True,
):
    """Текст/Caption.

    - Навигация (callbacks): allow_answer=False → не плодим сообщения.
    - /start/сообщения: allow_answer=True.
    """
    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await message.edit_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
        return
    except TelegramBadRequest:
        if allow_answer:
            await message.answer(text=text, reply_markup=reply_markup, parse_mode="Markdown")
