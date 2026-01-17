from pathlib import Path
from bot.users.storage import JsonUserStorage
from bot.users.service import UserService

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

user_storage = JsonUserStorage(str(DATA_DIR / "users.json"))
user_service = UserService(user_storage)
