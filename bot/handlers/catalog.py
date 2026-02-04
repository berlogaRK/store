from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from bot.keyboards.callbacks import NavCb, PromoCb, PayGroupCb, BackCb
from bot.keyboards.inline import home_kb, catalog_kb, category_products_kb, chatgpt_plans_kb
from bot.keyboards.payments import payment_groups_kb, crypto_methods_kb
from bot.utils.text import home_text, catalog_text, product_text
from bot.utils.media import START_IMAGE, CATALOG_IMAGE
from bot.utils.render import show_photo, show_text
from bot.data.products import get_category, get_products_by_category, get_product

from bot.promos.state import USER_PROMO, AWAITING_PROMO_FOR_PRODUCT, PromoState
from bot.promos import promo_service

router = Router()


def _product_back_target(product_id: str) -> tuple[str, str | None]:
    """Куда вести 'Назад' из карточки товара/оплаты.

    Правила:
    - категория gpt -> chatgpt_plans
    - остальные:
        - если в категории 1 товар -> catalog
        - иначе -> category (payload=category_id)
    """
    product = get_product(product_id)
    if not product:
        return ("catalog", None)

    if product.category_id == "gpt":
        return ("chatgpt_plans", None)

    products_in_cat = get_products_by_category(product.category_id)
    if len(products_in_cat) <= 1:
        return ("catalog", None)

    return ("category", product.category_id)


@router.callback_query(BackCb.filter())
async def back_handler(cq: CallbackQuery, callback_data: BackCb):
    if callback_data.page == "home":
        return await go_home(cq)
    if callback_data.page == "catalog":
        return await go_catalog(cq)
    if callback_data.page == "chatgpt_plans":
        return await go_chatgpt_plans(cq)
    if callback_data.page == "category":
        return await go_category(cq, NavCb(page="category", payload=callback_data.payload))
    if callback_data.page == "product":
        return await go_product(cq, NavCb(page="product", payload=callback_data.payload))
    return await go_home(cq)


@router.callback_query(NavCb.filter(F.page == "home"))
async def go_home(cq: CallbackQuery):
    await cq.answer()
    await show_photo(
        message=cq.message,
        photo_path=START_IMAGE,
        caption=home_text(),
        reply_markup=home_kb(),
        allow_answer=False,
    )


@router.callback_query(NavCb.filter(F.page == "catalog"))
async def go_catalog(cq: CallbackQuery):
    await cq.answer()
    await show_photo(
        message=cq.message,
        photo_path=CATALOG_IMAGE,
        caption=catalog_text(),
        reply_markup=catalog_kb(),
        allow_answer=False,
    )


@router.callback_query(NavCb.filter(F.page == "chatgpt_plans"))
async def go_chatgpt_plans(cq: CallbackQuery):
    await cq.answer()
    await show_text(
        message=cq.message,
        text="",
        reply_markup=chatgpt_plans_kb(),
        allow_answer=False,
    )


@router.callback_query(NavCb.filter(F.page == "product"))
async def go_product(cq: CallbackQuery, callback_data: NavCb):
    await cq.answer()

    pid = callback_data.payload
    product = get_product(pid) if pid else None
    if not product:
        await show_text(cq.message, "❌ Товар не найден", home_kb(), allow_answer=False)
        return

    state = USER_PROMO.get(cq.from_user.id)
    has_promo = bool(state and state.product_id == product.id and state.promo_code)

    if has_promo and state.final_price_rub is not None and state.discount_rub is not None:
        price_text = f"{state.final_price_rub} ₽ (скидка {state.discount_rub} ₽, промокод {state.promo_code})"
    else:
        price_text = f"{product.price_rub} ₽"

    text = product_text(product.title, product.description, price_text)

    back_page, back_payload = _product_back_target(product.id)

    if getattr(product, "image_path", None):
        await show_photo(
            message=cq.message,
            photo_path=product.image_path,
            caption=text,
            reply_markup=payment_groups_kb(
                product.id,
                has_promo=has_promo,
                back_page=back_page,
                back_payload=back_payload,
            ),
            allow_answer=False,
        )
    else:
        await show_text(
            message=cq.message,
            text=text,
            reply_markup=payment_groups_kb(
                product.id,
                has_promo=has_promo,
                back_page=back_page,
                back_payload=back_payload,
            ),
            allow_answer=False,
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

    pid = AWAITING_PROMO_FOR_PRODUCT.get(user_id)
    if not pid:
        return

    text = (message.text or "").strip()

    if text.lower() in ("/cancel", "cancel", "отмена"):
        AWAITING_PROMO_FOR_PRODUCT.pop(user_id, None)
        await message.answer("Ок, ввод промокода отменён.")
        return

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
        AWAITING_PROMO_FOR_PRODUCT.pop(user_id, None)
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


@router.callback_query(NavCb.filter(F.page == "category"))
async def go_category(cq: CallbackQuery, callback_data: NavCb):
    await cq.answer()

    category_id = callback_data.payload
    category = get_category(category_id)

    if not category:
        await show_text(cq.message, "❌ Категория не найдена", home_kb(), allow_answer=False)
        return

    products = get_products_by_category(category_id)

    if len(products) == 1:
        product = products[0]
        await go_product(cq, NavCb(page="product", payload=product.id))
        return

    await show_text(
        message=cq.message,
        text="",
        reply_markup=category_products_kb(category_id),
        allow_answer=False,
    )


@router.callback_query(PayGroupCb.filter(F.group == "crypto"))
async def open_crypto_methods(cq: CallbackQuery, callback_data: PayGroupCb):
    await cq.answer()
    await cq.message.edit_reply_markup(
        reply_markup=crypto_methods_kb(callback_data.product_id)
    )


@router.callback_query(NavCb.filter(F.page == "payment_groups"))
async def back_to_payment_groups(cq: CallbackQuery, callback_data: NavCb):
    await cq.answer()

    state = USER_PROMO.get(cq.from_user.id)
    has_promo = bool(state and state.product_id == callback_data.payload)

    back_page, back_payload = _product_back_target(callback_data.payload)

    await cq.message.edit_reply_markup(
        reply_markup=payment_groups_kb(
            callback_data.payload,
            has_promo=has_promo,
            back_page=back_page,
            back_payload=back_payload,
        )
    )
