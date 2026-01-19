from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.keyboards.callbacks import NavCb
from bot.keyboards.inline import info_kb
from bot.utils.media import INFO_IMAGE
from bot.utils.render import show_photo

router = Router()


@router.callback_query(NavCb.filter(F.page == "info"))
async def info_page(cq: CallbackQuery):
    await cq.answer()

    await show_photo(
        message=cq.message,
        photo_path=INFO_IMAGE,
        caption="",
        reply_markup=info_kb(),
    )
