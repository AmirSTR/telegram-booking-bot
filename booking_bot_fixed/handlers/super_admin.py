from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import SUPER_ADMIN_ID
from db.database import add_master, get_all_masters, remove_master, get_master
from keyboards.keyboards import super_admin_main_kb, masters_list_kb
from utils.states import AddMasterStates

router = Router()


def is_super_admin(user_id: int) -> bool:
    return user_id == SUPER_ADMIN_ID


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_super_admin(message.from_user.id):
        return
    await message.answer(
        "👑 <b>Панель супер-администратора</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=super_admin_main_kb()
    )


@router.callback_query(F.data == "sa:add_master")
async def cb_add_master(callback: CallbackQuery, state: FSMContext):
    if not is_super_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "Введите Telegram ID нового мастера:\n\n"
        "<i>Мастер может узнать свой ID через @userinfobot</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddMasterStates.waiting_telegram_id)
    await callback.answer()


@router.message(AddMasterStates.waiting_telegram_id)
async def process_master_telegram_id(message: Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите числовой Telegram ID")
        return
    await state.update_data(telegram_id=tg_id)
    await message.answer("Введите имя мастера (будет отображаться клиентам):")
    await state.set_state(AddMasterStates.waiting_name)


@router.message(AddMasterStates.waiting_name)
async def process_master_name(message: Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    data = await state.get_data()
    name = message.text.strip()
    tg_id = data["telegram_id"]

    existing = await get_master(tg_id)
    if existing:
        await message.answer("⚠️ Этот мастер уже зарегистрирован!")
        await state.clear()
        return

    await add_master(tg_id, name)
    await state.clear()
    await message.answer(
        f"✅ Мастер <b>{name}</b> добавлен!\n\n"
        f"Telegram ID: <code>{tg_id}</code>\n\n"
        f"Теперь этот пользователь может открыть бота и управлять своими записями.",
        parse_mode="HTML",
        reply_markup=super_admin_main_kb()
    )


@router.callback_query(F.data == "sa:list_masters")
async def cb_list_masters(callback: CallbackQuery):
    if not is_super_admin(callback.from_user.id):
        return
    masters = await get_all_masters()
    if not masters:
        await callback.message.edit_text(
            "Нет зарегистрированных мастеров.",
            reply_markup=super_admin_main_kb()
        )
    else:
        text = "👤 <b>Мастера:</b>\n\n"
        for m in masters:
            text += f"• <b>{m['name']}</b> (ID: <code>{m['telegram_id']}</code>)\n"
            text += f"  Рабочее время: {m['work_start']}–{m['work_end']}, слот {m['slot_duration']} мин\n\n"
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=super_admin_main_kb()
        )
    await callback.answer()


@router.callback_query(F.data == "sa:remove_master")
async def cb_remove_master_list(callback: CallbackQuery):
    if not is_super_admin(callback.from_user.id):
        return
    masters = await get_all_masters()
    if not masters:
        await callback.message.edit_text(
            "Нет мастеров для удаления.", reply_markup=super_admin_main_kb()
        )
    else:
        await callback.message.edit_text(
            "Выберите мастера для удаления:",
            reply_markup=masters_list_kb(masters, action="confirm_remove")
        )
    await callback.answer()


@router.callback_query(F.data.startswith("sa:confirm_remove:"))
async def cb_confirm_remove_master(callback: CallbackQuery):
    if not is_super_admin(callback.from_user.id):
        return
    tg_id = int(callback.data.split(":")[2])
    master = await get_master(tg_id)
    if not master:
        await callback.answer("Мастер не найден", show_alert=True)
        return
    await remove_master(tg_id)
    await callback.message.edit_text(
        f"✅ Мастер <b>{master['name']}</b> удалён.",
        parse_mode="HTML",
        reply_markup=super_admin_main_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "sa:back")
async def cb_sa_back(callback: CallbackQuery):
    if not is_super_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "👑 <b>Панель супер-администратора</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=super_admin_main_kb()
    )
    await callback.answer()
