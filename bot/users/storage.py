import json
import os
import asyncio
from datetime import datetime
from typing import Dict


class JsonUserStorage:
    def __init__(self, path: str):
        self.path = path
        self._lock = asyncio.Lock()

    def _read(self) -> Dict:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def _write(self, data: Dict) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    async def upsert_user(self, user) -> None:
        now = datetime.utcnow().isoformat()

        async with self._lock:
            data = self._read()
            uid = str(user.id)

            if uid not in data:
                data[uid] = {
                    "id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "first_seen": now,
                    "last_seen": now,
                    "total_purchases": 0,
                    "total_spent_rub": 0,
                    "ref": None,
                }
            else:
                data[uid]["username"] = user.username
                data[uid]["first_name"] = user.first_name
                data[uid]["last_name"] = user.last_name
                data[uid]["last_seen"] = now

            self._write(data)

    async def add_purchase(self, user_id: int, amount_rub: int) -> None:
        async with self._lock:
            data = self._read()
            uid = str(user_id)

            if uid not in data:
                data[uid] = {
                    "id": user_id,
                    "username": None,
                    "first_name": None,
                    "last_name": None,
                    "first_seen": None,
                    "last_seen": None,
                    "total_purchases": 0,
                    "total_spent_rub": 0,
                    "ref": None,
                }

            data[uid]["total_purchases"] = int(
                data[uid].get("total_purchases", 0)
            ) + 1

            data[uid]["total_spent_rub"] = int(
                data[uid].get("total_spent_rub", 0)
            ) + int(amount_rub)

            self._write(data)

    async def try_set_ref(self, user_id: int, ref_id: int) -> bool:
        if user_id == ref_id:
            return False

        async with self._lock:
            data = self._read()
            uid = str(user_id)
            rid = int(ref_id)

            if uid not in data:
                data[uid] = {
                    "id": user_id,
                    "username": None,
                    "first_name": None,
                    "last_name": None,
                    "first_seen": None,
                    "last_seen": None,
                    "total_purchases": 0,
                    "total_spent_rub": 0,
                    "ref": None,
                }

            # уже есть реферер
            if data[uid].get("ref") is not None:
                return False

            # уже покупал
            if int(data[uid].get("total_spent_rub", 0)) > 0:
                return False

            data[uid]["ref"] = rid
            self._write(data)
            return True

    async def count_invited(self, ref_id: int) -> int:
        async with self._lock:
            data = self._read()
            return sum(1 for u in data.values() if u.get("ref") == ref_id)

    async def get_profile(self, user_id: int) -> dict:
        async with self._lock:
            data = self._read()
            uid = str(user_id)
            return data.get(uid, {})
