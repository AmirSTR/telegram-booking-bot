import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from config import BOT_TOKEN
from db.database import DB_PATH, init_db
from handlers import super_admin_router, master_router, client_router
from utils.reminders import setup_scheduler
from utils.sqlite_storage import SQLiteStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    """Register slash commands visible in the Telegram UI (UX-8)."""
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="book", description="Записаться"),
        BotCommand(command="appointments", description="Мои записи"),
        BotCommand(command="profile", description="Мой профиль"),
        BotCommand(command="cancel", description="Отменить запись"),
    ])


async def main():
    await init_db()
    logger.info("Database initialized")

    bot = Bot(token=BOT_TOKEN)

    # Persistent FSM storage — survives bot restarts (state constraint from spec)
    storage = SQLiteStorage(DB_PATH)
    dp = Dispatcher(storage=storage)

    # Register routers in priority order:
    # super_admin first (handles /admin command)
    # master next (handles master panel callbacks)
    # client last (handles /start with deep link)
    dp.include_router(super_admin_router)
    dp.include_router(master_router)
    dp.include_router(client_router)

    await set_bot_commands(bot)
    logger.info("Bot commands registered")

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
