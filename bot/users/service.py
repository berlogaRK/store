from bot.users.storage import JsonUserStorage


class UserService:
    def __init__(self, storage: JsonUserStorage):
        self.storage = storage

    async def track(self, user) -> None:
        await self.storage.upsert_user(user)

    async def add_purchase(self, user_id: int, amount_rub: int) -> None:
        await self.storage.add_purchase(user_id, amount_rub)
