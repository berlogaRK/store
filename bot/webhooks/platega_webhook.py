from __future__ import annotations

import asyncio
import json
import uuid
from aiohttp import web

from bot.payments.platega_orders import PlategaOrders
from bot.handlers.payments import _finalize_purchase  # payments НЕ импортирует webhook → кругового импорта не будет

orders = PlategaOrders()


async def _mark_paid_in_pg(pg_pool, tx_id: str) -> None:
    """Пытаемся отметить платеж как paid в PostgreSQL (если pg_pool передан)."""
    if not pg_pool:
        return
    try:
        order_id = uuid.UUID(str(tx_id))
    except Exception:
        return

    try:
        await pg_pool.execute(
            "update payments set status='paid' where order_id=$1",
            order_id,
        )
    except Exception:
        # не валим webhook из‑за БД — мягкая деградация
        return


async def _fetch_meta_from_pg(pg_pool, tx_id: str) -> dict | None:
    """Если JSON-меты нет (перезапуск/очистка файлов), пробуем достать мету из таблицы payments."""
    if not pg_pool:
        return None
    try:
        order_id = uuid.UUID(str(tx_id))
    except Exception:
        return None

    try:
        row = await pg_pool.fetchrow(
            """
            select ticket_id, user_id, product_id, promo_code, final_price_rub
            from payments
            where order_id=$1
            """,
            order_id,
        )
    except Exception:
        return None

    if not row:
        return None

    return {
        "ticket_id": row["ticket_id"],
        "buyer_id": row["user_id"],
        "buyer_username": None,
        "product_id": row["product_id"],
        "promo_code": row["promo_code"],
        "final_price_rub": row["final_price_rub"],
    }


async def platega_webhook(request: web.Request) -> web.Response:
    # 1) читаем json
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad json"}, status=400)

    tx = data.get("transaction") or {}
    tx_id = tx.get("id") or tx.get("transactionId")
    if not tx_id:
        return web.json_response({"ok": False, "error": "no tx id"}, status=400)

    # 2) перепроверяем статус через API (не доверяем webhook'у “на слово”)
    try:
        from bot.services.platega_pay import platega_pay  # lazy import
        st = await platega_pay.get_transaction(tx_id)
    except Exception:
        return web.json_response({"ok": False, "error": "status fetch failed"}, status=503)

    status = (st.get("status") or "").upper()
    if status != "CONFIRMED":
        return web.json_response({})  # ACK

    pg_pool = request.app.get("pg_pool")

    # 3) достаём мету (сначала JSON как быстрый путь, потом PG как fallback)
    meta = orders.pop(tx_id)
    if not meta:
        meta = await _fetch_meta_from_pg(pg_pool, tx_id)

    if not meta:
        return web.json_response({})  # уже обработано / неизвестно

    # 4) обновляем статус в PG (если можем)
    await _mark_paid_in_pg(pg_pool, tx_id)

    # 5) финализируем покупку
    await _finalize_purchase(
        bot=request.app["bot"],
        ticket_id=meta.get("ticket_id"),
        buyer_id=meta["buyer_id"],
        buyer_username=meta.get("buyer_username"),
        product_id=meta["product_id"],
        amount_asset=str(meta.get("final_price_rub") or 0),
        asset="RUB",
        final_price_rub=meta.get("final_price_rub"),
        promo_code=meta.get("promo_code"),
    )

    return web.json_response({})


async def start_platega_webhook_server(
    bot,
    pg_pool=None,
    host="0.0.0.0",
    port=8080,
):
    app = web.Application()
    app["bot"] = bot
    app["pg_pool"] = pg_pool

    app.router.add_post("/webhooks/platega", platega_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()

    # держим корутину живой
    while True:
        await asyncio.sleep(3600)
