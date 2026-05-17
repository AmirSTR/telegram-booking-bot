from aiogram.fsm.state import State, StatesGroup


class AddMasterStates(StatesGroup):
    waiting_telegram_id = State()
    waiting_name = State()


class AddServiceStates(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_duration = State()


class ScheduleStates(StatesGroup):
    waiting_work_start = State()
    waiting_work_end = State()
    waiting_slot_duration = State()


class ClientRegisterStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()


class BookingStates(StatesGroup):
    choosing_service = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()


class RescheduleStates(StatesGroup):
    choosing_booking = State()
    choosing_date = State()
    choosing_time = State()


class WaitlistStates(StatesGroup):
    choosing_service = State()


class WaitlistDateStates(StatesGroup):
    choosing_dates = State()


class ProfileStates(StatesGroup):
    editing_phone = State()
    editing_email = State()
