from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from typing import List


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
        [InlineKeyboardButton(text="🔗 Моя ссылка для клиентов", callback_data="m:link")],
        [InlineKeyboardButton(text="👥 Лист ожидания", callback_data="m:waitlist")],
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
        # Fix #9: show human-readable Russian date instead of raw YYYY-MM-DD
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


# ─── CLIENT ───────────────────────────────────────────────────────────────────

def client_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Записаться", callback_data="c:book")],
        [InlineKeyboardButton(text="📋 Мои записи", callback_data="c:my_bookings")],
        [InlineKeyboardButton(text="❌ Отменить запись", callback_data="c:cancel")],
        [InlineKeyboardButton(text="🔔 Лист ожидания", callback_data="c:waitlist")],
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


def client_bookings_kb(bookings: list) -> InlineKeyboardMarkup:
    buttons = []
    for b in bookings:
        from utils.schedule import format_date_ru
        label = f"📌 {format_date_ru(b['booking_date'])} {b['booking_time']} — {b['service_name']}"
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=f"c:cancel_id:{b['id']}"
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


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
