from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from bot.keyboards.callbacks import NavCb, PromoCb
from bot.keyboards.inline import home_kb, catalog_kb, only_home_kb
from bot.keyboards.payments import payment_methods_kb
from bot.utils.text import home_text, catalog_text, product_text
from bot.utils.media import START_IMAGE, CATALOG_IMAGE
from bot.utils.render import show_photo, show_text
from bot.data.products import get_product

from bot.promos.state import USER_PROMO, AWAITING_PROMO_FOR_PRODUCT, PromoState
from bot.promos import promo_service


router = Router()


@router.callback_query(NavCb.filter(F.page == "home"))
async def go_home(cq: CallbackQuery):
    await cq.answer()
    await show_photo(
        message=cq.message,
        photo_path=START_IMAGE,
        caption=home_text(),
        reply_markup=home_kb(),
    )


@router.callback_query(NavCb.filter(F.page == "catalog"))
async def go_catalog(cq: CallbackQuery):
    await cq.answer()
    await show_photo(
        message=cq.message,
        photo_path=CATALOG_IMAGE,
        caption=catalog_text(),
        reply_markup=catalog_kb(),
    )


@router.callback_query(NavCb.filter(F.page == "product"))
async def go_product(cq: CallbackQuery, callback_data: NavCb):
    await cq.answer()

    pid = callback_data.payload
    product = get_product(pid) if pid else None
    if not product:
        await show_text(cq.message, "❌ Товар не найден", home_kb())
        return

    state = USER_PROMO.get(cq.from_user.id)
    has_promo = bool(state and state.product_id == product.id and state.promo_code)

    if has_promo and state.final_price_rub is not None and state.discount_rub is not None:
        price_text = f"{state.final_price_rub} ₽ (скидка {state.discount_rub} ₽, промокод {state.promo_code})"
    else:
        price_text = f"{product.price_rub} ₽"

    text = product_text(
        product.title,
        product.description,
        price_text,
    )


    # ВАЖНО: если у товара есть картинка — меняем media (иначе останется фото каталога)
    if getattr(product, "image_path", None):
        await show_photo(
            message=cq.message,
            photo_path=product.image_path,
            caption=text,
            reply_markup=payment_methods_kb(product.id, has_promo=has_promo),
        )
    else:
        # Если у товара нет картинки — просто показываем текст (фото не сменится)
        await show_text(
            message=cq.message,
            text=text,
            reply_markup=payment_methods_kb(product.id, has_promo=has_promo),
        )

@router.callback_query(PromoCb.filter(F.action == "enter"))
async def promo_enter(cq: CallbackQuery, callback_data: PromoCb):
    await cq.answer()
    pid = callback_data.product_id

    AWAITING_PROMO_FOR_PRODUCT[cq.from_user.id] = pid

    await cq.message.answer(
        "🏷 Введите промокод сообщением.\n\n"
        "Чтобы отменить — отправьте /cancel"
    )

@router.message(F.text)
async def promo_input(message: Message):
    user_id = message.from_user.id

    # если мы не ждём промокод — выходим, не мешаем остальным хендлерам
    pid = AWAITING_PROMO_FOR_PRODUCT.get(user_id)
    if not pid:
        return

    text = (message.text or "").strip()

    # отмена
    if text.lower() in ("/cancel", "cancel", "отмена"):
        AWAITING_PROMO_FOR_PRODUCT.pop(user_id, None)
        await message.answer("Ок, ввод промокода отменён.")
        return

    # не ловим команды
    if text.startswith("/"):
        return

    product = get_product(pid)
    if not product:
        AWAITING_PROMO_FOR_PRODUCT.pop(user_id, None)
        await message.answer("❌ Товар не найден. Откройте карточку товара заново.")
        return

    try:
        result = await promo_service.apply(text, user_id, product)
    except Exception as e:
        AWAITING_PROMO_FOR_PRODUCT.pop(user_id, None)  # ← ВАЖНО
        await message.answer(f"❌ Не удалось применить промокод: {e}")
        return


    USER_PROMO[user_id] = PromoState(
        product_id=product.id,
        promo_code=result.code,
        final_price_rub=result.final_price_rub,
        discount_rub=result.discount_rub,
    )

    await message.answer(
        f"✅ Промокод применён!\n"
        f"{result.description}\n"
        f"Итоговая цена: {result.final_price_rub} ₽\n\n"
        f"_(Откройте карточку товара по новой или введите /start)_",
        parse_mode="Markdown"
    )

@router.callback_query(PromoCb.filter(F.action == "clear"))
async def promo_clear(cq: CallbackQuery, callback_data: PromoCb):
    await cq.answer()
    user_id = cq.from_user.id
    pid = callback_data.product_id

    st = USER_PROMO.get(user_id)
    if st and st.product_id == pid:
        USER_PROMO.pop(user_id, None)

    await cq.message.answer("✅ Промокод удалён. Цена вернулась к обычной.")
