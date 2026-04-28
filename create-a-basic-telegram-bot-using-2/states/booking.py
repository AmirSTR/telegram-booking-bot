from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    selecting_service = State()
    selecting_date = State()
    selecting_time = State()
    rescheduling_booking = State()
    rescheduling_date = State()
    rescheduling_time = State()
    cancelling_booking = State()
    confirming_cancel = State()
