from pathlib import Path
from bot.promos.storage import JsonPromoStorage
from bot.promos.service import PromoService

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

promo_storage = JsonPromoStorage(
    promos_path=str(DATA_DIR / "promos.json"),
    usage_path=str(DATA_DIR / "promo_usage.json"),
)

promo_service = PromoService(promo_storage)
