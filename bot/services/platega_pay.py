import aiohttp
from typing import Any, Dict, Optional

from bot.config import load_config

cfg = load_config()


class PlategaClient:
    """
    Platega API:
    - POST /transaction/process
    - GET  /transaction/{id}
    Base URL: https://app.platega.io/  
    """

    BASE_URL = "https://app.platega.io"

    def __init__(self, merchant_id: str, secret: str):
        self.merchant_id = merchant_id
        self.secret = secret
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    def _headers(self) -> Dict[str, str]:
        return {
            "X-MerchantId": self.merchant_id,
            "X-Secret": self.secret,
            "Content-Type": "application/json",
        }

    async def create_sbp_payment(
        self,
        amount_rub: int,
        description: str,
        payload: str,
        return_url: str,
        failed_url: str,
        payment_method: int = 2,
    ) -> Dict[str, Any]:
        s = await self._get_session()
        url = f"{self.BASE_URL}/transaction/process"
        body = {
            "paymentMethod": payment_method,
            "paymentDetails": {"amount": int(amount_rub), "currency": "RUB"},
            "description": description,
            "return": return_url,
            "failedUrl": failed_url,
            "payload": payload,
        }

        async with s.post(url, headers=self._headers(), json=body) as r:
            data = await r.json(content_type=None)
            if r.status >= 400:
                raise RuntimeError(f"Platega create error {r.status}: {data}")
            return data  # transactionId, redirect, status, expiresIn... 

    async def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        s = await self._get_session()
        url = f"{self.BASE_URL}/transaction/{transaction_id}"
        async with s.get(url, headers=self._headers()) as r:
            data = await r.json(content_type=None)
            if r.status >= 400:
                raise RuntimeError(f"Platega status error {r.status}: {data}")
            return data  # status, qr, paymentDetails... 


platega_pay = PlategaClient(cfg.platega_merchant_id, cfg.platega_secret)
