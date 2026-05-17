from urllib.parse import urlencode
from datetime import datetime, timedelta
from typing import List

from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)


def remove_kb():
    return ReplyKeyboardRemove()


# ─── SUPER ADMIN ──────────────────────────────────────────────────────────────

def super_admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Добавить мастера", callback_data="sa:add_master")],
        [InlineKeyboardButton(text="📋 Список мастеров", callback_data="sa:list_masters")],
        [InlineKeyboardButton(text="❌ Удалить мастера", callback_data="sa:remove_master")],
    ])


def masters_list_kb(masters: list, action: str = "remove") -> InlineKeyboardMarkup:
    buttons = []
    for m in masters:
        buttons.append([InlineKeyboardButton(
            text=f"✂️ {m['name']}",
            callback_data=f"sa:{action}:{m['telegram_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="sa:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── MASTER ───────────────────────────────────────────────────────────────────

def master_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 Мои услуги", callback_data="m:services")],
        [InlineKeyboardButton(text="📅 Расписание на сегодня", callback_data="m:today")],
        [InlineKeyboardButton(text="📆 Все записи", callback_data="m:bookings")],
        [InlineKeyboardButton(text="💰 Статистика дохода", callback_data="m:stats")],
        [InlineKeyboardButton(text="⏰ Настройки рабочего времени", callback_data="m:schedule")],
        [InlineKeyboardButton(text="ℹ️ Моя страница для клиентов", callback_data="m:my_info")],
        [InlineKeyboardButton(text="🔗 Моя ссылка для клиентов", callback_data="m:link")],
        [InlineKeyboardButton(text="👥 Лист ожидания", callback_data="m:waitlist")],
    ])


def master_info_kb() -> InlineKeyboardMarkup:
    """Keyboard for editing the master's public profile page."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Описание", callback_data="m:info:bio")],
        [InlineKeyboardButton(text="✏️ Адрес", callback_data="m:info:address")],
        [InlineKeyboardButton(text="✏️ Ссылка Яндекс.Карты", callback_data="m:info:maps_yandex")],
        [InlineKeyboardButton(text="✏️ Ссылка 2ГИС", callback_data="m:info:maps_2gis")],
        [InlineKeyboardButton(text="✏️ Координаты (широта, долгота)", callback_data="m:info:lat_lon")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="m:back")],
    ])


def services_kb(services: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in services:
        buttons.append([InlineKeyboardButton(
            text=f"{s['name']} — {s['price']:.0f}₽ ({s['duration']} мин)",
            callback_data=f"m:del_service:{s['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить услугу", callback_data="m:add_service")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="m:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_service_kb(service_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 Да, удалить", callback_data=f"m:confirm_del_service:{service_id}"),
            InlineKeyboardButton(text="◀️ Отмена", callback_data="m:services"),
        ]
    ])


def bookings_master_kb(bookings: list) -> InlineKeyboardMarkup:
    buttons = []
    for b in bookings:
        status_icon = {"pending": "⏳", "confirmed": "✅", "completed": "💚", "cancelled": "❌"}.get(b["status"], "❓")
        from utils.schedule import format_date_ru
        label = f"{status_icon} {format_date_ru(b['booking_date'])} {b['booking_time']} — {b['client_name']}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"m:booking:{b['id']}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="m:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def booking_actions_master_kb(booking_id: int, status: str) -> InlineKeyboardMarkup:
    buttons = []
    if status in ("pending", "confirmed"):
        buttons.append([InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"m:confirm:{booking_id}")])
        buttons.append([InlineKeyboardButton(text="💚 Выполнено", callback_data=f"m:complete:{booking_id}")])
        buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data=f"m:cancel:{booking_id}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="m:bookings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def stats_period_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Эта неделя", callback_data="m:stats:week")],
        [InlineKeyboardButton(text="🗓 Этот месяц", callback_data="m:stats:month")],
        [InlineKeyboardButton(text="📆 Этот год", callback_data="m:stats:year")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="m:back")],
    ])


def waitlist_kb(waitlist: list) -> InlineKeyboardMarkup:
    buttons = []
    for w in waitlist:
        label = f"🔔 {w['client_name']} — {w['service_name']}"
        if w["preferred_date"]:
            label += f" ({w['preferred_date']})"
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=f"m:notify_waitlist:{w['id']}:{w['client_telegram_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="m:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── CLIENT — REPLY KEYBOARD ──────────────────────────────────────────────────

def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def menu_reply_kb() -> ReplyKeyboardMarkup:
    """Persistent bottom keyboard shown after phone registration (BUG-3 fix)."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 Меню")]],
        resize_keyboard=True
    )


# ─── CLIENT — INLINE KEYBOARDS ────────────────────────────────────────────────

def client_main_kb() -> InlineKeyboardMarkup:
    """Restructured main menu (UX-2)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Записаться", callback_data="c:book")],
        [InlineKeyboardButton(text="📋 Мои записи", callback_data="c:my_bookings")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="c:profile")],
        [InlineKeyboardButton(text="ℹ️ О мастере", callback_data="c:about")],
    ])


def services_client_kb(services: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in services:
        buttons.append([InlineKeyboardButton(
            text=f"✂️ {s['name']} — {s['price']:.0f}₽ ({s['duration']} мин)",
            callback_data=f"c:service:{s['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="c:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def dates_kb(dates: List[str]) -> InlineKeyboardMarkup:
    from utils.schedule import format_date_ru
    buttons = []
    row = []
    for i, d in enumerate(dates):
        row.append(InlineKeyboardButton(
            text=format_date_ru(d),
            callback_data=f"c:date:{d}"
        ))
        if len(row) == 2 or i == len(dates) - 1:
            buttons.append(row)
            row = []
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="c:book")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def time_slots_kb(slots: List[str]) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for i, t in enumerate(slots):
        row.append(InlineKeyboardButton(text=t, callback_data=f"c:time:{t}"))
        if len(row) == 4 or i == len(slots) - 1:
            buttons.append(row)
            row = []
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="c:choose_date")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_booking_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="c:confirm_booking"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="c:cancel_booking"),
        ]
    ])


def booking_success_kb(gcal_url: str = "") -> InlineKeyboardMarkup:
    """Keyboard shown after successful booking — includes Google Calendar link (UX-7)."""
    buttons = []
    if gcal_url:
        buttons.append([InlineKeyboardButton(
            text="📆 Добавить в Google Календарь", url=gcal_url
        )])
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="c:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def client_bookings_kb(bookings: list, waitlist_entries: list = None) -> InlineKeyboardMarkup:
    """
    Мои записи: each booking has an inline ❌ cancel button (UX-2).
    Waitlist entries are listed below bookings with a ❌ remove button.
    """
    from utils.schedule import format_date_ru
    if waitlist_entries is None:
        waitlist_entries = []
    buttons = []
    for b in bookings:
        status_icon = {"pending": "⏳", "confirmed": "✅"}.get(b["status"], "📌")
        label = f"{status_icon} {format_date_ru(b['booking_date'])} {b['booking_time']} — {b['service_name']}"
        buttons.append([InlineKeyboardButton(
            text=label[:60],
            callback_data=f"c:cancel_id:{b['id']}"
        )])
    for w in waitlist_entries:
        date_label = format_date_ru(w["preferred_date"]) if w.get("preferred_date") else "любая дата"
        label = f"🔔 {w['service_name']} — {date_label}"
        buttons.append([InlineKeyboardButton(
            text=label[:60],
            callback_data=f"c:del_waitlist:{w['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="c:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_cancel_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"c:do_cancel:{booking_id}"),
            InlineKeyboardButton(text="◀️ Нет", callback_data="c:my_bookings"),
        ]
    ])


def reminder_confirm_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"r:confirm:{booking_id}"),
            InlineKeyboardButton(text="❌ Отменяю", callback_data=f"r:cancel:{booking_id}"),
        ]
    ])


def waitlist_dates_kb(dates: List[str], selected: List[str] = None) -> InlineKeyboardMarkup:
    """Date picker for waitlist sign-up with toggle selection (UX-3)."""
    from utils.schedule import format_date_ru
    if selected is None:
        selected = []
    buttons = []
    row = []
    for i, d in enumerate(dates):
        mark = "✅ " if d in selected else ""
        row.append(InlineKeyboardButton(
            text=f"{mark}{format_date_ru(d)}",
            callback_data=f"c:wl_date:{d}"
        ))
        if len(row) == 2 or i == len(dates) - 1:
            buttons.append(row)
            row = []
    buttons.append([
        InlineKeyboardButton(text="✅ Готово", callback_data="c:wl_confirm"),
        InlineKeyboardButton(text="◀️ Другая дата", callback_data="c:choose_date"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def profile_kb(has_email: bool = False) -> InlineKeyboardMarkup:
    """Profile section keyboard (UX-4)."""
    buttons = [
        [InlineKeyboardButton(text="✏️ Изменить телефон", callback_data="c:edit_phone")],
    ]
    if has_email:
        buttons.append([InlineKeyboardButton(text="✏️ Изменить email", callback_data="c:edit_email")])
    else:
        buttons.append([InlineKeyboardButton(text="✏️ Добавить email", callback_data="c:edit_email")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="c:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def about_master_kb(yandex_url: str = "", gis_url: str = "") -> InlineKeyboardMarkup:
    """О мастере keyboard with map links (UX-5)."""
    buttons = []
    if yandex_url:
        buttons.append([InlineKeyboardButton(text="🗺 Яндекс.Карты", url=yandex_url)])
    if gis_url:
        buttons.append([InlineKeyboardButton(text="🗺 2ГИС", url=gis_url)])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="c:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def make_gcal_url(service_name: str, date_str: str, time_str: str,
                  duration_min: int, master_name: str, address: str = "") -> str:
    """Build a prefilled Google Calendar event URL (UX-7). No API required."""
    try:
        start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        end = start + timedelta(minutes=duration_min)
        params = {
            "action": "TEMPLATE",
            "text": f"{service_name} — {master_name}",
            "dates": f"{start.strftime('%Y%m%dT%H%M%S')}/{end.strftime('%Y%m%dT%H%M%S')}",
        }
        if address:
            params["location"] = address
        return "https://calendar.google.com/calendar/r/eventedit?" + urlencode(params)
    except Exception:
        return ""
