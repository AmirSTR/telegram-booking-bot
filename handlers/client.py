from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from db.database import (
    get_master, get_client, register_client, get_services, get_service,
    get_booked_slots, create_booking, get_client_bookings,
    cancel_booking, add_to_waitlist, get_booking,
    update_client_name, update_client_phone, update_client_email,
    get_client_visit_count, get_client_waitlist, remove_client_waitlist_entry,
    get_client_master, confirm_booking,
)
from keyboards.keyboards import (
    client_main_kb, services_client_kb, dates_kb, time_slots_kb,
    confirm_booking_kb, client_bookings_kb, confirm_cancel_kb, phone_kb,
    menu_reply_kb, profile_kb, about_master_kb, waitlist_dates_kb,
    booking_success_kb, make_gcal_url,
)
from utils.states import (
    ClientRegisterStates, BookingStates, WaitlistDateStates, ProfileStates,
)
from utils.schedule import (
    get_weekdays_for_next_days, generate_time_slots, get_free_slots, format_date_ru,
)
from utils.notifications import notify_waitlist
from utils.message_manager import manager

router = Router()


# ─── HELPERS ──────────────────────────────────────────────────────────────────

async def get_client_master_id(state: FSMContext) -> int | None:
    return (await state.get_data()).get("master_id")


async def _resolve_master_id(state: FSMContext, user_id: int) -> int | None:
    master_id = await get_client_master_id(state)
    if not master_id:
        existing = await get_client_master(user_id)
        if existing:
            master_id = existing["admin_id"]
            await state.update_data(master_id=master_id)
    return master_id


async def update_menu(
    callback: CallbackQuery,
    text: str,
    keyboard=None,
    parse_mode: str = "HTML",
) -> None:
    """
    Primary display primitive for callback handlers.

    Tries to edit the current message in-place (no new message, no chat clutter).
    Falls back to sending a new tracked message only if edit fails (message too
    old, deleted, or content unchanged triggers a benign "not modified" error).
    """
    try:
        await callback.message.edit_text(
            text, parse_mode=parse_mode, reply_markup=keyboard
        )
    except Exception as e:
        if "message is not modified" in str(e).lower():
            return  # content is already correct — nothing to do
        # Edit not possible: send a new message and track it for auto-cleanup
        msg = await callback.message.answer(
            text, parse_mode=parse_mode, reply_markup=keyboard
        )
        await manager.register(
            callback.bot, msg.chat.id, callback.from_user.id, msg.message_id
        )


async def send_tracked(
    message: Message,
    text: str,
    keyboard=None,
    parse_mode: str = "HTML",
    persistent: bool = False,
) -> Message:
    """
    Send a new bot message and register it with the message manager.
    Use this in all Message handlers (text input, slash commands) where
    sending a new message is unavoidable.
    persistent=True: message sets the reply keyboard — never auto-deleted.
    """
    msg = await message.answer(text, parse_mode=parse_mode, reply_markup=keyboard)
    await manager.register(
        message.bot, msg.chat.id, message.from_user.id, msg.message_id,
        persistent=persistent,
    )
    return msg


# ─── START ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def client_start(message: Message, state: FSMContext):
    from keyboards.keyboards import master_main_kb as _master_main_kb

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

    if sender_master and not master_id:
        await send_tracked(
            message,
            f"✂️ Привет, <b>{sender_master['name']}</b>!\n\nЭто твоя панель управления записями.",
            _master_main_kb(),
        )
        return

    if sender_master and master_id and sender_master["telegram_id"] == master_id:
        await send_tracked(
            message,
            f"✂️ Привет, <b>{sender_master['name']}</b>!\n\nЭто твоя панель управления записями.",
            _master_main_kb(),
        )
        return

    # No deep-link, not a master → check if already registered client
    if not master_id:
        existing = await get_client_master(message.from_user.id)
        if existing:
            stored_master_id = existing["admin_id"]
            await state.update_data(master_id=stored_master_id)
            master = await get_master(stored_master_id)
            await send_tracked(
                message,
                f"✂️ Добро пожаловать к мастеру <b>{master['name']}</b>!\n\nЧто вы хотите сделать?",
                client_main_kb(),
            )
            return
        await send_tracked(
            message,
            "👋 Привет! Чтобы записаться, перейди по персональной ссылке своего мастера.\n\n"
            "Если ссылки нет — попроси её у мастера напрямую.",
        )
        return

    master = await get_master(master_id)
    if not master:
        await send_tracked(message, "❌ Мастер не найден. Проверь ссылку.")
        return

    await state.update_data(master_id=master_id)
    client = await get_client(master_id, message.from_user.id)

    welcome = (
        f"👋 Привет! Вы попали к боту мастера <b>{master['name']}</b>.\n\n"
        f"Здесь вы можете:\n"
        f"📅 Записаться на сеанс\n"
        f"📋 Посмотреть свои записи\n"
        f"🔔 Встать в лист ожидания\n\n"
    )
    if client:
        await send_tracked(message, welcome + "Что вы хотите сделать?", client_main_kb())
    else:
        await send_tracked(message, welcome + "Для начала — как вас зовут?")
        await state.set_state(ClientRegisterStates.waiting_name)


# ─── SLASH COMMANDS (UX-8) ────────────────────────────────────────────────────

@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext):
    master_id = await _resolve_master_id(state, message.from_user.id)
    if not master_id:
        await send_tracked(message, "Перейди по ссылке мастера, чтобы начать запись.")
        return
    services = await get_services(master_id)
    if not services:
        await send_tracked(message, "😔 У мастера пока нет доступных услуг.", client_main_kb())
    else:
        await send_tracked(message, "✂️ <b>Выберите услугу:</b>", services_client_kb(services))
        await state.set_state(BookingStates.choosing_service)


@router.message(Command("appointments"))
async def cmd_appointments(message: Message, state: FSMContext):
    master_id = await _resolve_master_id(state, message.from_user.id)
    if not master_id:
        await send_tracked(message, "Перейди по ссылке мастера для доступа к записям.")
        return
    text, kb = await _bookings_content(master_id, message.from_user.id)
    await send_tracked(message, text, kb)


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext):
    master_id = await _resolve_master_id(state, message.from_user.id)
    if not master_id:
        await send_tracked(message, "Перейди по ссылке мастера для доступа к профилю.")
        return
    text, has_email = await _build_profile_text(message.bot, master_id, message.from_user.id)
    await send_tracked(message, text, profile_kb(has_email))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    master_id = await _resolve_master_id(state, message.from_user.id)
    if not master_id:
        await send_tracked(message, "Перейди по ссылке мастера.")
        return
    text, kb = await _bookings_content(master_id, message.from_user.id)
    await send_tracked(message, text, kb)


# ─── REPLY KEYBOARD HANDLER (BUG-3) ───────────────────────────────────────────

@router.message(F.text == "📋 Меню")
async def handle_menu_button(message: Message, state: FSMContext):
    master_id = await _resolve_master_id(state, message.from_user.id)
    if not master_id:
        await send_tracked(message, "Перейди по ссылке мастера.")
        return
    master = await get_master(master_id)
    await send_tracked(
        message,
        f"✂️ Мастер <b>{master['name']}</b>\n\nЧто вы хотите сделать?",
        client_main_kb(),
    )


# ─── REGISTRATION ─────────────────────────────────────────────────────────────

@router.message(ClientRegisterStates.waiting_name)
async def process_client_name(message: Message, state: FSMContext):
    name = message.text.strip() if message.text else ""
    if len(name) < 2:
        await send_tracked(message, "❌ Пожалуйста, введите ваше имя (минимум 2 символа).")
        return
    await state.update_data(client_name=name)
    await send_tracked(
        message,
        "Поделитесь номером телефона (нажмите кнопку) или введите вручную:",
        phone_kb(),
    )
    await state.set_state(ClientRegisterStates.waiting_phone)


@router.message(ClientRegisterStates.waiting_phone, F.contact)
async def process_client_phone_contact(message: Message, state: FSMContext):
    await _finish_registration(message, state, message.contact.phone_number)


@router.message(ClientRegisterStates.waiting_phone)
async def process_client_phone_text(message: Message, state: FSMContext):
    await _finish_registration(message, state, message.text.strip() if message.text else None)


async def _finish_registration(message: Message, state: FSMContext, phone: str | None):
    data = await state.get_data()
    master_id = data.get("master_id")
    name = data.get("client_name")
    master = await get_master(master_id)
    await register_client(master_id, message.from_user.id, name, phone)
    await state.set_state(None)
    # BUG-3: persistent reply keyboard (not tracked — sets the bottom "Меню" button forever)
    await message.answer(
        f"✅ Вы зарегистрированы у мастера <b>{master['name']}</b>!",
        parse_mode="HTML",
        reply_markup=menu_reply_kb(),
    )
    await send_tracked(message, "Что вы хотите сделать?", client_main_kb())


# ─── MAIN MENU ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "c:back")
async def cb_client_back(callback: CallbackQuery, state: FSMContext):
    master_id = await get_client_master_id(state)
    if not master_id:
        await callback.answer("Сессия истекла. Перейди по ссылке мастера заново.", show_alert=True)
        return
    master = await get_master(master_id)
    await update_menu(
        callback,
        f"✂️ Мастер <b>{master['name']}</b>\n\nЧто вы хотите сделать?",
        client_main_kb(),
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
        await update_menu(callback, "😔 У мастера пока нет доступных услуг.", client_main_kb())
    else:
        await update_menu(callback, "✂️ <b>Выберите услугу:</b>", services_client_kb(services))
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
    await update_menu(
        callback,
        "📅 <b>Выберите дату:</b>\n<i>Доступны только будние дни</i>",
        dates_kb(dates),
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

    master = await get_master(master_id)
    service = await get_service(data["service_id"])

    all_slots = generate_time_slots(master["work_start"], master["work_end"], master["slot_duration"])
    booked = await get_booked_slots(master_id, date_str)
    free_slots = get_free_slots(all_slots, booked, service["duration"])

    if not free_slots:
        await update_menu(
            callback,
            f"😔 На <b>{format_date_ru(date_str)}</b> нет свободных слотов.\n\n"
            "Хотите встать в лист ожидания и получить уведомление, когда появится место?",
            _no_slots_kb(date_str),
        )
    else:
        await update_menu(
            callback,
            f"⏰ <b>Выберите время</b> на {format_date_ru(date_str)}:",
            time_slots_kb(free_slots),
        )
        await state.set_state(BookingStates.choosing_time)
    await callback.answer()


def _no_slots_kb(date_str: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Встать в лист ожидания", callback_data=f"c:wl_start:{date_str}")],
        [InlineKeyboardButton(text="◀️ Выбрать другую дату", callback_data="c:choose_date")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="c:back")],
    ])


@router.callback_query(F.data.startswith("c:time:"), BookingStates.choosing_time)
async def cb_choose_time(callback: CallbackQuery, state: FSMContext):
    time_str = ":".join(callback.data.split(":")[2:])
    await state.update_data(booking_time=time_str)
    data = await state.get_data()
    service = await get_service(data["service_id"])
    master = await get_master(data["master_id"])
    await update_menu(
        callback,
        f"📋 <b>Подтвердите запись:</b>\n\n"
        f"✂️ Мастер: {master['name']}\n"
        f"🎯 Услуга: {service['name']}\n"
        f"💰 Цена: {service['price']:.0f}₽\n"
        f"📅 Дата: {format_date_ru(data['booking_date'])}\n"
        f"⏰ Время: {time_str}\n"
        f"⌛ Длительность: {service['duration']} мин",
        confirm_booking_kb(),
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

    booking_id = await create_booking(
        master_id, callback.from_user.id, service_id, booking_date, booking_time
    )

    if booking_id is None:
        service = await get_service(service_id)
        master = await get_master(master_id)
        booked = await get_booked_slots(master_id, booking_date)
        all_slots = generate_time_slots(master["work_start"], master["work_end"], master["slot_duration"])
        free_slots = get_free_slots(all_slots, booked, service["duration"])
        if free_slots:
            await update_menu(
                callback,
                f"⚠️ К сожалению, это время только что заняли.\n\n"
                f"⏰ <b>Выберите другое время</b> на {format_date_ru(booking_date)}:",
                time_slots_kb(free_slots),
            )
            await state.set_state(BookingStates.choosing_time)
        else:
            await update_menu(
                callback,
                f"⚠️ Слот занят, и свободных мест на {format_date_ru(booking_date)} больше нет.\n\n"
                "Выберите другую дату.",
                dates_kb(get_weekdays_for_next_days(14)),
            )
            await state.set_state(BookingStates.choosing_date)
        await callback.answer()
        return

    service = await get_service(service_id)
    master = await get_master(master_id)
    client = await get_client(master_id, callback.from_user.id)

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
            parse_mode="HTML",
        )
    except Exception:
        pass

    await state.set_state(None)
    gcal_url = make_gcal_url(
        service["name"], booking_date, booking_time,
        service["duration"], master["name"], master["address"] or "",
    )
    await update_menu(
        callback,
        f"✅ <b>Запись подтверждена!</b>\n\n"
        f"📅 {format_date_ru(booking_date)} в {booking_time}\n"
        f"✂️ {service['name']} у мастера {master['name']}\n\n"
        f"🔔 Мы напомним вам за 24 часа и за 2 часа до сеанса.",
        booking_success_kb(gcal_url),
    )
    await callback.answer()


@router.callback_query(F.data == "c:cancel_booking")
async def cb_cancel_new_booking(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    await update_menu(callback, "Запись отменена.", client_main_kb())
    await callback.answer()


# ─── WAITLIST FLOW (UX-3) ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("c:wl_start:"))
async def cb_wl_start(callback: CallbackQuery, state: FSMContext):
    initial_date = callback.data[len("c:wl_start:"):]
    await state.update_data(waitlist_dates=[initial_date])
    dates = get_weekdays_for_next_days(14)
    await update_menu(
        callback,
        "🔔 <b>Лист ожидания</b>\n\n"
        "Выберите даты, когда вам удобно — мы уведомим вас, как только появится свободное время.\n\n"
        "Нажмите на дату, чтобы выбрать или снять выбор:",
        waitlist_dates_kb(dates, [initial_date]),
    )
    await state.set_state(WaitlistDateStates.choosing_dates)
    await callback.answer()


@router.callback_query(F.data.startswith("c:wl_date:"), WaitlistDateStates.choosing_dates)
async def cb_wl_toggle_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data[len("c:wl_date:"):]
    data = await state.get_data()
    selected = list(data.get("waitlist_dates", []))
    if date_str in selected:
        selected.remove(date_str)
    else:
        selected.append(date_str)
    await state.update_data(waitlist_dates=selected)
    dates = get_weekdays_for_next_days(14)
    try:
        await callback.message.edit_reply_markup(reply_markup=waitlist_dates_kb(dates, selected))
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "c:wl_confirm", WaitlistDateStates.choosing_dates)
async def cb_wl_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    master_id = data.get("master_id")
    service_id = data.get("service_id")
    selected = data.get("waitlist_dates", [])

    if not selected:
        await callback.answer("Выберите хотя бы одну дату!", show_alert=True)
        return

    for date_str in selected:
        await add_to_waitlist(master_id, callback.from_user.id, service_id, date_str)

    await state.set_state(None)
    await state.update_data(waitlist_dates=[])
    dates_text = ", ".join(format_date_ru(d) for d in selected)
    await update_menu(
        callback,
        f"✅ <b>Вы в листе ожидания!</b>\n\n"
        f"Выбранные даты: {dates_text}\n\n"
        "Как только появится свободное место — мы вас уведомим.",
        client_main_kb(),
    )
    await callback.answer()


# ─── MY BOOKINGS (UX-2) ───────────────────────────────────────────────────────

async def _bookings_content(master_id: int, user_id: int) -> tuple:
    bookings = await get_client_bookings(master_id, user_id)
    waitlist_entries = await get_client_waitlist(master_id, user_id)

    if not bookings and not waitlist_entries:
        return "📋 У вас нет предстоящих записей и активных листов ожидания.", client_main_kb()

    text = "📋 <b>Ваши записи:</b>\n"
    if bookings:
        text += "\n"
        for b in bookings:
            icon = {"pending": "⏳", "confirmed": "✅"}.get(b["status"], "📌")
            text += f"{icon} {format_date_ru(b['booking_date'])} в {b['booking_time']} — {b['service_name']}\n"
    if waitlist_entries:
        text += "\n🔔 <b>Лист ожидания:</b>\n\n"
        for w in waitlist_entries:
            dl = format_date_ru(w["preferred_date"]) if w.get("preferred_date") else "любая дата"
            text += f"• {w['service_name']} — {dl}\n"
    text += "\n<i>Нажмите на запись, чтобы отменить её:</i>"
    return text, client_bookings_kb(bookings, waitlist_entries)


@router.callback_query(F.data == "c:my_bookings")
async def cb_my_bookings(callback: CallbackQuery, state: FSMContext):
    master_id = await get_client_master_id(state)
    if not master_id:
        await callback.answer("Сессия истекла. Перейди по ссылке мастера заново.", show_alert=True)
        return
    text, kb = await _bookings_content(master_id, callback.from_user.id)
    await update_menu(callback, text, kb)
    await callback.answer()


# ─── CANCEL BOOKING ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("c:cancel_id:"))
async def cb_cancel_select(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[2])
    b = await get_booking(booking_id)
    if not b:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    await update_menu(
        callback,
        f"Отменить запись на <b>{format_date_ru(b['booking_date'])}</b>"
        f" в <b>{b['booking_time']}</b>?\nУслуга: {b['service_name']}",
        confirm_cancel_kb(booking_id),
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
            parse_mode="HTML",
        )
    except Exception:
        pass

    await notify_waitlist(
        callback.bot, b["admin_id"], b["booking_date"],
        exclude_user_id=callback.from_user.id,
    )
    await update_menu(callback, "✅ Запись отменена.", client_main_kb())
    await callback.answer()


# ─── DELETE WAITLIST ENTRY ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("c:del_waitlist:"))
async def cb_del_waitlist(callback: CallbackQuery, state: FSMContext):
    waitlist_id = int(callback.data.split(":")[2])
    await remove_client_waitlist_entry(waitlist_id, callback.from_user.id)
    await callback.answer("✅ Удалено из листа ожидания", show_alert=True)
    master_id = await get_client_master_id(state)
    if master_id:
        text, kb = await _bookings_content(master_id, callback.from_user.id)
        await update_menu(callback, text, kb)


# ─── PROFILE (UX-4) ───────────────────────────────────────────────────────────

async def _build_profile_text(bot, master_id: int, user_id: int) -> tuple:
    client = await get_client(master_id, user_id)
    visit_count = await get_client_visit_count(master_id, user_id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=master_{master_id}"
    try:
        email_val = client["email"]
    except (IndexError, KeyError, TypeError):
        email_val = None
    return (
        f"👤 <b>Мой профиль</b>\n\n"
        f"Имя: <b>{client['name']}</b>\n"
        f"Телефон: <b>{client['phone'] or 'не указан'}</b>\n"
        f"Email: <b>{email_val or 'не указан'}</b>\n"
        f"Всего визитов: <b>{visit_count}</b>\n\n"
        f"🔗 Ваша реферальная ссылка:\n<code>{ref_link}</code>"
    ), bool(email_val)


@router.callback_query(F.data == "c:profile")
async def cb_profile(callback: CallbackQuery, state: FSMContext):
    master_id = await get_client_master_id(state)
    if not master_id:
        await callback.answer("Сессия истекла.", show_alert=True)
        return
    text, has_email = await _build_profile_text(callback.bot, master_id, callback.from_user.id)
    await update_menu(callback, text, profile_kb(has_email))
    await callback.answer()


# — Edit name ——————————————————————————————————————————————————————————————————

@router.callback_query(F.data == "c:edit_name")
async def cb_edit_name(callback: CallbackQuery, state: FSMContext):
    if not await get_client_master_id(state):
        await callback.answer("Сессия истекла.", show_alert=True)
        return
    await update_menu(
        callback,
        "✏️ Введите новое имя:",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="c:profile")]
        ]),
    )
    await state.set_state(ProfileStates.editing_name)
    await callback.answer()


@router.message(ProfileStates.editing_name)
async def process_new_name(message: Message, state: FSMContext):
    master_id = await get_client_master_id(state)
    name = message.text.strip() if message.text else ""
    if len(name) < 2:
        await send_tracked(message, "❌ Имя должно быть не короче 2 символов.")
        return
    await update_client_name(master_id, message.from_user.id, name)
    await state.set_state(None)
    text, has_email = await _build_profile_text(message.bot, master_id, message.from_user.id)
    await send_tracked(message, "✅ Имя обновлено!")
    await send_tracked(message, text, profile_kb(has_email))


# — Edit phone —————————————————————————————————————————————————————————————————

@router.callback_query(F.data == "c:edit_phone")
async def cb_edit_phone(callback: CallbackQuery, state: FSMContext):
    if not await get_client_master_id(state):
        await callback.answer("Сессия истекла.", show_alert=True)
        return
    await update_menu(
        callback,
        "📱 Введите новый номер телефона:",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="c:profile")]
        ]),
    )
    await state.set_state(ProfileStates.editing_phone)
    await callback.answer()


@router.message(ProfileStates.editing_phone)
async def process_new_phone(message: Message, state: FSMContext):
    master_id = await get_client_master_id(state)
    phone = message.text.strip() if message.text else ""
    if len(phone) < 5:
        await send_tracked(message, "❌ Введите корректный номер телефона.")
        return
    await update_client_phone(master_id, message.from_user.id, phone)
    await state.set_state(None)
    text, has_email = await _build_profile_text(message.bot, master_id, message.from_user.id)
    await send_tracked(message, "✅ Номер телефона обновлён!")
    await send_tracked(message, text, profile_kb(has_email))


# — Edit email —————————————————————————————————————————————————————————————————

@router.callback_query(F.data == "c:edit_email")
async def cb_edit_email(callback: CallbackQuery, state: FSMContext):
    if not await get_client_master_id(state):
        await callback.answer("Сессия истекла.", show_alert=True)
        return
    await update_menu(
        callback,
        "📧 Введите email адрес:",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="c:profile")]
        ]),
    )
    await state.set_state(ProfileStates.editing_email)
    await callback.answer()


@router.message(ProfileStates.editing_email)
async def process_new_email(message: Message, state: FSMContext):
    master_id = await get_client_master_id(state)
    email = message.text.strip() if message.text else ""
    if "@" not in email or "." not in email.split("@")[-1]:
        await send_tracked(message, "❌ Введите корректный email (например: user@example.com).")
        return
    await update_client_email(master_id, message.from_user.id, email)
    await state.set_state(None)
    text, has_email = await _build_profile_text(message.bot, master_id, message.from_user.id)
    await send_tracked(message, "✅ Email обновлён!")
    await send_tracked(message, text, profile_kb(has_email))


# ─── ABOUT MASTER (UX-5) ──────────────────────────────────────────────────────

@router.callback_query(F.data == "c:about")
async def cb_about_master(callback: CallbackQuery, state: FSMContext):
    master_id = await get_client_master_id(state)
    if not master_id:
        await callback.answer("Сессия истекла.", show_alert=True)
        return
    master = await get_master(master_id)

    bio = master["bio"] or ""
    address = master["address"] or ""
    lat = master["lat"] or ""
    lon = master["lon"] or ""

    text = f"ℹ️ <b>О мастере {master['name']}</b>\n\n"
    if bio:
        text += f"{bio}\n\n"
    if address:
        text += f"📍 <b>Адрес:</b> {address}\n"
    if not bio and not address:
        text += "Информация о мастере ещё не заполнена."

    await update_menu(callback, text, about_master_kb(master["maps_yandex"] or "", master["maps_2gis"] or ""))

    if lat and lon:
        try:
            await callback.message.answer_location(float(lat), float(lon))
        except Exception:
            pass

    await callback.answer()


# ─── REMINDER RESPONSES ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("r:confirm:"))
async def cb_reminder_confirm(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[2])
    b = await get_booking(booking_id)
    if not b:
        await callback.answer("Запись не найдена.", show_alert=True)
        return
    await confirm_booking(booking_id)
    try:
        await callback.bot.send_message(
            b["admin_id"],
            f"✅ Клиент <b>{b['client_name']}</b> подтвердил запись на "
            f"{format_date_ru(b['booking_date'])} в {b['booking_time']}",
            parse_mode="HTML",
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
        await callback.answer("Запись не найдена.", show_alert=True)
        return
    await cancel_booking(booking_id)
    try:
        await callback.bot.send_message(
            b["admin_id"],
            f"❌ Клиент <b>{b['client_name']}</b> отменил запись на "
            f"{format_date_ru(b['booking_date'])} в {b['booking_time']}",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await notify_waitlist(callback.bot, b["admin_id"], b["booking_date"])
    await callback.message.edit_text("❌ Запись отменена. Жаль, что не получилось!")
    await callback.answer()


# ─── FALLBACK: unknown / stale client callbacks ────────────────────────────────

@router.callback_query(F.data.startswith("c:"))
async def cb_unknown_client(callback: CallbackQuery):
    """
    Catch-all for any c: callback that wasn't matched above.
    Prevents unhandled callback warnings and gives the user a clear message.
    Must be registered LAST in this router.
    """
    await callback.answer(
        "Эта кнопка устарела. Пожалуйста, вернитесь в меню.",
        show_alert=True,
    )
