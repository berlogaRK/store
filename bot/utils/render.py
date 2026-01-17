from aiogram.types import Message, FSInputFile, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest

async def show_photo(message: Message, photo_path: str, caption: str, reply_markup):
    """Пытаемся редактировать (если возможно), иначе отправляем новое."""
    photo = FSInputFile(photo_path)
    try:
        if message.photo:
            media = InputMediaPhoto(media=photo, caption=caption, parse_mode="Markdown")
            await message.edit_media(media=media, reply_markup=reply_markup)
        else:
            await message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup, parse_mode="Markdown")
    except TelegramBadRequest:
        await message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup, parse_mode="Markdown")

async def show_text(message: Message, text: str, reply_markup):
    """Если текущий месседж фото — правим caption, иначе text."""
    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await message.edit_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    except TelegramBadRequest:
        await message.answer(text=text, reply_markup=reply_markup, parse_mode="Markdown")