from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from db.database import (
    get_master, get_services, add_service, delete_service,
    get_master_bookings, get_income_stats, update_master_schedule,
    confirm_booking, complete_booking, cancel_booking, get_booking,
    get_waitlist, remove_from_waitlist,
    update_master_info
)
from keyboards.keyboards import (
    master_close_kb, services_kb, confirm_delete_service_kb,
    bookings_master_kb, booking_actions_master_kb, stats_period_kb,
    waitlist_kb, master_info_kb
)
from utils.states import AddServiceStates, ScheduleStates, MasterInfoStates
from utils.schedule import format_date_ru
from utils.message_manager import manager

router = Router()


async def is_master(user_id: int) -> bool:
    return await get_master(user_id) is not None


# ─── HELPERS ──────────────────────────────────────────────────────────────────

async def _send_master(message: Message, text: str, keyboard=None, parse_mode: str = "HTML") -> None:
    msg = await message.answer(text, parse_mode=parse_mode, reply_markup=keyboard)
    await manager.register(message.bot, msg.chat.id, message.from_user.id, msg.message_id)


async def _show_content(message: Message, text: str, keyboard=None, parse_mode: str = "HTML") -> None:
    """Clear old tracked content, send fresh content message."""
    await manager.clear(message.bot, message.from_user.id)
    await _send_master(message, text, keyboard, parse_mode)


async def _finish_master_fsm(message: Message, text: str, keyboard=None, parse_mode: str = "HTML") -> None:
    """End multi-step FSM: delete all intermediate messages, send clean result."""
    await manager.clear(message.bot, message.from_user.id)
    await _send_master(message, text, keyboard, parse_mode)


# ─── BOTTOM KEYBOARD NAVIGATION ───────────────────────────────────────────────
# Text handlers must be registered BEFORE FSM state handlers so that tapping
# a bottom button always navigates away, even when an FSM flow is in progress.

@router.message(F.text == "💼 Услуги")
async def msg_master_services(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await state.clear()
    services = await get_services(message.from_user.id)
    text = "💼 У тебя пока нет услуг.\nДобавь первую!" if not services else \
           "💼 <b>Твои услуги</b>\n\nНажми на услугу, чтобы удалить её:"
    await _show_content(message, text, services_kb(services))


@router.message(F.text == "📅 Сегодня")
async def msg_master_today(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await state.clear()
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    bookings = await get_master_bookings(message.from_user.id, date=today)
    if not bookings:
        text = f"📅 На сегодня ({format_date_ru(today)}) записей нет."
    else:
        text = f"📅 <b>Записи на сегодня ({format_date_ru(today)}):</b>\n\n"
        for b in bookings:
            icon = {"pending": "⏳", "confirmed": "✅", "completed": "💚", "cancelled": "❌"}.get(b["status"], "❓")
            text += f"{icon} <b>{b['booking_time']}</b> — {b['client_name']}\n"
            text += f"   {b['service_name']} — {b['price']:.0f}₽\n"
            if b["phone"]:
                text += f"   📱 {b['phone']}\n"
            text += "\n"
    await _show_content(message, text, master_close_kb())


@router.message(F.text == "📆 Записи")
async def msg_master_bookings(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await state.clear()
    bookings = await get_master_bookings(message.from_user.id)
    if not bookings:
        await _show_content(message, "📆 Записей пока нет.", master_close_kb())
    else:
        await _show_content(
            message,
            "📆 <b>Все записи:</b>\n\nНажми на запись для управления:",
            bookings_master_kb(bookings),
        )


@router.message(F.text == "💰 Статистика")
async def msg_master_stats(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await state.clear()
    await _show_content(message, "💰 <b>Статистика дохода</b>\n\nВыберите период:", stats_period_kb())


@router.message(F.text == "⏰ Расписание")
async def msg_master_schedule(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await state.clear()
    master = await get_master(message.from_user.id)
    await _show_content(
        message,
        f"⏰ <b>Настройки рабочего времени</b>\n\n"
        f"Текущие: {master['work_start']} — {master['work_end']}, слот {master['slot_duration']} мин\n\n"
        f"Введи начало рабочего дня (формат ЧЧ:ММ, например <code>09:00</code>):",
    )
    await state.set_state(ScheduleStates.waiting_work_start)


@router.message(F.text == "👥 Лист ожидания")
async def msg_master_waitlist(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await state.clear()
    waitlist = await get_waitlist(message.from_user.id)
    if not waitlist:
        await _show_content(message, "👥 Лист ожидания пуст.", master_close_kb())
    else:
        await _show_content(
            message,
            "👥 <b>Лист ожидания</b>\n\nНажми на клиента, чтобы уведомить его:",
            waitlist_kb(waitlist),
        )


@router.message(F.text == "ℹ️ Моя страница")
async def msg_master_my_info(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await state.clear()
    master = await get_master(message.from_user.id)
    await _show_content(message, _info_display(master), master_info_kb())


@router.message(F.text == "🔗 Ссылка")
async def msg_master_link(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await state.clear()
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=master_{message.from_user.id}"
    await _show_content(
        message,
        f"🔗 <b>Твоя ссылка для клиентов:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"Отправь эту ссылку своим клиентам. Перейдя по ней, они автоматически "
        f"попадут в твой кабинет и смогут записаться.",
        master_close_kb(),
    )


# ─── m:back — dismiss content message ─────────────────────────────────────────

@router.callback_query(F.data == "m:back")
async def cb_master_back(callback: CallbackQuery):
    if not await is_master(callback.from_user.id):
        return
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


# ─── SERVICES (inline sub-navigation) ────────────────────────────────────────

@router.callback_query(F.data == "m:services")
async def cb_services(callback: CallbackQuery):
    if not await is_master(callback.from_user.id):
        return
    services = await get_services(callback.from_user.id)
    text = "💼 У тебя пока нет услуг.\nДобавь первую!" if not services else \
           "💼 <b>Твои услуги</b>\n\nНажми на услугу, чтобы удалить её:"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=services_kb(services))
    await callback.answer()


@router.callback_query(F.data == "m:add_service")
async def cb_add_service_start(callback: CallbackQuery, state: FSMContext):
    if not await is_master(callback.from_user.id):
        return
    await callback.message.edit_text("Введи название услуги:")
    await state.set_state(AddServiceStates.waiting_name)
    await callback.answer()


@router.message(AddServiceStates.waiting_name)
async def process_service_name(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await state.update_data(name=message.text.strip())
    await _send_master(message, "Введи цену в рублях (только число, например: 1500):")
    await state.set_state(AddServiceStates.waiting_price)


@router.message(AddServiceStates.waiting_price)
async def process_service_price(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    try:
        price = float(message.text.strip().replace(",", "."))
    except ValueError:
        await _send_master(message, "❌ Введи число, например: 1500")
        return
    await state.update_data(price=price)
    await _send_master(message, "Введи длительность в минутах (например: 60):")
    await state.set_state(AddServiceStates.waiting_duration)


@router.message(AddServiceStates.waiting_duration)
async def process_service_duration(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    try:
        duration = int(message.text.strip())
        if duration <= 0:
            raise ValueError
    except ValueError:
        await _send_master(message, "❌ Введи целое число минут, например: 60")
        return
    data = await state.get_data()
    await add_service(message.from_user.id, data["name"], data["price"], duration)
    await state.clear()
    services = await get_services(message.from_user.id)
    await _finish_master_fsm(
        message,
        f"✅ Услуга <b>{data['name']}</b> добавлена!\n"
        f"Цена: {data['price']:.0f}₽, Длительность: {duration} мин\n\n"
        f"💼 <b>Твои услуги:</b>",
        services_kb(services),
    )


@router.callback_query(F.data.startswith("m:del_service:"))
async def cb_del_service_prompt(callback: CallbackQuery):
    if not await is_master(callback.from_user.id):
        return
    service_id = int(callback.data.split(":")[2])
    from db.database import get_service
    service = await get_service(service_id)
    if not service or service["admin_id"] != callback.from_user.id:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
    await callback.message.edit_text(
        f"Удалить услугу <b>{service['name']}</b>?",
        parse_mode="HTML",
        reply_markup=confirm_delete_service_kb(service_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("m:confirm_del_service:"))
async def cb_confirm_del_service(callback: CallbackQuery):
    if not await is_master(callback.from_user.id):
        return
    service_id = int(callback.data.split(":")[2])
    await delete_service(service_id, callback.from_user.id)
    services = await get_services(callback.from_user.id)
    await callback.message.edit_text(
        "✅ Услуга удалена.\n\n💼 <b>Твои услуги:</b>",
        parse_mode="HTML",
        reply_markup=services_kb(services)
    )
    await callback.answer()


# ─── BOOKINGS ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "m:bookings")
async def cb_all_bookings(callback: CallbackQuery):
    if not await is_master(callback.from_user.id):
        return
    bookings = await get_master_bookings(callback.from_user.id)
    if not bookings:
        await callback.message.edit_text("📆 Записей пока нет.", reply_markup=master_close_kb())
    else:
        await callback.message.edit_text(
            "📆 <b>Все записи:</b>\n\nНажми на запись для управления:",
            parse_mode="HTML",
            reply_markup=bookings_master_kb(bookings)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("m:booking:"))
async def cb_booking_detail(callback: CallbackQuery):
    if not await is_master(callback.from_user.id):
        return
    booking_id = int(callback.data.split(":")[2])
    b = await get_booking(booking_id)
    if not b or b["admin_id"] != callback.from_user.id:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    status_map = {"pending": "⏳ Ожидает", "confirmed": "✅ Подтверждена",
                  "completed": "💚 Выполнена", "cancelled": "❌ Отменена"}
    text = (
        f"📌 <b>Запись #{booking_id}</b>\n\n"
        f"👤 Клиент: {b['client_name']}\n"
        f"📱 Телефон: {b['phone'] or 'не указан'}\n"
        f"✂️ Услуга: {b['service_name']}\n"
        f"💰 Цена: {b['price']:.0f}₽\n"
        f"📅 Дата: {format_date_ru(b['booking_date'])}\n"
        f"⏰ Время: {b['booking_time']}\n"
        f"🔖 Статус: {status_map.get(b['status'], b['status'])}"
    )
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=booking_actions_master_kb(booking_id, b["status"])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("m:confirm:"))
async def cb_confirm_booking(callback: CallbackQuery):
    if not await is_master(callback.from_user.id):
        return
    booking_id = int(callback.data.split(":")[2])
    b = await get_booking(booking_id)
    if not b or b["admin_id"] != callback.from_user.id:
        return
    await confirm_booking(booking_id)
    try:
        await callback.bot.send_message(
            b["client_telegram_id"],
            f"✅ Ваша запись подтверждена мастером!\n\n"
            f"📅 {format_date_ru(b['booking_date'])} в {b['booking_time']}\n"
            f"✂️ {b['service_name']}"
        )
    except Exception:
        pass
    await callback.answer("✅ Запись подтверждена", show_alert=True)
    await cb_all_bookings(callback)


@router.callback_query(F.data.startswith("m:complete:"))
async def cb_complete_booking(callback: CallbackQuery):
    if not await is_master(callback.from_user.id):
        return
    booking_id = int(callback.data.split(":")[2])
    b = await get_booking(booking_id)
    if not b or b["admin_id"] != callback.from_user.id:
        return
    await complete_booking(booking_id)
    await callback.answer("💚 Запись отмечена как выполненная", show_alert=True)
    await cb_all_bookings(callback)


@router.callback_query(F.data.startswith("m:cancel:"))
async def cb_cancel_booking_master(callback: CallbackQuery):
    if not await is_master(callback.from_user.id):
        return
    booking_id = int(callback.data.split(":")[2])
    b = await get_booking(booking_id)
    if not b or b["admin_id"] != callback.from_user.id:
        return
    await cancel_booking(booking_id)
    try:
        await callback.bot.send_message(
            b["client_telegram_id"],
            f"❌ Ваша запись на {format_date_ru(b['booking_date'])} в {b['booking_time']} "
            f"была отменена мастером.\n\nПожалуйста, свяжитесь с мастером для переноса."
        )
    except Exception:
        pass
    from utils.notifications import notify_waitlist
    await notify_waitlist(callback.bot, b["admin_id"], b["booking_date"])
    await callback.answer("❌ Запись отменена", show_alert=True)
    await cb_all_bookings(callback)


# ─── STATS ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("m:stats:"))
async def cb_stats_period(callback: CallbackQuery):
    if not await is_master(callback.from_user.id):
        return
    period = callback.data.split(":")[2]
    stats = await get_income_stats(callback.from_user.id, period)
    period_labels = {"week": "эту неделю", "month": "этот месяц", "year": "этот год"}
    income = stats["total_income"] or 0
    total = stats["total_bookings"] or 0
    clients = stats["unique_clients"] or 0

    if total > 0:
        text = (
            f"💰 <b>Доход за {period_labels.get(period, period)}:</b>\n\n"
            f"💵 Выручка: <b>{income:.0f}₽</b>\n"
            f"✂️ Выполнено записей: <b>{total}</b>\n"
            f"👥 Уникальных клиентов: <b>{clients}</b>\n"
            f"📊 Средний чек: <b>{(income / total):.0f}₽</b>"
        )
    else:
        text = f"💰 <b>Доход за {period_labels.get(period, period)}:</b>\n\nПока нет выполненных записей."

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=stats_period_kb())
    await callback.answer()


# ─── SCHEDULE SETTINGS (FSM) ──────────────────────────────────────────────────

@router.message(ScheduleStates.waiting_work_start)
async def process_work_start(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    try:
        from datetime import datetime
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await _send_master(message, "❌ Формат ЧЧ:ММ, например: 09:00")
        return
    await state.update_data(work_start=message.text.strip())
    await _send_master(message, "Введи конец рабочего дня (формат ЧЧ:ММ, например <code>18:00</code>):", parse_mode="HTML")
    await state.set_state(ScheduleStates.waiting_work_end)


@router.message(ScheduleStates.waiting_work_end)
async def process_work_end(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    try:
        from datetime import datetime
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await _send_master(message, "❌ Формат ЧЧ:ММ, например: 18:00")
        return
    await state.update_data(work_end=message.text.strip())
    await _send_master(message, "Введи длительность одного слота в минутах (например: 60):")
    await state.set_state(ScheduleStates.waiting_slot_duration)


@router.message(ScheduleStates.waiting_slot_duration)
async def process_slot_duration(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    try:
        slot = int(message.text.strip())
        if slot <= 0:
            raise ValueError
    except ValueError:
        await _send_master(message, "❌ Введи целое число, например: 60")
        return
    data = await state.get_data()
    await update_master_schedule(message.from_user.id, data["work_start"], data["work_end"], slot)
    await state.clear()
    await _finish_master_fsm(
        message,
        f"✅ Расписание обновлено!\n"
        f"Рабочий день: {data['work_start']} — {data['work_end']}\n"
        f"Длительность слота: {slot} мин",
    )


# ─── MY INFO PAGE ─────────────────────────────────────────────────────────────

def _info_display(master) -> str:
    def val(v):
        return v if v else "не указано"
    lat = master["lat"] or ""
    lon = master["lon"] or ""
    coords = f"{lat}, {lon}" if lat and lon else "не указаны"
    return (
        f"ℹ️ <b>Ваша страница для клиентов</b>\n\n"
        f"📝 Описание:\n{val(master['bio'])}\n\n"
        f"📍 Адрес: {val(master['address'])}\n"
        f"🗺 Яндекс.Карты: {val(master['maps_yandex'])}\n"
        f"🗺 2ГИС: {val(master['maps_2gis'])}\n"
        f"📌 Координаты: {coords}\n\n"
        f"<i>Нажмите кнопку, чтобы изменить поле:</i>"
    )


@router.callback_query(F.data.startswith("m:info:"))
async def cb_master_info_field(callback: CallbackQuery, state: FSMContext):
    if not await is_master(callback.from_user.id):
        return
    field = callback.data.split(":")[2]
    prompts = {
        "bio":         ("📝 Введите описание (расскажите о себе, опыте, стиле):", MasterInfoStates.editing_bio),
        "address":     ("📍 Введите адрес (например: Москва, ул. Пушкина, д. 10):", MasterInfoStates.editing_address),
        "maps_yandex": ("🗺 Вставьте ссылку на Яндекс.Карты:", MasterInfoStates.editing_maps_yandex),
        "maps_2gis":   ("🗺 Вставьте ссылку на 2ГИС:", MasterInfoStates.editing_maps_2gis),
        "lat_lon":     ("📌 Введите координаты через запятую (широта, долгота)\nПример: <code>55.7558, 37.6173</code>:", MasterInfoStates.editing_lat_lon),
    }
    if field not in prompts:
        await callback.answer()
        return
    prompt, next_state = prompts[field]
    await callback.message.edit_text(prompt, parse_mode="HTML")
    await state.set_state(next_state)
    await callback.answer()


async def _save_info_field(message: Message, state: FSMContext, field: str):
    value = message.text.strip() if message.text else ""
    await update_master_info(message.from_user.id, field, value)
    await state.set_state(None)
    master = await get_master(message.from_user.id)
    await _finish_master_fsm(
        message,
        f"✅ Сохранено!\n\n{_info_display(master)}",
        master_info_kb(),
    )


@router.message(MasterInfoStates.editing_bio)
async def process_master_bio(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await _save_info_field(message, state, "bio")


@router.message(MasterInfoStates.editing_address)
async def process_master_address(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await _save_info_field(message, state, "address")


@router.message(MasterInfoStates.editing_maps_yandex)
async def process_master_maps_yandex(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await _save_info_field(message, state, "maps_yandex")


@router.message(MasterInfoStates.editing_maps_2gis)
async def process_master_maps_2gis(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    await _save_info_field(message, state, "maps_2gis")


@router.message(MasterInfoStates.editing_lat_lon)
async def process_master_lat_lon(message: Message, state: FSMContext):
    if not await is_master(message.from_user.id):
        return
    text = message.text.strip() if message.text else ""
    parts = [p.strip() for p in text.replace(",", " ").split()]
    if len(parts) == 2:
        try:
            lat, lon = float(parts[0]), float(parts[1])
            await update_master_info(message.from_user.id, "lat", str(lat))
            await update_master_info(message.from_user.id, "lon", str(lon))
            await state.set_state(None)
            master = await get_master(message.from_user.id)
            await _finish_master_fsm(
                message,
                f"✅ Координаты сохранены!\n\n{_info_display(master)}",
                master_info_kb(),
            )
            return
        except ValueError:
            pass
    await _send_master(
        message,
        "❌ Неверный формат. Введите два числа через запятую, например: <code>55.7558, 37.6173</code>",
        parse_mode="HTML",
    )


# ─── WAITLIST ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "m:waitlist")
async def cb_waitlist(callback: CallbackQuery):
    if not await is_master(callback.from_user.id):
        return
    waitlist = await get_waitlist(callback.from_user.id)
    if not waitlist:
        await callback.message.edit_text("👥 Лист ожидания пуст.", reply_markup=master_close_kb())
    else:
        await callback.message.edit_text(
            "👥 <b>Лист ожидания</b>\n\nНажми на клиента, чтобы уведомить его:",
            parse_mode="HTML",
            reply_markup=waitlist_kb(waitlist)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("m:notify_waitlist:"))
async def cb_notify_waitlist(callback: CallbackQuery):
    if not await is_master(callback.from_user.id):
        return
    parts = callback.data.split(":")
    waitlist_id = int(parts[2])
    client_tg_id = int(parts[3])
    master = await get_master(callback.from_user.id)
    bot_info = await callback.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=master_{callback.from_user.id}"
    try:
        await callback.bot.send_message(
            client_tg_id,
            f"🎉 <b>Появилось свободное окно!</b>\n\n"
            f"Мастер <b>{master['name']}</b> уведомляет, что появилось свободное время.\n\n"
            f"Перейди по ссылке, чтобы записаться: {link}",
            parse_mode="HTML"
        )
        await remove_from_waitlist(waitlist_id)
        await callback.answer("✅ Клиент уведомлён и удалён из листа ожидания", show_alert=True)
    except Exception:
        await callback.answer("❌ Не удалось отправить сообщение клиенту", show_alert=True)
    await cb_waitlist(callback)
