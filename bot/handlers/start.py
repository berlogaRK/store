from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.types import CallbackQuery

from bot.utils.media import START_IMAGE
from bot.utils.text import home_text
from bot.utils.render import show_photo
from bot.keyboards.inline import home_kb
from bot.keyboards.callbacks import NewPurchaseCb

router = Router()


async def show_start(message: Message):
    await show_photo(
        message=message,
        photo_path=START_IMAGE,
        caption=home_text(),
        reply_markup=home_kb(),
    )

@router.message(CommandStart())
async def start_cmd(message: Message):
    await show_start(message)


@router.callback_query(NewPurchaseCb.filter()) #новая покупка
async def new_purchase(cq: CallbackQuery):
    await cq.answer()
    await show_start(cq.message)