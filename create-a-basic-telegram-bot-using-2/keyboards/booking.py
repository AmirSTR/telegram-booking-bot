from datetime import date, timedelta

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import Booking, Service

WEEKDAY_LABELS = {
    0: "Пн",
    1: "Вт",
    2: "Ср",
    3: "Чт",
    4: "Пт",
    5: "Сб",
    6: "Вс",
}


def services_keyboard(services: list[Service]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for service in services:
        builder.button(
            text=f"{service.name} - {service.price} руб.",
            callback_data=f"booking_service:{service.id}",
        )

    builder.adjust(1)
    return builder.as_markup()


def dates_keyboard(days_ahead: int = 10) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    added_days = 0
    current_date = date.today()
    offset = 0

    while added_days < days_ahead:
        candidate = current_date + timedelta(days=offset)
        offset += 1

        if candidate.weekday() >= 5:
            continue

        label = f"{WEEKDAY_LABELS[candidate.weekday()]} {candidate.strftime('%d.%m')}"
        builder.button(
            text=label,
            callback_data=f"booking_date:{candidate.isoformat()}",
        )
        added_days += 1

    builder.adjust(2)
    return builder.as_markup()


def time_slots_keyboard(slots: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for slot in slots:
        builder.button(
            text=slot,
            callback_data=f"booking_time:{slot}",
        )

    builder.adjust(2)
    return builder.as_markup()


def cancel_bookings_keyboard(
    bookings: list[tuple[Booking, Service]],
) -> InlineKeyboardMarkup:
    return bookings_keyboard(bookings, callback_prefix="cancel_booking_select")


def bookings_keyboard(
    bookings: list[tuple[Booking, Service]],
    callback_prefix: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for booking, service in bookings:
        builder.button(
            text=(
                f"{booking.date.strftime('%d.%m.%Y')} | "
                f"{booking.time.strftime('%H:%M')} | "
                f"{service.name}"
            ),
            callback_data=f"{callback_prefix}:{booking.id}",
        )

    builder.adjust(1)
    return builder.as_markup()


def confirm_cancel_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Подтвердить отмену",
        callback_data=f"cancel_booking_confirm:{booking_id}",
    )
    builder.button(
        text="Назад",
        callback_data="cancel_booking_back",
    )
    builder.adjust(1)
    return builder.as_markup()


def confirm_booking_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Подтвердить запись",
        callback_data=f"confirm_booking:{booking_id}",
    )
    builder.adjust(1)
    return builder.as_markup()


def waitlist_offer_keyboard(service_id: int, selected_date: date) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Встать в лист ожидания",
        callback_data=f"waitlist_join:{service_id}:{selected_date.isoformat()}",
    )
    builder.adjust(1)
    return builder.as_markup()
