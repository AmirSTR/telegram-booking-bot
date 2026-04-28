from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import and_, select

from config import get_admin_chat_id
from database.db import get_session
from database.models import Booking, Service, WaitlistEntry
from keyboards.booking import confirm_booking_keyboard

logger = logging.getLogger(__name__)
REMINDER_24H = timedelta(hours=24)
REMINDER_3H = timedelta(hours=3)
REMINDER_GRACE = timedelta(minutes=15)
WORKDAY_START = time(hour=10, minute=0)
WORKDAY_END = time(hour=20, minute=0)


def build_booking_datetime(booking: Booking) -> datetime:
    return datetime.combine(booking.date, booking.time)


def build_booking_end_datetime(booking: Booking, service: Service) -> datetime:
    return build_booking_datetime(booking) + timedelta(minutes=service.duration)


def combine_date_time(selected_date: date, selected_time: time) -> datetime:
    return datetime.combine(selected_date, selected_time)


def build_time_slots(duration_minutes: int, selected_date: date) -> list[time]:
    slots: list[time] = []
    current_start = combine_date_time(selected_date, WORKDAY_START)
    day_end = combine_date_time(selected_date, WORKDAY_END)
    now = datetime.now()

    while current_start + timedelta(minutes=duration_minutes) <= day_end:
        if selected_date > now.date() or current_start >= now:
            slots.append(current_start.time().replace(second=0, microsecond=0))
        current_start += timedelta(minutes=duration_minutes)

    return slots


def has_time_overlap(
    start_a: datetime,
    duration_a: int,
    start_b: datetime,
    duration_b: int,
) -> bool:
    end_a = start_a + timedelta(minutes=duration_a)
    end_b = start_b + timedelta(minutes=duration_b)
    return start_a < end_b and start_b < end_a


def get_available_slots_for_service(
    service_duration: int,
    selected_date: date,
) -> list[str]:
    with get_session() as session:
        booked_items = session.execute(
            select(Booking, Service)
            .join(Service, Booking.service_id == Service.id)
            .where(
                and_(
                    Booking.date == selected_date,
                    Booking.status == "active",
                )
            )
            .order_by(Booking.time)
        ).all()

    available_slots: list[str] = []

    for slot_time in build_time_slots(service_duration, selected_date):
        slot_start = combine_date_time(selected_date, slot_time)
        if any(
            has_time_overlap(
                slot_start,
                service_duration,
                combine_date_time(booking.date, booking.time),
                service.duration,
            )
            for booking, service in booked_items
        ):
            continue

        available_slots.append(slot_time.strftime("%H:%M"))

    return available_slots


def should_send_reminder(
    now: datetime,
    booking_time: datetime,
    reminder_delta: timedelta,
) -> bool:
    time_left = booking_time - now
    return reminder_delta - REMINDER_GRACE <= time_left <= reminder_delta


def build_reminder_message(booking: Booking, service: Service) -> str:
    return (
        "Напоминание о записи:\n"
        f"Дата: {booking.date.strftime('%d.%m.%Y')}\n"
        f"Время: {booking.time.strftime('%H:%M')}\n"
        f"Услуга: {service.name}"
    )


def build_admin_unconfirmed_message(booking: Booking, service: Service) -> str:
    return (
        "Запись не подтверждена:\n"
        f"Дата: {booking.date.strftime('%d.%m.%Y')}\n"
        f"Время: {booking.time.strftime('%H:%M')}\n"
        f"Услуга: {service.name}\n"
        f"Пользователь ID: {booking.user_id}"
    )


async def mark_completed_bookings() -> None:
    now = datetime.now().replace(second=0, microsecond=0)

    with get_session() as session:
        booking_rows = session.execute(
            select(Booking, Service)
            .join(Service, Booking.service_id == Service.id)
            .where(Booking.status == "active")
        ).all()

        for booking, service in booking_rows:
            booking_end = build_booking_end_datetime(booking, service)
            if booking_end <= now:
                booking.status = "completed"
                booking.completed_at = booking_end

        session.commit()


async def notify_waitlist_users(bot: Bot) -> None:
    now = datetime.now().replace(second=0, microsecond=0)

    with get_session() as session:
        entries = session.execute(
            select(WaitlistEntry, Service)
            .join(Service, WaitlistEntry.service_id == Service.id)
            .where(WaitlistEntry.status.in_(("waiting", "notified")))
            .order_by(WaitlistEntry.date, WaitlistEntry.created_at)
        ).all()

        grouped_entries: dict[tuple[int, date], list[tuple[WaitlistEntry, Service]]] = {}
        for entry, service in entries:
            grouped_entries.setdefault((entry.service_id, entry.date), []).append((entry, service))

        for (_, waitlist_date), queue in grouped_entries.items():
            if waitlist_date < now.date():
                continue

            first_entry, service = queue[0]
            available_slots = get_available_slots_for_service(service.duration, waitlist_date)

            if not available_slots:
                continue

            if first_entry.status == "notified":
                continue

            try:
                await bot.send_message(
                    chat_id=first_entry.user_id,
                    text=(
                        "Освободилось время из листа ожидания:\n"
                        f"Услуга: {service.name}\n"
                        f"Дата: {waitlist_date.strftime('%d.%m.%Y')}\n"
                        f"Свободное время: {', '.join(available_slots)}"
                    ),
                )
            except Exception:
                logger.exception(
                    "Failed to notify waitlist user %s for service %s on %s",
                    first_entry.user_id,
                    service.id,
                    waitlist_date,
                )
                continue

            first_entry.status = "notified"
            first_entry.notified_at = now

        session.commit()


async def send_due_reminders(bot: Bot) -> None:
    now = datetime.now().replace(second=0, microsecond=0)
    admin_chat_id = get_admin_chat_id()

    with get_session() as session:
        booking_rows = session.execute(
            select(Booking, Service)
            .join(Service, Booking.service_id == Service.id)
            .where(Booking.status == "active")
            .order_by(Booking.date, Booking.time)
        ).all()

        for booking, service in booking_rows:
            booking_time = build_booking_datetime(booking)

            if booking_time <= now:
                continue

            reminders_to_mark: list[str] = []

            if (
                booking.reminder_24h_sent_at is None
                and should_send_reminder(now, booking_time, REMINDER_24H)
            ):
                reminders_to_mark.append("24h")

            if (
                booking.reminder_3h_sent_at is None
                and should_send_reminder(now, booking_time, REMINDER_3H)
            ):
                reminders_to_mark.append("3h")

            if not reminders_to_mark:
                if (
                    admin_chat_id is not None
                    and booking.confirmed_at is None
                    and booking.admin_unconfirmed_notified_at is None
                    and should_send_reminder(now, booking_time, REMINDER_3H)
                ):
                    try:
                        await bot.send_message(
                            chat_id=admin_chat_id,
                            text=build_admin_unconfirmed_message(booking, service),
                        )
                    except Exception:
                        logger.exception(
                            "Failed to send admin unconfirmed notification for booking %s",
                            booking.id,
                        )
                    else:
                        booking.admin_unconfirmed_notified_at = now
                continue

            message_text = build_reminder_message(booking, service)
            reply_markup = None

            if booking.confirmed_at is None:
                reply_markup = confirm_booking_keyboard(booking.id)

            try:
                await bot.send_message(
                    chat_id=booking.user_id,
                    text=message_text,
                    reply_markup=reply_markup,
                )
            except Exception:
                logger.exception(
                    "Failed to send reminder for booking %s",
                    booking.id,
                )
                continue

            if "24h" in reminders_to_mark:
                booking.reminder_24h_sent_at = now
            if "3h" in reminders_to_mark:
                booking.reminder_3h_sent_at = now

            if (
                admin_chat_id is not None
                and booking.confirmed_at is None
                and booking.admin_unconfirmed_notified_at is None
                and "3h" in reminders_to_mark
            ):
                try:
                    await bot.send_message(
                        chat_id=admin_chat_id,
                        text=build_admin_unconfirmed_message(booking, service),
                    )
                except Exception:
                    logger.exception(
                        "Failed to send admin unconfirmed notification for booking %s",
                        booking.id,
                    )
                else:
                    booking.admin_unconfirmed_notified_at = now

        session.commit()


def setup_reminder_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        mark_completed_bookings,
        trigger="interval",
        minutes=1,
        id="mark_completed_bookings",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        notify_waitlist_users,
        trigger="interval",
        minutes=1,
        args=[bot],
        id="waitlist_notifications",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        send_due_reminders,
        trigger="interval",
        minutes=1,
        args=[bot],
        id="booking_reminders",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    return scheduler
