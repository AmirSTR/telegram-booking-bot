from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    adding_service = State()
    editing_service = State()
