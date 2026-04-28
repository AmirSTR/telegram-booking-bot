from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import and_, select

from config import is_admin
from database.db import get_session
from database.models import Booking, Service, User
from keyboards.admin import admin_panel_keyboard, admin_services_keyboard
from states.admin import AdminStates

router = Router()


def build_services_text(services: list[Service]) -> str:
    if not services:
        return "Услуги пока отсутствуют"

    lines = ["Услуги:"]
    for service in services:
        lines.append(
            f"{service.id}. {service.name} | {service.price} руб. | {service.duration} мин."
        )
    return "\n".join(lines)


def split_text_chunks(text: str, limit: int = 3500) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current_chunk = ""

    for line in text.splitlines():
        candidate = f"{current_chunk}\n{line}".strip()
        if len(candidate) <= limit:
            current_chunk = candidate
            continue

        if current_chunk:
            chunks.append(current_chunk)
        current_chunk = line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def get_services() -> list[Service]:
    with get_session() as session:
        return session.scalars(select(Service).order_by(Service.id)).all()


def get_all_bookings_text() -> str:
    with get_session() as session:
        rows = session.execute(
            select(Booking, Service, User)
            .join(Service, Booking.service_id == Service.id)
            .join(User, Booking.user_id == User.id)
            .order_by(Booking.date, Booking.time)
        ).all()

    if not rows:
        return "Записей нет"

    lines = ["Все записи:"]
    for booking, service, user in rows:
        username = f"@{user.username}" if user.username else "без username"
        if booking.status == "completed":
            status = "завершена"
        elif booking.confirmed_at:
            status = "подтверждена"
        else:
            status = "ожидает подтверждения"
        lines.append(
            f"{booking.date.strftime('%d.%m.%Y')} | "
            f"{booking.time.strftime('%H:%M')} | "
            f"{service.name} | "
            f"{user.name} ({username}) | "
            f"{status}"
        )

    return "\n".join(lines)


def get_income_text() -> str:
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    with get_session() as session:
        rows = session.execute(
            select(Booking, Service)
            .join(Service, Booking.service_id == Service.id)
            .where(
                and_(
                    Booking.status == "completed",
                    Booking.completed_at.is_not(None),
                )
            )
        ).all()

    today_income = sum(
        service.price
        for booking, service in rows
        if booking.completed_at is not None and booking.completed_at >= today_start
    )
    weekly_income = sum(
        service.price
        for booking, service in rows
        if booking.completed_at is not None and booking.completed_at >= week_start
    )
    monthly_income = sum(
        service.price
        for booking, service in rows
        if booking.completed_at is not None and booking.completed_at >= month_start
    )

    return (
        "Доход:\n"
        f"Сегодня: {today_income} руб.\n"
        f"За неделю: {weekly_income} руб.\n"
        f"За месяц: {monthly_income} руб.\n"
        f"Завершенных записей: {len(rows)}"
    )


def parse_service_input(text: str) -> tuple[str, int, int]:
    parts = [part.strip() for part in text.split("|")]
    if len(parts) != 3:
        raise ValueError("Используйте формат: Название | Цена | Длительность")

    name, price_raw, duration_raw = parts
    price = int(price_raw)
    duration = int(duration_raw)

    if not name:
        raise ValueError("Название не может быть пустым")
    if price <= 0:
        raise ValueError("Цена должна быть больше 0")
    if duration <= 0:
        raise ValueError("Длительность должна быть больше 0")

    return name, price, duration


async def send_services_panel(message: Message) -> None:
    services = get_services()
    await message.answer(
        build_services_text(services),
        reply_markup=admin_services_keyboard(services),
    )


def ensure_admin(user_id: int) -> bool:
    return is_admin(user_id)


@router.message(Command("admin"))
async def open_admin_panel(message: Message, state: FSMContext) -> None:
    if not ensure_admin(message.from_user.id):
        await message.answer("Доступ запрещен")
        return

    await state.clear()
    await message.answer(
        "Админ-панель:",
        reply_markup=admin_panel_keyboard(),
    )


@router.callback_query(F.data == "admin_panel:back")
async def admin_panel_back(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return

    if not ensure_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    await state.clear()
    await callback.answer()
    await callback.message.answer(
        "Админ-панель:",
        reply_markup=admin_panel_keyboard(),
    )


@router.callback_query(F.data == "admin_panel:services")
async def admin_services(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return

    if not ensure_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    await state.clear()
    await callback.answer()
    await send_services_panel(callback.message)


@router.callback_query(F.data == "admin_panel:bookings")
async def admin_bookings(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return

    if not ensure_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    await state.clear()
    await callback.answer()
    for chunk in split_text_chunks(get_all_bookings_text()):
        await callback.message.answer(chunk)


@router.callback_query(F.data == "admin_panel:income")
async def admin_income(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return

    if not ensure_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    await state.clear()
    await callback.answer()
    await callback.message.answer(get_income_text())


@router.callback_query(F.data == "admin_service:add")
async def admin_service_add(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return

    if not ensure_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.adding_service)
    await callback.answer()
    await callback.message.answer(
        "Введите новую услугу в формате:\n"
        "Название | Цена | Длительность"
    )


@router.callback_query(F.data.startswith("admin_service:edit:"))
async def admin_service_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    if not ensure_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    service_id = int(callback.data.split(":")[-1])

    with get_session() as session:
        service = session.get(Service, service_id)

    if service is None:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.set_state(AdminStates.editing_service)
    await state.update_data(edit_service_id=service.id)
    await callback.answer()
    await callback.message.answer(
        "Введите новые данные услуги в формате:\n"
        "Название | Цена | Длительность\n\n"
        f"Текущее значение:\n{service.name} | {service.price} | {service.duration}"
    )


@router.message(AdminStates.adding_service)
async def admin_service_add_submit(message: Message, state: FSMContext) -> None:
    if not ensure_admin(message.from_user.id):
        await message.answer("Доступ запрещен")
        return

    try:
        name, price, duration = parse_service_input(message.text or "")
    except ValueError as error:
        await message.answer(str(error))
        return

    with get_session() as session:
        session.add(
            Service(
                name=name,
                price=price,
                duration=duration,
            )
        )
        session.commit()

    await state.clear()
    await message.answer("Услуга добавлена")
    await send_services_panel(message)


@router.message(AdminStates.editing_service)
async def admin_service_edit_submit(message: Message, state: FSMContext) -> None:
    if not ensure_admin(message.from_user.id):
        await message.answer("Доступ запрещен")
        return

    data = await state.get_data()
    service_id = data.get("edit_service_id")

    if service_id is None:
        await state.clear()
        await message.answer("Начните редактирование заново")
        return

    try:
        name, price, duration = parse_service_input(message.text or "")
    except ValueError as error:
        await message.answer(str(error))
        return

    with get_session() as session:
        service = session.get(Service, service_id)

        if service is None:
            await state.clear()
            await message.answer("Услуга не найдена")
            return

        service.name = name
        service.price = price
        service.duration = duration
        session.commit()

    await state.clear()
    await message.answer("Услуга обновлена")
    await send_services_panel(message)
