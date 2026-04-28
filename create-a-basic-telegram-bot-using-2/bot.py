import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from database.db import init_db
from handlers.admin import router as admin_router
from handlers.booking import router as booking_router
from handlers.menu import router as menu_router
from handlers.start import router as start_router
from scheduler.reminders import setup_reminder_scheduler


async def main() -> None:
    load_dotenv()
    init_db()
    token = os.getenv("BOT_TOKEN")

    if not token:
        raise ValueError("BOT_TOKEN not found. Add it to the .env file.")

    bot = Bot(token=token)
    scheduler = setup_reminder_scheduler(bot)
    dp = Dispatcher()
    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(booking_router)
    dp.include_router(menu_router)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
