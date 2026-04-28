from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import and_, or_, select

from database.db import get_session
from database.models import Booking, Service

router = Router()


@router.message(F.text == "Мои записи")
async def handle_my_bookings(message: Message) -> None:
    now = datetime.now()
    today = now.date()
    current_time = now.time().replace(second=0, microsecond=0)

    with get_session() as session:
        bookings = session.execute(
            select(Booking, Service)
            .join(Service, Booking.service_id == Service.id)
            .where(
                and_(
                    Booking.user_id == message.from_user.id,
                    Booking.status == "active",
                    or_(
                        Booking.date > today,
                        and_(
                            Booking.date == today,
                            Booking.time >= current_time,
                        ),
                    ),
                )
            )
            .order_by(Booking.date, Booking.time)
        ).all()

    if not bookings:
        await message.answer("У вас нет предстоящих записей")
        return

    lines = ["Ваши записи:"]
    for booking, service in bookings:
        lines.append(
            f"{booking.date.strftime('%d.%m.%Y')} | "
            f"{booking.time.strftime('%H:%M')} | "
            f"{service.name}"
        )

    await message.answer("\n".join(lines))
@router.message(F.text == "Прайс")
async def handle_price(message: Message) -> None:
    with get_session() as session:
        services = session.scalars(select(Service).order_by(Service.id)).all()

    if not services:
        await message.answer("Список услуг пока пуст")
        return

    lines = ["Прайс:"]
    for service in services:
        lines.append(
            f"{service.name} - {service.price} руб. ({service.duration} мин.)"
        )

    await message.answer("\n".join(lines))
