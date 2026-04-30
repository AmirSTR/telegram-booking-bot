from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from db.database import (
    get_master, get_client, register_client, get_services,
    get_booked_slots, create_booking, get_client_bookings,
    cancel_booking, add_to_waitlist, get_booking
)
from keyboards.keyboards import (
    client_main_kb, services_client_kb, dates_kb, time_slots_kb,
    confirm_booking_kb, client_bookings_kb, confirm_cancel_kb, phone_kb
)
from utils.states import ClientRegisterStates, BookingStates, WaitlistStates
from utils.schedule import get_weekdays_for_next_days, generate_time_slots, get_free_slots, format_date_ru

router = Router()


async def get_client_master_id(state: FSMContext) -> int | None:
    data = await state.get_data()
    return data.get("master_id")


# ─── START ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def client_start(message: Message, state: FSMContext):
    """
    Single entry point for ALL /start commands.
    Handles: masters (no args), clients via deep-link, unknown users.
    """
    from keyboards.keyboards import master_main_kb as _master_main_kb

    # Parse deep-link argument — Telegram sends "/start master_123"
    text = message.text or ""
    parts = text.split(maxsplit=1)
    raw_arg = parts[1] if len(parts) > 1 else ""

    master_id = None
    if raw_arg.startswith("master_"):
        try:
            master_id = int(raw_arg[len("master_"):])
        except ValueError:
            pass

    sender_master = await get_master(message.from_user.id)

    # Case 1: known master, no deep-link → show master panel
    if sender_master and not master_id:
        await message.answer(
            f"✂️ Привет, <b>{sender_master['name']}</b>!\n\n"
            f"Это твоя панель управления записями.",
            parse_mode="HTML",
            reply_markup=_master_main_kb()
        )
        return

    # Case 2: master opened their own link → show master panel
    if sender_master and master_id and sender_master["telegram_id"] == master_id:
        await message.answer(
            f"✂️ Привет, <b>{sender_master['name']}</b>!\n\n"
            f"Это твоя панель управления записями.",
            parse_mode="HTML",
            reply_markup=_master_main_kb()
        )
        return

    # Case 3: no deep-link and not a master → ask to get link from master
    if not master_id:
        await message.answer(
            "👋 Привет!\n\n"
            "Для записи к мастеру используй персональную ссылку от своего мастера.\n\n"
            "Если у тебя нет ссылки — попроси её у мастера напрямую."
        )
        return

    # Case 4: client arrived via deep-link
    master = await get_master(master_id)
    if not master:
        await message.answer("❌ Мастер не найден. Проверь ссылку.")
        return

    # Save master_id in FSM so all subsequent buttons work
    await state.update_data(master_id=master_id)

    client = await get_client(master_id, message.from_user.id)
    if client:
        await message.answer(
            f"✂️ Добро пожаловать к мастеру <b>{master['name']}</b>!\n\n"
            f"Что вы хотите сделать?",
            parse_mode="HTML",
            reply_markup=client_main_kb()
        )
    else:
        await message.answer(
            f"👋 Привет! Вы переходите к мастеру <b>{master['name']}</b>.\n\n"
            f"Как вас зовут? (введите имя и фамилию)",
            parse_mode="HTML"
        )
        await state.set_state(ClientRegisterStates.waiting_name)


@router.message(ClientRegisterStates.waiting_name)
async def process_client_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Пожалуйста, введите полное имя")
        return
    await state.update_data(client_name=name)
    await message.answer(
        "Поделитесь номером телефона (нажмите кнопку) или введите вручную:",
        reply_markup=phone_kb()
    )
    await state.set_state(ClientRegisterStates.waiting_phone)


@router.message(ClientRegisterStates.waiting_phone, F.contact)
async def process_client_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await _finish_registration(message, state, phone)


@router.message(ClientRegisterStates.waiting_phone)
async def process_client_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip() if message.text else None
    await _finish_registration(message, state, phone)


async def _finish_registration(message: Message, state: FSMContext, phone: str | None):
    data = await state.get_data()
    master_id = data.get("master_id")
    name = data.get("client_name")
    master = await get_master(master_id)
    await register_client(master_id, message.from_user.id, name, phone)
    await message.answer(
        f"✅ Вы зарегистрированы у мастера <b>{master['name']}</b>!\n\n"
        f"Что вы хотите сделать?",
        parse_mode="HTML",
        reply_markup=client_main_kb()
    )
    # Fix #6: only clear FSM state, keep master_id in data
    await state.set_state(None)


# ─── MAIN MENU ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "c:back")
async def cb_client_back(callback: CallbackQuery, state: FSMContext):
    master_id = await get_client_master_id(state)
    if not master_id:
        await callback.answer("Сессия истекла. Перейди по ссылке мастера заново.", show_alert=True)
        return
    master = await get_master(master_id)
    await callback.message.edit_text(
        f"✂️ Мастер <b>{master['name']}</b>\n\nЧто вы хотите сделать?",
        parse_mode="HTML",
        reply_markup=client_main_kb()
    )
    await callback.answer()


# ─── BOOKING FLOW ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "c:book")
async def cb_book_start(callback: CallbackQuery, state: FSMContext):
    master_id = await get_client_master_id(state)
    if not master_id:
        await callback.answer("Сессия истекла. Перейди по ссылке мастера заново.", show_alert=True)
        return
    services = await get_services(master_id)
    if not services:
        await callback.message.edit_text(
            "😔 У мастера пока нет доступных услуг.", reply_markup=client_main_kb()
        )
    else:
        await callback.message.edit_text(
            "✂️ <b>Выберите услугу:</b>",
            parse_mode="HTML",
            reply_markup=services_client_kb(services)
        )
        await state.set_state(BookingStates.choosing_service)
    await callback.answer()


@router.callback_query(F.data.startswith("c:service:"), BookingStates.choosing_service)
async def cb_choose_service(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split(":")[2])
    await state.update_data(service_id=service_id)
    await _show_dates(callback, state)
    await callback.answer()


async def _show_dates(callback: CallbackQuery, state: FSMContext):
    dates = get_weekdays_for_next_days(14)
    await callback.message.edit_text(
        "📅 <b>Выберите дату:</b>\n<i>Доступны только будние дни</i>",
        parse_mode="HTML",
        reply_markup=dates_kb(dates)
    )
    await state.set_state(BookingStates.choosing_date)


@router.callback_query(F.data == "c:choose_date")
async def cb_back_to_dates(callback: CallbackQuery, state: FSMContext):
    await _show_dates(callback, state)
    await callback.answer()


@router.callback_query(F.data.startswith("c:date:"), BookingStates.choosing_date)
async def cb_choose_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[2]
    await state.update_data(booking_date=date_str)
    master_id = await get_client_master_id(state)
    data = await state.get_data()
    service_id = data.get("service_id")

    master = await get_master(master_id)
    from db.database import get_service
    service = await get_service(service_id)

    all_slots = generate_time_slots(
        master["work_start"], master["work_end"], master["slot_duration"]
    )
    booked = await get_booked_slots(master_id, date_str)
    # Fix #4: pass service duration so overlaps are detected correctly
    free_slots = get_free_slots(all_slots, booked, service["duration"])

    if not free_slots:
        await callback.message.edit_text(
            f"😔 На <b>{format_date_ru(date_str)}</b> нет свободных слотов.\n\n"
            f"Выберите другую дату или встаньте в лист ожидания.",
            parse_mode="HTML",
            reply_markup=dates_kb(get_weekdays_for_next_days(14))
        )
    else:
        await callback.message.edit_text(
            f"⏰ <b>Выберите время</b> на {format_date_ru(date_str)}:",
            parse_mode="HTML",
            reply_markup=time_slots_kb(free_slots)
        )
        await state.set_state(BookingStates.choosing_time)
    await callback.answer()


@router.callback_query(F.data.startswith("c:time:"), BookingStates.choosing_time)
async def cb_choose_time(callback: CallbackQuery, state: FSMContext):
    # Fix #2: robust time parsing — join everything after "c:time:" prefix
    time_str = ":".join(callback.data.split(":")[2:])
    await state.update_data(booking_time=time_str)
    data = await state.get_data()
    master_id = data.get("master_id")
    service_id = data.get("service_id")
    from db.database import get_service
    service = await get_service(service_id)
    master = await get_master(master_id)
    await callback.message.edit_text(
        f"📋 <b>Подтвердите запись:</b>\n\n"
        f"✂️ Мастер: {master['name']}\n"
        f"🎯 Услуга: {service['name']}\n"
        f"💰 Цена: {service['price']:.0f}₽\n"
        f"📅 Дата: {format_date_ru(data['booking_date'])}\n"
        f"⏰ Время: {time_str}\n"
        f"⌛ Длительность: {service['duration']} мин",
        parse_mode="HTML",
        reply_markup=confirm_booking_kb()
    )
    await state.set_state(BookingStates.confirming)
    await callback.answer()


@router.callback_query(F.data == "c:confirm_booking", BookingStates.confirming)
async def cb_confirm_booking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    master_id = data["master_id"]
    service_id = data["service_id"]
    booking_date = data["booking_date"]
    booking_time = data["booking_time"]

    # Fix #7: create_booking now checks for conflicts atomically; returns None on conflict
    booking_id = await create_booking(
        master_id, callback.from_user.id, service_id, booking_date, booking_time
    )

    if booking_id is None:
        # Slot was taken between selection and confirmation — show updated availability
        from db.database import get_service
        service = await get_service(service_id)
        master = await get_master(master_id)
        booked = await get_booked_slots(master_id, booking_date)
        all_slots = generate_time_slots(master["work_start"], master["work_end"], master["slot_duration"])
        free_slots = get_free_slots(all_slots, booked, service["duration"])
        if free_slots:
            await callback.message.edit_text(
                f"⚠️ К сожалению, это время только что заняли.\n\n"
                f"⏰ <b>Выберите другое время</b> на {format_date_ru(booking_date)}:",
                parse_mode="HTML",
                reply_markup=time_slots_kb(free_slots)
            )
            await state.set_state(BookingStates.choosing_time)
        else:
            await callback.message.edit_text(
                f"⚠️ К сожалению, это время только что заняли, и свободных слотов на "
                f"{format_date_ru(booking_date)} больше нет.\n\nВыберите другую дату.",
                parse_mode="HTML",
                reply_markup=dates_kb(get_weekdays_for_next_days(14))
            )
            await state.set_state(BookingStates.choosing_date)
        await callback.answer()
        return

    from db.database import get_service
    service = await get_service(service_id)
    master = await get_master(master_id)
    client = await get_client(master_id, callback.from_user.id)

    # Notify master
    try:
        await callback.bot.send_message(
            master_id,
            f"🔔 <b>Новая запись!</b>\n\n"
            f"👤 Клиент: {client['name']}\n"
            f"📱 Телефон: {client['phone'] or 'не указан'}\n"
            f"✂️ Услуга: {service['name']}\n"
            f"💰 Цена: {service['price']:.0f}₽\n"
            f"📅 Дата: {format_date_ru(booking_date)}\n"
            f"⏰ Время: {booking_time}",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await state.set_state(None)
    await callback.message.edit_text(
        f"✅ <b>Запись создана!</b>\n\n"
        f"📅 {format_date_ru(booking_date)} в {booking_time}\n"
        f"✂️ {service['name']} у мастера {master['name']}\n\n"
        f"Мы напомним вам за сутки и за несколько часов до визита.",
        parse_mode="HTML",
        reply_markup=client_main_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "c:cancel_booking")
async def cb_cancel_new_booking(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    await callback.message.edit_text(
        "Запись отменена.", reply_markup=client_main_kb()
    )
    await callback.answer()


# ─── MY BOOKINGS ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "c:my_bookings")
async def cb_my_bookings(callback: CallbackQuery, state: FSMContext):
    master_id = await get_client_master_id(state)
    if not master_id:
        await callback.answer("Сессия истекла. Перейди по ссылке мастера заново.", show_alert=True)
        return
    bookings = await get_client_bookings(master_id, callback.from_user.id)
    if not bookings:
        await callback.message.edit_text(
            "📋 У вас нет предстоящих записей.", reply_markup=client_main_kb()
        )
    else:
        text = "📋 <b>Ваши записи:</b>\n\n"
        for b in bookings:
            status_icon = {"pending": "⏳", "confirmed": "✅"}.get(b["status"], "📌")
            text += f"{status_icon} {format_date_ru(b['booking_date'])} в {b['booking_time']}\n"
            text += f"   {b['service_name']} — {b['price']:.0f}₽\n\n"
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=client_main_kb()
        )
    await callback.answer()


# ─── CANCEL BOOKING ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "c:cancel")
async def cb_cancel_start(callback: CallbackQuery, state: FSMContext):
    master_id = await get_client_master_id(state)
    if not master_id:
        await callback.answer("Сессия истекла. Перейди по ссылке мастера заново.", show_alert=True)
        return
    bookings = await get_client_bookings(master_id, callback.from_user.id)
    if not bookings:
        await callback.message.edit_text(
            "📋 Нет записей для отмены.", reply_markup=client_main_kb()
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Выберите запись для отмены:</b>",
            parse_mode="HTML",
            reply_markup=client_bookings_kb(bookings)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("c:cancel_id:"))
async def cb_cancel_select(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[2])
    b = await get_booking(booking_id)
    if not b:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    await callback.message.edit_text(
        f"Отменить запись на <b>{format_date_ru(b['booking_date'])}</b> в <b>{b['booking_time']}</b>?\n"
        f"Услуга: {b['service_name']}",
        parse_mode="HTML",
        reply_markup=confirm_cancel_kb(booking_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("c:do_cancel:"))
async def cb_do_cancel(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.split(":")[2])
    b = await get_booking(booking_id)
    if not b:
        return
    await cancel_booking(booking_id, client_telegram_id=callback.from_user.id)
    try:
        await callback.bot.send_message(
            b["admin_id"],
            f"❌ <b>Клиент отменил запись</b>\n\n"
            f"👤 {b['client_name']}\n"
            f"📅 {format_date_ru(b['booking_date'])} в {b['booking_time']}\n"
            f"✂️ {b['service_name']}",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.message.edit_text(
        "✅ Запись отменена.", reply_markup=client_main_kb()
    )
    await callback.answer()


# ─── WAITLIST ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "c:waitlist")
async def cb_client_waitlist(callback: CallbackQuery, state: FSMContext):
    master_id = await get_client_master_id(state)
    if not master_id:
        await callback.answer("Сессия истекла. Перейди по ссылке мастера заново.", show_alert=True)
        return
    services = await get_services(master_id)
    if not services:
        await callback.message.edit_text(
            "Нет доступных услуг.", reply_markup=client_main_kb()
        )
        return
    await callback.message.edit_text(
        "🔔 <b>Лист ожидания</b>\n\nВыберите услугу, для которой хотите ждать свободное окно:",
        parse_mode="HTML",
        reply_markup=services_client_kb(services)
    )
    # Fix #3: use proper StatesGroup instead of raw string
    await state.set_state(WaitlistStates.choosing_service)
    await callback.answer()


# Fix #3: filter uses WaitlistStates.choosing_service instead of raw string
@router.callback_query(F.data.startswith("c:service:"), WaitlistStates.choosing_service)
async def cb_waitlist_service(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split(":")[2])
    master_id = await get_client_master_id(state)
    await add_to_waitlist(master_id, callback.from_user.id, service_id)
    await state.set_state(None)
    master = await get_master(master_id)
    await callback.message.edit_text(
        f"✅ Вы добавлены в лист ожидания!\n\n"
        f"Как только у мастера <b>{master['name']}</b> появится свободное окно, "
        f"мы вас уведомим.",
        parse_mode="HTML",
        reply_markup=client_main_kb()
    )
    await callback.answer()


# ─── REMINDER RESPONSES ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("r:confirm:"))
async def cb_reminder_confirm(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[2])
    from db.database import confirm_booking
    b = await get_booking(booking_id)
    if not b:
        return
    await confirm_booking(booking_id)
    try:
        await callback.bot.send_message(
            b["admin_id"],
            f"✅ Клиент <b>{b['client_name']}</b> подтвердил запись на "
            f"{format_date_ru(b['booking_date'])} в {b['booking_time']}",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.message.edit_text("✅ Запись подтверждена! Ждём вас.")
    await callback.answer()


@router.callback_query(F.data.startswith("r:cancel:"))
async def cb_reminder_cancel(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[2])
    b = await get_booking(booking_id)
    if not b:
        return
    await cancel_booking(booking_id)
    try:
        await callback.bot.send_message(
            b["admin_id"],
            f"❌ Клиент <b>{b['client_name']}</b> отменил запись на "
            f"{format_date_ru(b['booking_date'])} в {b['booking_time']}",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.message.edit_text("❌ Запись отменена. Жаль, что не получилось!")
    await callback.answer()
