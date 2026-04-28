from datetime import date, datetime, time, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import and_, or_, select

from database.db import get_session
from database.models import Booking, Service, WaitlistEntry
from keyboards.booking import (
    bookings_keyboard,
    cancel_bookings_keyboard,
    confirm_booking_keyboard,
    confirm_cancel_keyboard,
    dates_keyboard,
    services_keyboard,
    time_slots_keyboard,
    waitlist_offer_keyboard,
)
from states.booking import BookingStates

router = Router()
WORKDAY_START = time(hour=10, minute=0)
WORKDAY_END = time(hour=20, minute=0)


def get_now_parts() -> tuple[date, time]:
    now = datetime.now()
    return now.date(), now.time().replace(second=0, microsecond=0)


def combine_date_time(selected_date: date, selected_time: time) -> datetime:
    return datetime.combine(selected_date, selected_time)


def format_slot(slot_time: time) -> str:
    return slot_time.strftime("%H:%M")


def get_service(service_id: int) -> Service | None:
    with get_session() as session:
        return session.get(Service, service_id)


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


def get_available_slots(
    service_duration: int,
    selected_date: date,
    excluded_booking_id: int | None = None,
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
        )
        existing_bookings = [
            (booking, service)
            for booking, service in booked_items.all()
            if excluded_booking_id is None or booking.id != excluded_booking_id
        ]

    available_slots: list[str] = []

    for slot_time in build_time_slots(service_duration, selected_date):
        slot_start = combine_date_time(selected_date, slot_time)
        is_available = True

        for booking, service in existing_bookings:
            booking_start = combine_date_time(booking.date, booking.time)
            if has_time_overlap(
                slot_start,
                service_duration,
                booking_start,
                service.duration,
            ):
                is_available = False
                break

        if is_available:
            available_slots.append(format_slot(slot_time))

    return available_slots


def get_upcoming_bookings(user_id: int) -> list[tuple[Booking, Service]]:
    today, current_time = get_now_parts()

    with get_session() as session:
        return session.execute(
            select(Booking, Service)
            .join(Service, Booking.service_id == Service.id)
            .where(
                and_(
                    Booking.user_id == user_id,
                    Booking.status == "active",
                    or_(
                        Booking.date > today,
                        and_(
                            Booking.date == today,
                            Booking.time >= current_time,
                        )
                    ),
                )
            )
            .order_by(Booking.date, Booking.time)
        ).all()


@router.message(F.text == "Записаться")
async def start_booking(message: Message, state: FSMContext) -> None:
    with get_session() as session:
        services = session.scalars(select(Service).order_by(Service.id)).all()

    if not services:
        await message.answer("Список услуг пока пуст")
        return

    await state.clear()
    await state.set_state(BookingStates.selecting_service)
    await message.answer(
        "Выберите услугу:",
        reply_markup=services_keyboard(services),
    )


@router.message(F.text == "Отменить запись")
async def start_cancel_booking(message: Message, state: FSMContext) -> None:
    bookings = get_upcoming_bookings(message.from_user.id)

    if not bookings:
        await message.answer("У вас нет записей для отмены")
        return

    await state.clear()
    await state.set_state(BookingStates.cancelling_booking)
    await message.answer(
        "Выберите запись для отмены:",
        reply_markup=cancel_bookings_keyboard(bookings),
    )


@router.message(F.text == "Перенести запись")
async def start_reschedule_booking(message: Message, state: FSMContext) -> None:
    bookings = get_upcoming_bookings(message.from_user.id)

    if not bookings:
        await message.answer("У вас нет записей для переноса")
        return

    await state.clear()
    await state.set_state(BookingStates.rescheduling_booking)
    await message.answer(
        "Выберите запись для переноса:",
        reply_markup=bookings_keyboard(
            bookings,
            callback_prefix="reschedule_booking_select",
        ),
    )


@router.callback_query(
    BookingStates.selecting_service,
    F.data.startswith("booking_service:"),
)
async def select_service(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    service_id = int(callback.data.split(":", maxsplit=1)[1])

    service = get_service(service_id)

    if service is None:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(
        service_id=service_id,
        service_name=service.name,
        service_duration=service.duration,
    )
    await state.set_state(BookingStates.selecting_date)
    await callback.answer()
    await callback.message.answer(
        f"Услуга: {service.name}\nВыберите дату:",
        reply_markup=dates_keyboard(),
    )


@router.callback_query(
    BookingStates.selecting_date,
    F.data.startswith("booking_date:"),
)
async def select_date(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    selected_date = date.fromisoformat(callback.data.split(":", maxsplit=1)[1])

    if selected_date.weekday() >= 5:
        await callback.answer("Можно выбрать только будни", show_alert=True)
        return

    data = await state.get_data()
    service_id = data.get("service_id")
    service_duration = data.get("service_duration")

    if service_id is None or service_duration is None:
        await state.clear()
        await callback.answer("Начните запись заново", show_alert=True)
        return

    available_slots = get_available_slots(service_duration, selected_date)

    if not available_slots:
        await callback.answer()
        await callback.message.answer(
            "На эту дату нет свободного времени. Выберите другую дату:",
            reply_markup=waitlist_offer_keyboard(service_id, selected_date),
        )
        return

    await state.update_data(date=selected_date.isoformat())
    await state.set_state(BookingStates.selecting_time)
    await callback.answer()
    await callback.message.answer(
        f"Дата: {selected_date.strftime('%d.%m.%Y')}\nВыберите время:",
        reply_markup=time_slots_keyboard(available_slots),
    )


@router.callback_query(
    BookingStates.selecting_time,
    F.data.startswith("booking_time:"),
)
async def select_time(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    selected_slot = callback.data.split(":", maxsplit=1)[1]
    data = await state.get_data()
    service_id = data.get("service_id")
    service_name = data.get("service_name")
    service_duration = data.get("service_duration")
    selected_date_raw = data.get("date")

    if (
        service_id is None
        or service_name is None
        or service_duration is None
        or selected_date_raw is None
    ):
        await state.clear()
        await callback.answer("Начните запись заново", show_alert=True)
        return

    selected_date = date.fromisoformat(selected_date_raw)
    try:
        selected_time = datetime.strptime(selected_slot, "%H:%M").time()
    except ValueError:
        await callback.answer("Некорректное время", show_alert=True)
        return

    available_slots = get_available_slots(service_duration, selected_date)

    if selected_slot not in available_slots:
        await callback.answer("Это время уже занято", show_alert=True)

        if not available_slots:
            await state.set_state(BookingStates.selecting_date)
            await callback.message.answer(
                "На эту дату больше нет свободного времени. Выберите другую дату:",
                reply_markup=waitlist_offer_keyboard(service_id, selected_date),
            )
            return

        await callback.message.answer(
            "Выберите другое время:",
            reply_markup=time_slots_keyboard(available_slots),
        )
        return

    with get_session() as session:
        conflicts = session.execute(
            select(Booking, Service)
            .join(Service, Booking.service_id == Service.id)
            .where(
                and_(
                    Booking.date == selected_date,
                    Booking.status == "active",
                )
            )
        )
        slot_start = combine_date_time(selected_date, selected_time)
        existing_booking = next(
            (
                booking
                for booking, service in conflicts.all()
                if has_time_overlap(
                    slot_start,
                    service_duration,
                    combine_date_time(booking.date, booking.time),
                    service.duration,
                )
            ),
            None,
        )

        if existing_booking is not None:
            await callback.answer("Это время уже занято", show_alert=True)
            refreshed_slots = get_available_slots(service_duration, selected_date)

            if not refreshed_slots:
                await state.set_state(BookingStates.selecting_date)
                await callback.message.answer(
                    "На эту дату больше нет свободного времени. Выберите другую дату:",
                    reply_markup=waitlist_offer_keyboard(service_id, selected_date),
                )
                return

            await callback.message.answer(
                "Выберите другое время:",
                reply_markup=time_slots_keyboard(refreshed_slots),
            )
            return

        booking = Booking(
            user_id=callback.from_user.id,
            service_id=service_id,
            date=selected_date,
            time=selected_time,
            status="active",
        )
        session.add(booking)
        session.flush()
        booking_id = booking.id
        waitlist_entries = session.scalars(
            select(WaitlistEntry).where(
                and_(
                    WaitlistEntry.user_id == callback.from_user.id,
                    WaitlistEntry.service_id == service_id,
                    WaitlistEntry.date == selected_date,
                    WaitlistEntry.status.in_(("waiting", "notified")),
                )
            )
        ).all()

        for waitlist_entry in waitlist_entries:
            waitlist_entry.status = "fulfilled"

        session.commit()

    await state.clear()
    await callback.answer("Запись сохранена")
    await callback.message.answer(
        "Запись успешно создана:\n"
        f"Услуга: {service_name}\n"
        f"Дата: {selected_date.strftime('%d.%m.%Y')}\n"
        f"Время: {selected_slot}\n"
        "Статус: ожидает подтверждения",
        reply_markup=confirm_booking_keyboard(booking_id),
    )


@router.callback_query(
    BookingStates.rescheduling_booking,
    F.data.startswith("reschedule_booking_select:"),
)
async def select_booking_to_reschedule(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    booking_id = int(callback.data.split(":", maxsplit=1)[1])

    with get_session() as session:
        result = session.execute(
            select(Booking, Service)
            .join(Service, Booking.service_id == Service.id)
            .where(
                and_(
                    Booking.id == booking_id,
                    Booking.user_id == callback.from_user.id,
                    Booking.status == "active",
                )
            )
        ).first()

    if result is None:
        await state.clear()
        await callback.answer("Запись не найдена", show_alert=True)
        return

    booking, service = result
    booking_label = (
        f"{booking.date.strftime('%d.%m.%Y')} | "
        f"{booking.time.strftime('%H:%M')} | "
        f"{service.name}"
    )

    await state.update_data(
        reschedule_booking_id=booking.id,
        reschedule_service_id=booking.service_id,
        reschedule_service_name=service.name,
        reschedule_service_duration=service.duration,
        reschedule_old_label=booking_label,
    )
    await state.set_state(BookingStates.rescheduling_date)
    await callback.answer()
    await callback.message.answer(
        "Вы выбрали запись:\n"
        f"{booking_label}\n\n"
        "Выберите новую дату:",
        reply_markup=dates_keyboard(),
    )


@router.callback_query(
    BookingStates.rescheduling_date,
    F.data.startswith("booking_date:"),
)
async def select_reschedule_date(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    selected_date = date.fromisoformat(callback.data.split(":", maxsplit=1)[1])

    if selected_date.weekday() >= 5:
        await callback.answer("Можно выбрать только будни", show_alert=True)
        return

    data = await state.get_data()
    service_duration = data.get("reschedule_service_duration")
    booking_id = data.get("reschedule_booking_id")

    if service_duration is None or booking_id is None:
        await state.clear()
        await callback.answer("Начните перенос заново", show_alert=True)
        return

    available_slots = get_available_slots(
        service_duration,
        selected_date,
        excluded_booking_id=booking_id,
    )

    if not available_slots:
        await callback.answer()
        await callback.message.answer(
            "На эту дату нет свободного времени. Выберите другую дату:",
            reply_markup=dates_keyboard(),
        )
        return

    await state.update_data(reschedule_date=selected_date.isoformat())
    await state.set_state(BookingStates.rescheduling_time)
    await callback.answer()
    await callback.message.answer(
        f"Новая дата: {selected_date.strftime('%d.%m.%Y')}\nВыберите новое время:",
        reply_markup=time_slots_keyboard(available_slots),
    )


@router.callback_query(
    BookingStates.rescheduling_time,
    F.data.startswith("booking_time:"),
)
async def select_reschedule_time(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    selected_slot = callback.data.split(":", maxsplit=1)[1]
    data = await state.get_data()
    booking_id = data.get("reschedule_booking_id")
    service_id = data.get("reschedule_service_id")
    service_name = data.get("reschedule_service_name")
    service_duration = data.get("reschedule_service_duration")
    selected_date_raw = data.get("reschedule_date")

    if (
        booking_id is None
        or service_id is None
        or service_name is None
        or service_duration is None
        or selected_date_raw is None
    ):
        await state.clear()
        await callback.answer("Начните перенос заново", show_alert=True)
        return

    selected_date = date.fromisoformat(selected_date_raw)
    try:
        selected_time = datetime.strptime(selected_slot, "%H:%M").time()
    except ValueError:
        await callback.answer("Некорректное время", show_alert=True)
        return

    available_slots = get_available_slots(
        service_duration,
        selected_date,
        excluded_booking_id=booking_id,
    )

    if selected_slot not in available_slots:
        await callback.answer("Это время уже занято", show_alert=True)

        if not available_slots:
            await state.set_state(BookingStates.rescheduling_date)
            await callback.message.answer(
                "На эту дату больше нет свободного времени. Выберите другую дату:",
                reply_markup=dates_keyboard(),
            )
            return

        await callback.message.answer(
            "Выберите другое время:",
            reply_markup=time_slots_keyboard(available_slots),
        )
        return

    with get_session() as session:
        booking = session.scalar(
            select(Booking).where(
                and_(
                    Booking.id == booking_id,
                    Booking.user_id == callback.from_user.id,
                    Booking.status == "active",
                )
            )
        )

        if booking is None:
            await state.clear()
            await callback.answer("Запись уже недоступна", show_alert=True)
            return

        conflicts = session.execute(
            select(Booking, Service)
            .join(Service, Booking.service_id == Service.id)
            .where(
                and_(
                    Booking.id != booking_id,
                    Booking.date == selected_date,
                    Booking.status == "active",
                )
            )
        )
        slot_start = combine_date_time(selected_date, selected_time)
        existing_booking = next(
            (
                other_booking
                for other_booking, service in conflicts.all()
                if has_time_overlap(
                    slot_start,
                    service_duration,
                    combine_date_time(other_booking.date, other_booking.time),
                    service.duration,
                )
            ),
            None,
        )

        if existing_booking is not None:
            await callback.answer("Это время уже занято", show_alert=True)
            refreshed_slots = get_available_slots(
                service_duration,
                selected_date,
                excluded_booking_id=booking_id,
            )

            if not refreshed_slots:
                await state.set_state(BookingStates.rescheduling_date)
                await callback.message.answer(
                    "На эту дату больше нет свободного времени. Выберите другую дату:",
                    reply_markup=dates_keyboard(),
                )
                return

            await callback.message.answer(
                "Выберите другое время:",
                reply_markup=time_slots_keyboard(refreshed_slots),
            )
            return

        booking.date = selected_date
        booking.time = selected_time
        booking.confirmed_at = None
        booking.reminder_24h_sent_at = None
        booking.reminder_3h_sent_at = None
        booking.admin_unconfirmed_notified_at = None
        waitlist_entries = session.scalars(
            select(WaitlistEntry).where(
                and_(
                    WaitlistEntry.user_id == callback.from_user.id,
                    WaitlistEntry.service_id == service_id,
                    WaitlistEntry.date == selected_date,
                    WaitlistEntry.status.in_(("waiting", "notified")),
                )
            )
        ).all()

        for waitlist_entry in waitlist_entries:
            waitlist_entry.status = "fulfilled"

        session.commit()

    await state.clear()
    await callback.answer("Запись перенесена")
    await callback.message.answer(
        "Запись успешно перенесена:\n"
        f"Услуга: {service_name}\n"
        f"Дата: {selected_date.strftime('%d.%m.%Y')}\n"
        f"Время: {selected_slot}\n"
        "Статус: ожидает подтверждения",
        reply_markup=confirm_booking_keyboard(booking_id),
    )


@router.callback_query(F.data.startswith("confirm_booking:"))
async def confirm_booking(callback: CallbackQuery) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    booking_id = int(callback.data.split(":", maxsplit=1)[1])

    with get_session() as session:
        booking = session.scalar(
            select(Booking).where(
                and_(
                    Booking.id == booking_id,
                    Booking.user_id == callback.from_user.id,
                    Booking.status == "active",
                )
            )
        )

        if booking is None:
            await callback.answer("Запись не найдена", show_alert=True)
            return

        if booking.confirmed_at is not None:
            await callback.answer("Запись уже подтверждена")
            return

        booking.confirmed_at = datetime.now().replace(second=0, microsecond=0)
        session.commit()

    await callback.answer("Запись подтверждена")
    await callback.message.answer("Запись подтверждена")


@router.callback_query(F.data.startswith("waitlist_join:"))
async def join_waitlist(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    _, service_id_raw, selected_date_raw = callback.data.split(":", maxsplit=2)
    service_id = int(service_id_raw)
    selected_date = date.fromisoformat(selected_date_raw)

    service = get_service(service_id)
    if service is None:
        await state.clear()
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    with get_session() as session:
        existing_entry = session.scalar(
            select(WaitlistEntry).where(
                and_(
                    WaitlistEntry.user_id == callback.from_user.id,
                    WaitlistEntry.service_id == service_id,
                    WaitlistEntry.date == selected_date,
                    WaitlistEntry.status.in_(("waiting", "notified")),
                )
            )
        )

        if existing_entry is not None:
            await state.clear()
            await callback.answer("Вы уже в листе ожидания", show_alert=True)
            return

        session.add(
            WaitlistEntry(
                user_id=callback.from_user.id,
                service_id=service_id,
                date=selected_date,
                status="waiting",
            )
        )
        session.commit()

    await state.clear()
    await callback.answer("Вы добавлены в лист ожидания")
    await callback.message.answer(
        "Вы добавлены в лист ожидания:\n"
        f"Услуга: {service.name}\n"
        f"Дата: {selected_date.strftime('%d.%m.%Y')}\n"
        "Мы уведомим вас, когда появится свободное время."
    )


@router.callback_query(
    BookingStates.cancelling_booking,
    F.data.startswith("cancel_booking_select:"),
)
async def select_booking_to_cancel(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    booking_id = int(callback.data.split(":", maxsplit=1)[1])

    with get_session() as session:
        result = session.execute(
            select(Booking, Service)
            .join(Service, Booking.service_id == Service.id)
            .where(
                and_(
                    Booking.id == booking_id,
                    Booking.user_id == callback.from_user.id,
                    Booking.status == "active",
                )
            )
        ).first()

    if result is None:
        await state.clear()
        await callback.answer("Запись не найдена", show_alert=True)
        return

    booking, service = result
    booking_label = (
        f"{booking.date.strftime('%d.%m.%Y')} | "
        f"{booking.time.strftime('%H:%M')} | "
        f"{service.name}"
    )

    await state.update_data(cancel_booking_id=booking.id, cancel_booking_label=booking_label)
    await state.set_state(BookingStates.confirming_cancel)
    await callback.answer()
    await callback.message.answer(
        "Подтвердите отмену записи:\n"
        f"{booking_label}",
        reply_markup=confirm_cancel_keyboard(booking.id),
    )


@router.callback_query(
    BookingStates.confirming_cancel,
    F.data == "cancel_booking_back",
)
async def cancel_booking_back(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return

    bookings = get_upcoming_bookings(callback.from_user.id)

    if not bookings:
        await state.clear()
        await callback.answer()
        await callback.message.answer("У вас больше нет записей для отмены")
        return

    await state.set_state(BookingStates.cancelling_booking)
    await callback.answer()
    await callback.message.answer(
        "Выберите запись для отмены:",
        reply_markup=cancel_bookings_keyboard(bookings),
    )


@router.callback_query(
    BookingStates.confirming_cancel,
    F.data.startswith("cancel_booking_confirm:"),
)
async def confirm_cancel_booking(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    booking_id = int(callback.data.split(":", maxsplit=1)[1])
    data = await state.get_data()
    stored_booking_id = data.get("cancel_booking_id")

    if stored_booking_id != booking_id:
        await state.clear()
        await callback.answer("Начните отмену заново", show_alert=True)
        return

    with get_session() as session:
        booking = session.scalar(
            select(Booking).where(
                and_(
                    Booking.id == booking_id,
                    Booking.user_id == callback.from_user.id,
                    Booking.status == "active",
                )
            )
        )

        if booking is None:
            await state.clear()
            await callback.answer("Запись уже недоступна", show_alert=True)
            return

        session.delete(booking)
        session.commit()

    await state.clear()
    await callback.answer("Запись отменена")
    await callback.message.answer("Запись отменена. Слот снова свободен.")
