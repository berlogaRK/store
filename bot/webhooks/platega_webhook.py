from __future__ import annotations

import asyncio
import uuid
from aiohttp import web


async def _try_mark_paid(pg_pool, tx_id: str) -> bool:
    """
    Idempotency guard:
    - True  -> мы ПЕРВЫЕ перевели статус в 'paid' (можно финализировать)
    - False -> уже было paid (или не нашли платёж) => финализировать НЕЛЬЗЯ
    """
    if not pg_pool:
        return False

    try:
        order_id = uuid.UUID(str(tx_id))
    except Exception:
        return False

    # Атомарно: выставляем paid только если ещё не paid
    try:
        row = await pg_pool.fetchrow(
            """
            update payments
               set status = 'paid'
             where order_id = $1
               and status <> 'paid'
         returning status
            """,
            order_id,
        )
    except Exception:
        return False

    # row есть только если обновление произошло (то есть НЕ было paid)
    return row is not None


async def _fetch_meta_from_pg(pg_pool, tx_id: str) -> dict | None:
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
             where order_id = $1
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


async def _process_platega_tx(app: web.Application, tx_id: str) -> None:
    """
    Фоновая обработка:
    - ретраи на запрос статуса
    - финализация только если CONFIRMED
    - анти-дубликат через атомарный UPDATE ... WHERE status <> 'paid'
    """
    pg_pool = app.get("pg_pool")
    bot = app["bot"]

    # 1) получаем статус с ретраями
    st = None
    for _ in range(10):  # ~30 секунд
        try:
            from bot.services.platega_pay import platega_pay
            st = await platega_pay.get_transaction(tx_id)
            break
        except Exception:
            await asyncio.sleep(3)

    if not st:
        # не смогли получить статус — просто выходим (webhook уже ACK'нули 200)
        return

    status = (st.get("status") or "").upper()
    if status != "CONFIRMED":
        return

    # 2) Анти-дубликат: только первый CONFIRMED переводит в paid и финализирует
    can_finalize = await _try_mark_paid(pg_pool, tx_id)
    if not can_finalize:
        return

    # 3) Достаём мету из PG
    meta = await _fetch_meta_from_pg(pg_pool, tx_id)
    if not meta:
        return

    # 4) Финализируем покупку (уведомления/тикет/промокод)
    from bot.handlers.payments import _finalize_purchase  # lazy import
    await _finalize_purchase(
        bot=bot,
        ticket_id=meta.get("ticket_id"),
        buyer_id=meta["buyer_id"],
        buyer_username=meta.get("buyer_username"),
        product_id=meta["product_id"],
        amount_asset=str(meta.get("final_price_rub") or 0),
        asset="RUB",
        final_price_rub=meta.get("final_price_rub"),
        promo_code=meta.get("promo_code"),
    )


async def platega_webhook(request: web.Request) -> web.Response:
    # ✅ всегда ACK 200, чтобы Platega не считала доставку "failed"
    # даже если тело неожиданное
    try:
        raw = await request.read()
    except Exception:
        raw = b""

    data = {}
    try:
        # пробуем JSON
        if raw:
            import json
            data = json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception:
        data = {}

    # пытаемся вытащить tx_id максимально широко
    tx_id = None

    # 1) стандартный формат: {"transaction": {"id": "..."}}
    tx = data.get("transaction") if isinstance(data, dict) else None
    if isinstance(tx, dict):
        tx_id = tx.get("id") or tx.get("transactionId")

    # 2) иногда transactionId приходит на верхнем уровне
    if not tx_id and isinstance(data, dict):
        tx_id = data.get("transactionId") or data.get("id")

    # 3) если вообще ничего не нашли — всё равно 200, просто не обрабатываем
    if tx_id:
        asyncio.create_task(_process_platega_tx(request.app, str(tx_id)))

    return web.json_response({})  # 200


async def start_platega_webhook_server(
    bot,
    pg_pool=None,
    host="0.0.0.0",
    port=8080,
):
    app = web.Application()
    app["bot"] = bot
    app["pg_pool"] = pg_pool

    # и со слэшем, и без
    app.router.add_post("/webhooks/platega", platega_webhook)
    app.router.add_post("/webhooks/platega/", platega_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()

    while True:
        await asyncio.sleep(3600)
