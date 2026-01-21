import json
import os
from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class PendingPlategaOrder:
    buyer_id: int
    buyer_username: str | None
    product_id: str
    promo_code: str | None
    final_price_rub: int
    created_at: str  # ISO string

class PlategaOrders:
    def __init__(self, path: str = "data/platega_orders.json"):
        self.path = path

    def _load(self) -> dict[str, Any]:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def _save(self, data: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def put(self, transaction_id: str, order: PendingPlategaOrder) -> None:
        data = self._load()
        data[transaction_id] = asdict(order)
        self._save(data)

    def pop(self, transaction_id: str) -> dict[str, Any] | None:
        data = self._load()
        item = data.pop(transaction_id, None)
        self._save(data)
        return item

    def get(self, transaction_id: str) -> dict[str, Any] | None:
        return self._load().get(transaction_id)
