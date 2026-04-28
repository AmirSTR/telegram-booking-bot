from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from database.db import get_session
from database.models import User
from keyboards.main_menu import main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    telegram_user = message.from_user

    await state.clear()

    if telegram_user is not None:
        with get_session() as session:
            user = session.scalar(
                select(User).where(User.id == telegram_user.id)
            )

            if user is None:
                session.add(
                    User(
                        id=telegram_user.id,
                        name=telegram_user.full_name,
                        username=telegram_user.username,
                    )
                )
            else:
                user.name = telegram_user.full_name
                user.username = telegram_user.username

            session.commit()

    await message.answer(
        "Добро пожаловать",
        reply_markup=main_menu_keyboard(),
    )
