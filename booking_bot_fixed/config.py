import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
SUPER_ADMIN_ID: int = int(os.getenv("SUPER_ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env")
if not SUPER_ADMIN_ID:
    raise ValueError("SUPER_ADMIN_ID is not set in .env")
