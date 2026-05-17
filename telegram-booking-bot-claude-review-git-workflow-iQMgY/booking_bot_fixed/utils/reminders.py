import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from db.database import DB_PATH, get_pending_reminders_24h, get_pending_reminders_2h, mark_reminder_sent
from keyboards.keyboards import reminder_confirm_kb
from utils.message_manager import MessageManager
from utils.schedule import format_date_ru

logger = logging.getLogger(__name__)
message_manager = MessageManager(DB_PATH)


async def send_reminders(bot: Bot):
    """Send 24h and 2h reminders for upcoming bookings (UX-6)."""

    # 24-hour reminders
    for booking in await get_pending_reminders_24h():
        addr_line = f"\n📍 Адрес: {booking['master_address']}" if booking["master_address"] else ""
        try:
            await message_manager.send_message(
                bot,
                booking["client_telegram_id"],
                f"⏰ <b>Напоминание!</b>\n\n"
                f"Завтра в <b>{booking['booking_time']}</b> у вас запись:\n"
                f"✂️ {booking['service_name']}\n"
                f"📅 {format_date_ru(booking['booking_date'])}"
                f"{addr_line}\n\n"
                f"Пожалуйста, подтвердите визит:",
                parse_mode="HTML",
                user_id=booking["client_telegram_id"],
                persistent=True,
                reply_markup=reminder_confirm_kb(booking["id"])
            )
            await mark_reminder_sent(booking["id"], "24h")
            logger.info(f"Sent 24h reminder for booking #{booking['id']}")
        except Exception as e:
            logger.error(f"Failed to send 24h reminder for booking #{booking['id']}: {e}")

    # 2-hour reminders
    for booking in await get_pending_reminders_2h():
        addr_line = f"\n📍 Адрес: {booking['master_address']}" if booking["master_address"] else ""
        try:
            await message_manager.send_message(
                bot,
                booking["client_telegram_id"],
                f"🔔 <b>Скоро визит!</b>\n\n"
                f"Через ~2 часа, в <b>{booking['booking_time']}</b>, вас ждёт:\n"
                f"✂️ {booking['service_name']}"
                f"{addr_line}\n\n"
                f"Подтвердите, что придёте:",
                parse_mode="HTML",
                user_id=booking["client_telegram_id"],
                persistent=True,
                reply_markup=reminder_confirm_kb(booking["id"])
            )
            await mark_reminder_sent(booking["id"], "2h")
            logger.info(f"Sent 2h reminder for booking #{booking['id']}")
        except Exception as e:
            logger.error(f"Failed to send 2h reminder for booking #{booking['id']}: {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_reminders,
        trigger="interval",
        minutes=30,
        args=[bot],
        id="reminders"
    )
    return scheduler
