import asyncio
import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import Any, Optional

from bot.promos.model import PromoCode, PromoType


def _parse_dt(value: Any) -> Optional[datetime]:
    if value in (None, "", 0):
        return None
    # ISO-строка
    return datetime.fromisoformat(value)


class JsonPromoStorage:
    def __init__(self, promos_path: str, usage_path: str):
        self.promos_path = promos_path
        self.usage_path = usage_path
        self._lock = asyncio.Lock()

    def _read_json(self, path: str) -> dict:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}


    def _atomic_write_json(self, path: str, data: dict) -> None:
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    async def get_promo(self, code: str) -> Optional[PromoCode]:
        code = code.strip().upper()
        async with self._lock:
            all_promos = self._read_json(self.promos_path)

        raw = all_promos.get(code)

        if not raw:
            return None

        return PromoCode(
            code=code,
            type=PromoType(raw["type"]),
            value=int(raw["value"]),
            active=bool(raw.get("active", True)),
            expires_at=_parse_dt(raw.get("expires_at")),
            max_uses=raw.get("max_uses"),
            per_user_limit=raw.get("per_user_limit"),
            allowed_products=raw.get("allowed_products"),
        )

    async def get_usage(self, code: str) -> dict:
        code = code.strip().upper()
        async with self._lock:
            usage = self._read_json(self.usage_path)
            return usage.get(code, {"total_uses": 0, "users": {}})

    async def increment_usage(self, code: str, user_id: int) -> None:
        code = code.strip().upper()
        uid = str(user_id)

        async with self._lock:
            usage = self._read_json(self.usage_path)
            entry = usage.get(code, {"total_uses": 0, "users": {}})
            entry["total_uses"] = int(entry.get("total_uses", 0)) + 1
            entry["users"][uid] = int(entry["users"].get(uid, 0)) + 1
            usage[code] = entry
            self._atomic_write_json(self.usage_path, usage)
