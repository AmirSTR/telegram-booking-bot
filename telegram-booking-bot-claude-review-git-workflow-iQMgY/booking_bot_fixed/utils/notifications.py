from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db.database import DB_PATH, get_waitlist_by_date, get_master
from utils.message_manager import MessageManager
from utils.schedule import format_date_ru

message_manager = MessageManager(DB_PATH)


async def notify_waitlist(bot: Bot, admin_id: int, date_str: str, exclude_user_id: int = None):
    """Notify waitlist clients when a slot opens on a specific date."""
    waitlist = await get_waitlist_by_date(admin_id, date_str)
    if not waitlist:
        return
    master = await get_master(admin_id)
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=master_{admin_id}"
    for entry in waitlist:
        if exclude_user_id and entry["client_telegram_id"] == exclude_user_id:
            continue
        try:
            await message_manager.send_message(
                bot,
                entry["client_telegram_id"],
                f"🔔 <b>Освободилось место!</b>\n\n"
                f"На <b>{format_date_ru(date_str)}</b> у мастера <b>{master['name']}</b> "
                f"появилось свободное время!\n\n"
                f"Перейдите по ссылке, чтобы записаться:",
                parse_mode="HTML",
                user_id=entry["client_telegram_id"],
                persistent=True,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📅 Записаться", url=link)]
                ])
            )
        except Exception:
            pass
