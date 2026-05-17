import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
SUPER_ADMIN_ID: int = int(os.getenv("SUPER_ADMIN_ID", "0"))

# Master info (configurable via env vars — no hardcoding)
MASTER_BIO: str = os.getenv("MASTER_BIO", "")
MASTER_ADDRESS: str = os.getenv("MASTER_ADDRESS", "")
MASTER_MAPS_YANDEX: str = os.getenv("MASTER_MAPS_YANDEX", "")
MASTER_MAPS_2GIS: str = os.getenv("MASTER_MAPS_2GIS", "")
MASTER_LAT: str = os.getenv("MASTER_LAT", "")
MASTER_LON: str = os.getenv("MASTER_LON", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env")
if not SUPER_ADMIN_ID:
    raise ValueError("SUPER_ADMIN_ID is not set in .env")
