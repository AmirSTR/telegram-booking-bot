import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from db.database import init_db
from handlers import super_admin_router, master_router, client_router
from utils.reminders import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    await init_db()
    logger.info("Database initialized")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers in priority order:
    # super_admin first (handles /admin command)
    # master next (handles /start for masters)
    # client last (handles /start with deep link)
    dp.include_router(super_admin_router)
    dp.include_router(master_router)
    dp.include_router(client_router)

    # Start reminder scheduler
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Reminder scheduler started")

    logger.info("Bot started")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
