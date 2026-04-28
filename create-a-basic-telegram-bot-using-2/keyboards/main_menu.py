from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Записаться"), KeyboardButton(text="Мои записи")],
            [
                KeyboardButton(text="Перенести запись"),
                KeyboardButton(text="Отменить запись"),
            ],
            [KeyboardButton(text="Прайс")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )
