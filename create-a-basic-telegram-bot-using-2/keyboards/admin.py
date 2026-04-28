from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import Service


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Услуги", callback_data="admin_panel:services")
    builder.button(text="Записи", callback_data="admin_panel:bookings")
    builder.button(text="Доход", callback_data="admin_panel:income")
    builder.adjust(1)
    return builder.as_markup()


def admin_services_keyboard(services: list[Service]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for service in services:
        builder.button(
            text=f"{service.name} | {service.price} руб. | {service.duration} мин.",
            callback_data=f"admin_service:edit:{service.id}",
        )

    builder.button(text="Добавить услугу", callback_data="admin_service:add")
    builder.button(text="Назад", callback_data="admin_panel:back")
    builder.adjust(1)
    return builder.as_markup()
