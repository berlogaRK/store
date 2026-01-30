import json
from aiohttp import web

from bot.payments.platega_orders import PlategaOrders
from bot.services.platega_pay import platega_pay
from bot.handlers.payments import _finalize_purchase  # можно так, круговой импорт не возникнет, если payments НЕ импортирует webhook

orders = PlategaOrders()

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
        st = await platega_pay.get_transaction(tx_id)
    except Exception:
        # лучше 503 чтобы Platega ретраила (если у них есть ретраи)
        return web.json_response({"ok": False, "error": "status fetch failed"}, status=503)

    status = (st.get("status") or "").upper()
    if status != "CONFIRMED":
        return web.json_response({})  # ACK

    # 3) достаём мету из нашего стораджа (идемпотентность через pop)
    meta = orders.pop(tx_id)
    if not meta:
        return web.json_response({})  # уже обработано / неизвестно

    await _finalize_purchase(
        bot=request.app["bot"],
        buyer_id=meta["buyer_id"],
        buyer_username=meta.get("buyer_username"),
        product_id=meta["product_id"],
        amount_asset=str(meta["final_price_rub"]),
        asset="RUB",
        final_price_rub=meta["final_price_rub"],
        promo_code=meta.get("promo_code"),
    )

    return web.json_response({})

async def start_platega_webhook_server(bot, host="0.0.0.0", port=8080):
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/webhooks/platega", platega_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()

    # держим сервер живым
    while True:
        await web.asyncio.sleep(3600)
