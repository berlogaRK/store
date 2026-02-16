from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from bot.keyboards.callbacks import NavCb, PromoCb, PayGroupCb, BackCb, BonusCb
from bot.keyboards.inline import home_kb, catalog_kb, category_products_kb, chatgpt_plans_kb, profile_kb, profile_kb
from bot.keyboards.payments import payment_groups_kb, crypto_methods_kb
from bot.utils.text import home_text, catalog_text, product_text, profile_text
from bot.utils.media import START_IMAGE, CATALOG_IMAGE, PROFILE_IMAGE
from bot.utils.render import show_photo, show_text
from bot.data.products import get_category, get_products_by_category, get_product
from bot.users import user_service

from bot.promos.state import USER_PROMO, AWAITING_PROMO_FOR_PRODUCT, PromoState
from bot.promos import promo_service

import copy
from dataclasses import replace
from bot.bonuses.state import BONUS_USE
from bot.utils.text import profile_text

router = Router()


def _product_back_target(product_id: str) -> tuple[str, str | None]:
    """Куда вести 'Назад' из карточки товара/оплаты.

    Правила:
    - ChatGPT (категория gpt) -> catalog (планов больше нет)
    - Остальные:
        - если в категории 1 товар -> catalog
        - иначе -> category (payload=category_id)
    """
    product = get_product(product_id)
    if not product:
        return ("catalog", None)

    # ✅ ВАЖНО: раньше здесь было chatgpt_plans, из-за этого и вылетало в планы.
    if product.category_id == "gpt":
        return ("catalog", None)

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
        # экран не нужен, но оставим безопасно
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

@router.callback_query(NavCb.filter(F.page == "profile"))
async def go_profile(cq: CallbackQuery):
    await cq.answer()

    pool = getattr(cq.bot, "db_pool", None)
    profile = await user_service.get_profile(cq.from_user.id, pool=pool)
    invited_count = await user_service.count_invited(cq.from_user.id, pool=pool)

    ref_id = profile.get("ref")
    bonus_balance = int(profile.get("bonus_balance", 0) or 0)

    await show_photo(
        message=cq.message,
        photo_path=PROFILE_IMAGE,
        caption=profile_text(
            user_id=cq.from_user.id,
            username=cq.from_user.username,
            first_name=cq.from_user.first_name,
            ref_id=ref_id,
            invited_count=invited_count,
            bonus_balance=bonus_balance
        ),
        reply_markup=profile_kb(),
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
    # На всякий случай: экран есть, но Plus там уже не будет (см. inline.py)
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

    # --- бонусы пользователя (баланс + применённые к этому товару) ---
    pool = getattr(cq.bot, "db_pool", None)
    profile = await user_service.get_profile(cq.from_user.id, pool=pool)
    bonus_balance = int(profile.get("bonus_balance", 0) or 0)

    bonus_applied = BONUS_USE.get(cq.from_user.id, {}).get(product.id, 0)
    bonus_applied = min(int(bonus_applied), bonus_balance, int(product.price_rub))
    price_after_bonus = max(int(product.price_rub) - bonus_applied, 0)

    # --- промокод  ---
    state = USER_PROMO.get(cq.from_user.id)
    has_promo = bool(state and state.product_id == product.id and state.promo_code)

    if has_promo and state.final_price_rub is not None and state.discount_rub is not None:
        price_text = f"{state.final_price_rub} ₽ (скидка {state.discount_rub} ₽, промокод {state.promo_code})"
        if bonus_applied > 0:
            price_text += f", бонусы -{bonus_applied} ₽"
    else:
        if bonus_applied > 0:
            price_text = f"{price_after_bonus} ₽ (бонусы -{bonus_applied} ₽)"
        else:
            price_text = f"{product.price_rub} ₽"

    text = product_text(product.title, product.description, price_text)

    back_page, back_payload = _product_back_target(product.id)

    kb = payment_groups_kb(
        product.id,
        has_promo=has_promo,
        back_page=back_page,
        back_payload=back_payload,
        bonus_balance=bonus_balance,
        bonus_applied=bonus_applied,
    )

    if getattr(product, "image_path", None):
        await show_photo(
            message=cq.message,
            photo_path=product.image_path,
            caption=text,
            reply_markup=kb,
            allow_answer=False,
        )
    else:
        await show_text(
            message=cq.message,
            text=text,
            reply_markup=kb,
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
    
    bonus_applied = BONUS_USE.get(user_id, {}).get(product.id, 0)
    bonus_applied = min(int(bonus_applied), int(product.price_rub))
    price_after_bonus = max(int(product.price_rub) - bonus_applied, 0)

    product_for_promo = replace(product, price_rub=price_after_bonus)


    try:
        result = await promo_service.apply(text, user_id, product_for_promo)
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

    pid = callback_data.payload
    if not pid:
        return

    # промо-стейт
    state = USER_PROMO.get(cq.from_user.id)
    has_promo = bool(state and state.product_id == pid and state.promo_code)

    back_page, back_payload = _product_back_target(pid)

    # --- бонусы: баланс + применённые к этому товару ---
    pool = getattr(cq.bot, "db_pool", None)
    profile = await user_service.get_profile(cq.from_user.id, pool=pool)
    bonus_balance = int(profile.get("bonus_balance", 0) or 0)

    # сколько пользователь выбрал применить (в рублях)
    bonus_applied = BONUS_USE.get(cq.from_user.id, {}).get(pid, 0)
    bonus_applied = int(bonus_applied or 0)

    product = get_product(pid)
    max_by_price = int(product.price_rub) if product else 0

    bonus_applied = min(bonus_applied, bonus_balance, max_by_price)
    if bonus_applied > 0:
        BONUS_USE.setdefault(cq.from_user.id, {})[pid] = bonus_applied
    else:
        try:
            BONUS_USE.get(cq.from_user.id, {}).pop(pid, None)
        except Exception:
            pass

    await cq.message.edit_reply_markup(
        reply_markup=payment_groups_kb(
            pid,
            has_promo=has_promo,
            back_page=back_page,
            back_payload=back_payload,
            bonus_balance=bonus_balance,
            bonus_applied=bonus_applied,
        )
    )

@router.callback_query(NavCb.filter(F.page == "ref_link"))
async def ref_link(cq: CallbackQuery):
    await cq.answer()

    me = await cq.bot.get_me()
    ref_url = f"https://t.me/{me.username}?start=ref_{cq.from_user.id}"

    await cq.message.answer(
        f"🔗 Ваша ссылка для друга:\n\n{ref_url}\n\n"
        "Если друг ещё не совершал покупки — вы закрепитесь как пригласивший, от чего вам будут начислятся бонусы в размере 10% от покупок всех приглашенных вами друзей!"
    )

@router.callback_query(BonusCb.filter(F.action == "use"))
async def bonus_use(cq: CallbackQuery, callback_data: BonusCb):
    await cq.answer()

    pid = callback_data.product_id
    product = get_product(pid)
    if not product:
        return

    pool = getattr(cq.bot, "db_pool", None)
    profile = await user_service.get_profile(cq.from_user.id, pool=pool)
    bonus_balance = int(profile.get("bonus_balance", 0) or 0)

    amount = min(bonus_balance, int(product.price_rub))
    BONUS_USE.setdefault(cq.from_user.id, {})[pid] = amount

    st = USER_PROMO.get(cq.from_user.id)
    if st and st.product_id == pid:
        USER_PROMO.pop(cq.from_user.id, None)

    await go_product(cq, NavCb(page="product", payload=pid))


@router.callback_query(BonusCb.filter(F.action == "clear"))
async def bonus_clear(cq: CallbackQuery, callback_data: BonusCb):
    await cq.answer()

    pid = callback_data.product_id
    BONUS_USE.get(cq.from_user.id, {}).pop(pid, None)

    st = USER_PROMO.get(cq.from_user.id)
    if st and st.product_id == pid:
        USER_PROMO.pop(cq.from_user.id, None)

    await go_product(cq, NavCb(page="product", payload=pid))
