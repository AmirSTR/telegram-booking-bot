import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from config import TIMEZONE_OFFSET_HOURS
from db.database import get_pending_reminders_24h, get_pending_reminders_2h, mark_reminder_sent
from keyboards.keyboards import reminder_confirm_kb
from utils.schedule import format_date_ru

logger = logging.getLogger(__name__)

_FMT = "%Y-%m-%d %H:%M"


def _local_now() -> datetime:
    """Current time in masters' local timezone (UTC + TIMEZONE_OFFSET_HOURS)."""
    return datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET_HOURS)


async def send_reminders(bot: Bot):
    """Send 24h and 2h reminders for upcoming bookings (UX-6)."""
    now = _local_now()

    # 24-hour reminders
    w24_start = (now + timedelta(hours=23)).strftime(_FMT)
    w24_end   = (now + timedelta(hours=25)).strftime(_FMT)
    for booking in await get_pending_reminders_24h(w24_start, w24_end):
        addr_line = f"\n📍 Адрес: {booking['master_address']}" if booking["master_address"] else ""
        try:
            await bot.send_message(
                booking["client_telegram_id"],
                f"⏰ <b>Напоминание!</b>\n\n"
                f"Завтра в <b>{booking['booking_time']}</b> у вас запись:\n"
                f"✂️ {booking['service_name']}\n"
                f"📅 {format_date_ru(booking['booking_date'])}"
                f"{addr_line}\n\n"
                f"Пожалуйста, подтвердите визит:",
                parse_mode="HTML",
                reply_markup=reminder_confirm_kb(booking["id"])
            )
            await mark_reminder_sent(booking["id"], "24h")
            logger.info(f"Sent 24h reminder for booking #{booking['id']}")
        except Exception as e:
            logger.error(f"Failed to send 24h reminder for booking #{booking['id']}: {e}")

    # 2-hour reminders
    w2_start = (now + timedelta(hours=1)).strftime(_FMT)
    w2_end   = (now + timedelta(hours=3)).strftime(_FMT)
    for booking in await get_pending_reminders_2h(w2_start, w2_end):
        addr_line = f"\n📍 Адрес: {booking['master_address']}" if booking["master_address"] else ""
        try:
            await bot.send_message(
                booking["client_telegram_id"],
                f"🔔 <b>Скоро визит!</b>\n\n"
                f"Через ~2 часа, в <b>{booking['booking_time']}</b>, вас ждёт:\n"
                f"✂️ {booking['service_name']}"
                f"{addr_line}\n\n"
                f"Подтвердите, что придёте:",
                parse_mode="HTML",
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
