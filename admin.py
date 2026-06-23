"""
Административная панель — полный функционал с управлением статусом бота
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from html import escape

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatType

from config import OWNER_ID, GROUP_ID, DATA_YEARS
from database import (
    get_current_year, set_year, get_all_users,
    get_registrations, unregister_slot, unregister_user,
    get_user_registration, get_user_by_username,
    conquer_slot, unconquer_slot, get_conquered_slots,
    find_conquered_by_name, is_slot_conquered,
    get_reg_message_id, set_reg_message_id,
    increment_relocations, wipe_all_registrations,
    get_user_data, register_slot, get_users_db, save_users_db,
    get_db, save_db, get_bot_status, set_bot_status
)
from data_loader import (
    find_slot_by_key, get_data_year, reload_caches,
    find_slot_by_name as dl_find_slot_by_name,
    get_slots_for_year
)
from keyboards import admin_panel_kb, year_select_kb, back_to_admin_kb
from messages import build_reg_message
from logger import log_year_change, log_unregister, log_broadcast, log
from premium_emoji import pe

router = Router()
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


class AdminStates(StatesGroup):
    waiting_broadcast = State()
    waiting_remove_id = State()
    waiting_custom_year = State()
    waiting_conquer_name = State()
    waiting_unconquer_name = State()
    waiting_wipe_confirm = State()
    waiting_manual_reg_user = State()
    waiting_manual_reg_slot = State()
    waiting_user_manage_id = State()
    waiting_user_manage_action = State()
    waiting_set_relocations = State()
    waiting_ban_user = State()
    waiting_create_slot_type = State()
    waiting_create_slot_name = State()
    waiting_create_slot_flag = State()


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def esc(text: str) -> str:
    return escape(str(text))


async def _update_reg_msg(bot: Bot, year: int):
    from registration import update_reg_message
    await update_reg_message(bot, year)


# ===================== ВХОД В АДМИНКУ =====================

@router.message(Command("admin"), F.chat.type == ChatType.PRIVATE)
async def cmd_admin(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    await state.clear()

    year = get_current_year()
    data_year = get_data_year(year)
    regs = get_registrations()
    users = get_all_users()
    conquered = get_conquered_slots()
    status = get_bot_status()
    status_text = "🟢 работает" if status == "on" else "🔴 техобслуживание"

    year_info = f"<b>{year}</b>"
    if data_year != year:
        year_info += f" <i>(слоты: {data_year})</i>"

    await message.answer(
        f"{pe('🔧')} <b>Панель администратора</b>\n\n"
        f"{pe('📅')} Текущий год: {year_info}\n"
        f"{pe('👥')} Пользователей в базе: <b>{len(users)}</b>\n"
        f"{pe('📋')} Активных регистраций: <b>{len(regs)}</b>\n"
        f"🏴 Завоёванных слотов: <b>{len(conquered)}</b>\n"
        f"🤖 Статус бота: <b>{status_text}</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )


# ===================== ВОЗВРАТ В АДМИНКУ =====================

@router.callback_query(F.data == "back_admin")
async def back_admin(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return
    await state.clear()

    year = get_current_year()
    data_year = get_data_year(year)
    regs = get_registrations()
    users = get_all_users()
    conquered = get_conquered_slots()
    status = get_bot_status()
    status_text = "🟢 работает" if status == "on" else "🔴 техобслуживание"

    year_info = f"<b>{year}</b>"
    if data_year != year:
        year_info += f" <i>(слоты: {data_year})</i>"

    await callback.message.edit_text(
        f"{pe('🔧')} <b>Панель администратора</b>\n\n"
        f"{pe('📅')} Текущий год: {year_info}\n"
        f"{pe('👥')} Пользователей в базе: <b>{len(users)}</b>\n"
        f"{pe('📋')} Активных регистраций: <b>{len(regs)}</b>\n"
        f"🏴 Завоёванных слотов: <b>{len(conquered)}</b>\n"
        f"🤖 Статус бота: <b>{status_text}</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )
    await callback.answer()


# ===================== ВЫБОР ГОДА =====================

@router.callback_query(F.data == "admin_year")
async def admin_year(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    await callback.message.edit_text(
        f"{pe('📅')} <b>Выбор года вайпа</b>\n\n"
        f"Текущий год: <b>{get_current_year()}</b>\n\n"
        f"Выбери новый год:",
        parse_mode="HTML",
        reply_markup=year_select_kb()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_year_"))
async def set_year_handler(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    new_year = int(callback.data[len("set_year_"):])
    old_year = get_current_year()
    bot = callback.bot

    set_year(new_year)
    reload_caches()
    await log_year_change(bot, callback.from_user.id, old_year, new_year)
    await _update_reg_msg(bot, new_year)

    await callback.message.edit_text(
        f"{pe('✅')} Год изменён: <b>{old_year}</b> → <b>{new_year}</b>\n\n"
        f"Сообщение регистрации обновлено.",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer(f"✅ Год: {new_year}")


@router.callback_query(F.data == "admin_custom_year")
async def admin_custom_year(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    await state.set_state(AdminStates.waiting_custom_year)
    await callback.message.edit_text(
        f"{pe('✏️')} <b>Свой год вайпа</b>\n\n"
        f"Введи год числом (например: <code>1941</code>).\n"
        f"Если для этого года нет данных — бот возьмёт ближайший из "
        f"<code>year_map.txt</code>.",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_custom_year, F.chat.type == ChatType.PRIVATE)
async def handle_custom_year(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    text = message.text.strip()
    if not text.isdigit() or len(text) != 4:
        await message.answer(
            f"{pe('❌')} Введи корректный год (4 цифры, например <code>1941</code>).",
            parse_mode="HTML",
            reply_markup=back_to_admin_kb(),
        )
        return

    new_year = int(text)
    old_year = get_current_year()
    data_year = get_data_year(new_year)
    bot = message.bot

    set_year(new_year)
    reload_caches()
    await log_year_change(bot, message.from_user.id, old_year, new_year)
    await _update_reg_msg(bot, new_year)

    note = ""
    if data_year != new_year:
        note = f"\n{pe('📋')} Слоты берутся из <b>{data_year}</b> (см. year_map.txt)"

    await message.answer(
        f"{pe('✅')} Год изменён: <b>{old_year}</b> → <b>{new_year}</b>{note}\n\nСообщение обновлено.",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )
    await state.clear()


# ===================== ЗАВОЁВАНО / СНЯТЬ ЗАВОЁВАНО =====================

@router.callback_query(F.data == "admin_conquer")
async def admin_conquer(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    conquered = get_conquered_slots()
    conquered_list = ""
    if conquered:
        lines = [f"🏴 {info['slot_flag']} {info['slot_name']}" for info in conquered.values()]
        conquered_list = "\n\nСейчас завоёваны:\n" + "\n".join(lines)

    await state.set_state(AdminStates.waiting_conquer_name)
    await callback.message.edit_text(
        f"🏴 <b>Завоёвано</b>\n\n"
        f"Введи название страны/ЧВК/организации, которую хочешь пометить как завоёванную.\n"
        f"Игроки не смогут её выбрать.{conquered_list}",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


@router.message(AdminStates.waiting_conquer_name, F.chat.type == ChatType.PRIVATE)
async def handle_conquer_name(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    text = message.text.strip()
    year = get_current_year()
    data_year = get_data_year(year)
    bot = message.bot

    slot = dl_find_slot_by_name(text, data_year)
    if not slot:
        all_slots = get_slots_for_year(data_year)
        slot = next((s for s in all_slots if text.lower() in s["name"].lower()), None)

    if not slot:
        await message.answer(
            f"{pe('❓')} Не нашёл слот <b>{esc(text)}</b>.\nПроверь написание.",
            parse_mode="HTML",
            reply_markup=back_to_admin_kb()
        )
        return

    if is_slot_conquered(slot["key"]):
        await message.answer(
            f"{pe('⚠️')} <b>{esc(slot['flag'])} {esc(slot['name'])}</b> уже завоёвана.",
            parse_mode="HTML",
            reply_markup=admin_panel_kb()
        )
        await state.clear()
        return

    conquer_slot(slot["key"], slot["name"], slot["flag"])
    await _update_reg_msg(bot, year)

    await message.answer(
        f"🏴 <b>{esc(slot['flag'])} {esc(slot['name'])}</b> помечена как завоёванная.",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )
    await state.clear()


@router.callback_query(F.data == "admin_unconquer")
async def admin_unconquer(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    conquered = get_conquered_slots()
    if not conquered:
        await callback.answer("Нет завоёванных слотов!", show_alert=True)
        return

    lines = [f"🏴 {info['slot_flag']} {info['slot_name']}" for info in conquered.values()]
    conquered_list = "\n".join(lines)

    await state.set_state(AdminStates.waiting_unconquer_name)
    await callback.message.edit_text(
        f"{pe('✅')} <b>Снять метку завоёвано</b>\n\n"
        f"Текущие завоёванные:\n{conquered_list}\n\nВведи название слота для снятия:",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


@router.message(AdminStates.waiting_unconquer_name, F.chat.type == ChatType.PRIVATE)
async def handle_unconquer_name(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    text = message.text.strip()
    year = get_current_year()
    bot = message.bot

    result = find_conquered_by_name(text)
    if not result:
        await message.answer(
            f"{pe('❓')} Не нашёл завоёванный слот <b>{esc(text)}</b>.",
            parse_mode="HTML",
            reply_markup=back_to_admin_kb()
        )
        return

    slot_key, info = result
    unconquer_slot(slot_key)
    await _update_reg_msg(bot, year)

    await message.answer(
        f"{pe('✅')} Метка снята с <b>{esc(info['slot_flag'])} {esc(info['slot_name'])}</b>.",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )
    await state.clear()


# ===================== СПИСОК ПОЛЬЗОВАТЕЛЕЙ =====================

@router.message(Command("users"), F.chat.type == ChatType.PRIVATE)
async def cmd_users(message: Message):
    if not is_owner(message.from_user.id):
        return

    users = get_all_users()
    if not users:
        await message.answer("👥 Нет пользователей в базе.")
        return

    lines = [
        "Rise of Europe — Список пользователей",
        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        "=" * 50, ""
    ]

    for u in users:
        reg = get_user_registration(u["user_id"])
        reg_info = f"Позиция: {reg['slot_flag']} {reg['slot_name']}" if reg else "Позиция: нет"
        lines.extend([
            f"ID: {u['user_id']}",
            f"Имя: {u.get('full_name', 'нет')}",
            f"Юзернейм: @{u.get('username', 'нет')}",
            f"Первый вход: {u.get('first_seen', 'неизвестно')}",
            f"Последний вход: {u.get('last_seen', 'неизвестно')}",
            f"Пересадок: {u.get('relocations', 0)}",
            reg_info,
            "-" * 30
        ])

    content = "\n".join(lines)
    file = BufferedInputFile(content.encode("utf-8"), filename="users.txt")
    await message.answer_document(file, caption=f"👥 Пользователей: {len(users)}")


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    users = get_all_users()
    if not users:
        await callback.answer("👥 Нет пользователей в базе.", show_alert=True)
        return

    lines = [
        "Rise of Europe — Список пользователей",
        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        "=" * 50, ""
    ]

    for u in users:
        reg = get_user_registration(u["user_id"])
        reg_info = f"Позиция: {reg['slot_flag']} {reg['slot_name']}" if reg else "Позиция: нет"
        lines.extend([
            f"ID: {u['user_id']}",
            f"Имя: {u.get('full_name', 'нет')}",
            f"Юзернейм: @{u.get('username', 'нет')}",
            f"Первый вход: {u.get('first_seen', 'неизвестно')}",
            f"Последний вход: {u.get('last_seen', 'неизвестно')}",
            f"Пересадок: {u.get('relocations', 0)}",
            reg_info,
            "-" * 30
        ])

    content = "\n".join(lines)
    file = BufferedInputFile(content.encode("utf-8"), filename="users.txt")
    await callback.message.answer_document(file, caption=f"👥 Пользователей: {len(users)}")
    await callback.answer()


# ===================== РАССЫЛКА =====================

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    await state.set_state(AdminStates.waiting_broadcast)
    await callback.message.edit_text(
        f"{pe('📢')} <b>Рассылка</b>\n\nНапиши текст сообщения для рассылки всем пользователям:",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


@router.message(AdminStates.waiting_broadcast, F.chat.type == ChatType.PRIVATE)
async def handle_broadcast(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    bot = message.bot
    text = message.text
    users = get_all_users()

    sent = 0
    failed = 0

    status_msg = await message.answer(f"📢 Рассылка начата... 0/{len(users)}")

    for user in users:
        try:
            await bot.send_message(
                chat_id=user["user_id"],
                text=f"📢 <b>Объявление от Rise of Europe:</b>\n\n{esc(text)}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

        if (sent + failed) % 10 == 0:
            try:
                await status_msg.edit_text(f"📢 Рассылка... {sent + failed}/{len(users)}")
            except Exception:
                pass

    await log_broadcast(bot, message.from_user.id, text, sent)

    await status_msg.edit_text(
        f"{pe('✅')} Рассылка завершена!\n"
        f"{pe('📩')} Отправлено: <b>{sent}</b>\n"
        f"{pe('❌')} Не доставлено: <b>{failed}</b>",
        parse_mode="HTML"
    )
    await state.clear()


# ===================== СНЯТИЕ ПОЛЬЗОВАТЕЛЯ =====================

@router.callback_query(F.data == "admin_remove")
async def admin_remove(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    await state.set_state(AdminStates.waiting_remove_id)
    await callback.message.edit_text(
        f"{pe('🗑️')} <b>Снятие пользователя</b>\n\nВведи ID, @юзернейм или название страны/позиции:",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


@router.message(AdminStates.waiting_remove_id, F.chat.type == ChatType.PRIVATE)
async def handle_remove_id(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    bot = message.bot
    text = message.text.strip()
    year = get_current_year()

    removed = None
    removed_user_id = None

    if text.isdigit():
        uid = int(text)
        reg = get_user_registration(uid)
        if reg:
            removed = unregister_slot(reg["slot_key"])
            removed_user_id = uid
    else:
        username = text.lstrip("@")
        user_data = get_user_by_username(username)
        if user_data:
            reg = get_user_registration(user_data["user_id"])
            if reg:
                removed = unregister_slot(reg["slot_key"])
                removed_user_id = user_data["user_id"]

        if not removed:
            slot = dl_find_slot_by_name(text, year)
            if slot:
                reg = get_registrations().get(slot["key"])
                if reg:
                    removed = unregister_slot(slot["key"])
                    removed_user_id = reg.get("user_id")

    if removed:
        slot_name = removed.get("slot_name", "?")
        user_name = removed.get("full_name", "?")

        await log_unregister(
            bot, removed_user_id or 0,
            removed.get("username", ""),
            user_name, slot_name, by_admin=True
        )
        await _update_reg_msg(bot, year)

        if removed_user_id:
            try:
                await bot.send_message(
                    chat_id=removed_user_id,
                    text=f"{pe('⚠️')} Администрация сняла вас с позиции <b>{esc(slot_name)}</b>.",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        await message.answer(
            f"{pe('✅')} Снят с <b>{esc(slot_name)}</b>: <code>{esc(user_name)}</code>",
            parse_mode="HTML",
            reply_markup=admin_panel_kb()
        )
    else:
        await message.answer(
            f"{pe('❌')} Пользователь не зарегистрирован или не найден.",
            parse_mode="HTML",
            reply_markup=admin_panel_kb()
        )

    await state.clear()


# ===================== РУЧНАЯ РЕГИСТРАЦИЯ =====================

@router.callback_query(F.data == "admin_manual_reg")
async def admin_manual_reg(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    await state.set_state(AdminStates.waiting_manual_reg_user)
    await callback.message.edit_text(
        f"👤 <b>Ручная регистрация</b>\n\nВведи ID или @юзернейм игрока:",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


@router.message(AdminStates.waiting_manual_reg_user, F.chat.type == ChatType.PRIVATE)
async def handle_manual_reg_user(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    text = message.text.strip()

    if text.isdigit():
        user_id = int(text)
        user_data = get_user_data(user_id)
        if not user_data:
            user_data = {"user_id": user_id, "username": "", "full_name": str(user_id)}
    else:
        uname = text.lstrip("@")
        user_data = get_user_by_username(uname)
        if not user_data:
            await message.answer(
                f"❌ Пользователь <code>{esc(text)}</code> не найден.\nПопробуй числовой ID.",
                parse_mode="HTML",
                reply_markup=back_to_admin_kb()
            )
            return

    await state.update_data(
        manual_user_id=user_data["user_id"],
        manual_username=user_data.get("username", ""),
        manual_full_name=user_data.get("full_name", str(user_data["user_id"]))
    )
    await state.set_state(AdminStates.waiting_manual_reg_slot)

    display = f"@{user_data['username']}" if user_data.get("username") else str(user_data["user_id"])
    fn = esc(user_data.get("full_name", str(user_data["user_id"])))

    await message.answer(
        f"✅ Игрок: <b>{fn}</b> ({display})\n\n"
        f"Введи название позиции для регистрации (например: Польша / ЧВК Вагнер / МО России):",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )


@router.message(AdminStates.waiting_manual_reg_slot, F.chat.type == ChatType.PRIVATE)
async def handle_manual_reg_slot(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    text = message.text.strip()
    year = get_current_year()
    data_year = get_data_year(year)
    bot = message.bot

    slot = dl_find_slot_by_name(text, data_year)
    if not slot:
        all_slots = get_slots_for_year(data_year)
        slot = next((s for s in all_slots if text.lower() in s["name"].lower()), None)

    if not slot:
        # Создаём кастомный слот
        slot = {
            "key": f"manual_{uuid.uuid4().hex[:8]}",
            "name": text,
            "type": "other",
            "flag": "🏳️",
            "year": data_year,
            "superpower": False,
        }

    data = await state.get_data()
    user_id = data["manual_user_id"]
    username = data["manual_username"]
    full_name = data["manual_full_name"]

    # Снимаем, если уже зарегистрирован
    current = get_user_registration(user_id)
    if current:
        unregister_slot(current["slot_key"])

    register_slot(
        slot_key=slot["key"],
        user_id=user_id,
        username=username,
        full_name=full_name,
        slot_info=slot
    )

    await _update_reg_msg(bot, year)

    display = f"@{username}" if username else str(user_id)
    await message.answer(
        f"✅ <b>Ручная регистрация выполнена!</b>\n\n"
        f"👤 Игрок: {esc(full_name)} ({display})\n"
        f"📍 Позиция: <b>{esc(slot['flag'])} {esc(slot['name'])}</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )

    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"📍 Администрация зарегистрировала вас за:\n<b>{esc(slot['flag'])} {esc(slot['name'])}</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await state.clear()


# ===================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЕМ =====================

@router.callback_query(F.data == "admin_user_manage")
async def admin_user_manage(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    await state.set_state(AdminStates.waiting_user_manage_id)
    await callback.message.edit_text(
        f"{pe('🔧')} <b>Управление пользователем</b>\n\n"
        f"Введи ID или @юзернейм пользователя:",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


@router.message(AdminStates.waiting_user_manage_id, F.chat.type == ChatType.PRIVATE)
async def handle_user_manage_id(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    text = message.text.strip()
    user_data = None

    if text.isdigit():
        user_id = int(text)
        user_data = get_user_data(user_id)
        if not user_data:
            user_data = {"user_id": user_id, "username": "", "full_name": str(user_id)}
    else:
        uname = text.lstrip("@")
        user_data = get_user_by_username(uname)

    if not user_data:
        await message.answer(
            f"❌ Пользователь не найден.",
            parse_mode="HTML",
            reply_markup=back_to_admin_kb()
        )
        return

    user_id = user_data["user_id"]
    username = user_data.get("username", "")
    full_name = user_data.get("full_name", str(user_id))
    relocations = user_data.get("relocations", 0)

    reg = get_user_registration(user_id)
    reg_info = f"{reg['slot_flag']} {reg['slot_name']}" if reg else "не зарегистрирован"

    await state.update_data(manage_user_id=user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Изменить пересадки", callback_data="manage_set_relo")],
            [InlineKeyboardButton(text="🚫 Забанить", callback_data="manage_ban")],
            [InlineKeyboardButton(text="🔓 Разбанить", callback_data="manage_unban")],
            [InlineKeyboardButton(text="🗑️ Снять с позиции", callback_data="manage_unreg")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin")]
        ]
    )

    await message.answer(
        f"{pe('👤')} <b>Информация о пользователе</b>\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Имя: {esc(full_name)}\n"
        f"Юзернейм: @{username or 'нет'}\n"
        f"Пересадок: <b>{relocations}</b>\n"
        f"Позиция: <b>{esc(reg_info)}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await state.clear()


@router.callback_query(F.data == "manage_set_relo")
async def manage_set_relo(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    data = await state.get_data()
    user_id = data.get("manage_user_id")
    if not user_id:
        await callback.answer("❌ Ошибка: пользователь не выбран", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_set_relocations)
    await callback.message.answer(
        f"✏️ Введи новое количество пересадок для пользователя <code>{user_id}</code>:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.waiting_set_relocations, F.chat.type == ChatType.PRIVATE)
async def handle_set_relocations(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Введи целое число.")
        return

    data = await state.get_data()
    user_id = data.get("manage_user_id")
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не выбран.")
        return

    new_count = int(text)
    users_db = get_users_db()
    uid = str(user_id)
    if uid not in users_db:
        users_db[uid] = {"user_id": user_id, "username": "", "full_name": str(user_id), "relocations": 0}
    users_db[uid]["relocations"] = new_count
    save_users_db(users_db)

    await message.answer(
        f"✅ Количество пересадок для <code>{user_id}</code> установлено: <b>{new_count}</b>",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await state.clear()


@router.callback_query(F.data == "manage_ban")
async def manage_ban(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    data = await state.get_data()
    user_id = data.get("manage_user_id")
    if not user_id:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    db = get_db()
    if "banned" not in db:
        db["banned"] = []
    if user_id not in db["banned"]:
        db["banned"].append(user_id)
    save_db(db)

    await callback.message.answer(
        f"🚫 Пользователь <code>{user_id}</code> забанен (не сможет регистрироваться).",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "manage_unban")
async def manage_unban(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    data = await state.get_data()
    user_id = data.get("manage_user_id")
    if not user_id:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    db = get_db()
    if "banned" in db and user_id in db["banned"]:
        db["banned"].remove(user_id)
        save_db(db)

    await callback.message.answer(
        f"🔓 Пользователь <code>{user_id}</code> разбанен.",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "manage_unreg")
async def manage_unreg(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    data = await state.get_data()
    user_id = data.get("manage_user_id")
    if not user_id:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    reg = get_user_registration(user_id)
    if not reg:
        await callback.message.answer("❌ Пользователь не зарегистрирован.")
        return

    removed = unregister_slot(reg["slot_key"])
    if removed:
        await _update_reg_msg(callback.bot, get_current_year())
        await callback.message.answer(
            f"✅ Снят с позиции <b>{esc(removed['slot_name'])}</b>",
            parse_mode="HTML",
            reply_markup=back_to_admin_kb()
        )
    else:
        await callback.message.answer("❌ Ошибка снятия.")
    await callback.answer()


# ===================== СОЗДАНИЕ КАСТОМНОГО СЛОТА =====================

@router.callback_query(F.data == "admin_create_slot")
async def admin_create_slot(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    await state.set_state(AdminStates.waiting_create_slot_type)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏳️ Страна", callback_data="create_type_country")],
            [InlineKeyboardButton(text="🛡️ ЧВК", callback_data="create_type_pmc")],
            [InlineKeyboardButton(text="⚔️ МО", callback_data="create_type_mo")],
            [InlineKeyboardButton(text="🤝 Вице", callback_data="create_type_vice")],
            [InlineKeyboardButton(text="💣 Террор", callback_data="create_type_terror")],
            [InlineKeyboardButton(text="🌐 Иное", callback_data="create_type_other")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin")],
        ]
    )
    await callback.message.edit_text(
        f"➕ <b>Создание кастомного слота</b>\n\nВыбери тип слота:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("create_type_"))
async def create_slot_type(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    slot_type = callback.data[len("create_type_"):]
    await state.update_data(create_slot_type=slot_type)
    await state.set_state(AdminStates.waiting_create_slot_name)

    await callback.message.edit_text(
        f"Введи название нового слота (например: \"Новая республика\"):",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


@router.message(AdminStates.waiting_create_slot_name, F.chat.type == ChatType.PRIVATE)
async def create_slot_name(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    name = message.text.strip()
    await state.update_data(create_slot_name=name)
    await state.set_state(AdminStates.waiting_create_slot_flag)

    await message.answer(
        f"Введи флаг для слота (эмодзи, например 🇺🇦):",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )


@router.message(AdminStates.waiting_create_slot_flag, F.chat.type == ChatType.PRIVATE)
async def create_slot_flag(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    flag = message.text.strip()
    data = await state.get_data()
    slot_type = data.get("create_slot_type", "other")
    name = data.get("create_slot_name", "Новый слот")
    year = get_current_year()
    data_year = get_data_year(year)

    key = f"custom_{uuid.uuid4().hex[:8]}"

    with open("data/countries.txt", "a", encoding="utf-8") as f:
        f.write(f"\n{data_year}|{slot_type}|{flag}|{name}|нет")

    reload_caches()

    await message.answer(
        f"✅ <b>Слот создан!</b>\n\n"
        f"Тип: {slot_type}\n"
        f"Название: {flag} {esc(name)}\n"
        f"Год: {data_year}\n\n"
        f"Слот добавлен в countries.txt",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )
    await state.clear()


# ===================== ОБНОВИТЬ СООБЩЕНИЕ =====================

@router.callback_query(F.data == "admin_update_msg")
async def admin_update_msg(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    year = get_current_year()
    await _update_reg_msg(callback.bot, year)
    await callback.answer("✅ Сообщение обновлено!", show_alert=True)


# ===================== СТАТИСТИКА =====================

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    year = get_current_year()
    regs = get_registrations()
    users = get_all_users()
    conquered = get_conquered_slots()

    type_counts = {}
    for reg in regs.values():
        t = reg.get("slot_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    type_labels = {
        "country": "🏳️ Страны",
        "superpower": "👑 Сверхдержавы",
        "pmc": "🛡️ ЧВК",
        "mo": "⚔️ МО",
        "vice": "🤝 Вице",
        "terror": "💣 Терроризм",
        "other": "🌐 Иное",
        "unknown": "❓ Неизвестно",
    }

    stats_lines = []
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        label = type_labels.get(t, t)
        stats_lines.append(f"  {label}: <b>{c}</b>")

    stats_text = "\n".join(stats_lines) if stats_lines else "  Нет регистраций"

    await callback.message.edit_text(
        f"{pe('📊')} <b>Статистика Rise of Europe</b>\n\n"
        f"{pe('📅')} Текущий год: <b>{year}</b>\n"
        f"{pe('👥')} Всего пользователей: <b>{len(users)}</b>\n"
        f"{pe('📋')} Активных регистраций: <b>{len(regs)}</b>\n"
        f"🏴 Завоёванных слотов: <b>{len(conquered)}</b>\n\n"
        f"По типам:\n{stats_text}",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


# ===================== ПОСМОТРЕТЬ ЛОГИ =====================

@router.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    log_file = "data/bot.log"
    if not os.path.exists(log_file):
        await callback.message.answer("❌ Лог-файл не найден.", reply_markup=back_to_admin_kb())
        return

    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()[-50:]

    content = "".join(lines)
    if len(content) > 4000:
        content = content[-4000:]

    file = BufferedInputFile(content.encode("utf-8"), filename="bot.log")
    await callback.message.answer_document(
        file,
        caption=f"📜 Последние 50 строк лога ({datetime.now().strftime('%d.%m.%Y %H:%M')})",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


# ===================== ПЕРЕЗАГРУЗИТЬ КЭШ =====================

@router.callback_query(F.data == "admin_reload_cache")
async def admin_reload_cache(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    reload_caches()
    await callback.message.edit_text(
        f"✅ Кэш данных перезагружен!",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )
    await callback.answer("✅ Кэш обновлён!")


# ===================== СБРОС ВСЕХ РЕГИСТРАЦИЙ =====================

@router.callback_query(F.data == "admin_wipe_regs")
async def admin_wipe_regs(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    regs = get_registrations()
    count = len(regs)

    await state.set_state(AdminStates.waiting_wipe_confirm)
    await callback.message.edit_text(
        f"⚠️ <b>СБРОС ВСЕХ РЕГИСТРАЦИЙ</b>\n\n"
        f"Сейчас зарегистрировано: <b>{count}</b> игроков\n\n"
        f"❗ Это действие:\n"
        f"▪️ Удалит ВСЕ регистрации\n"
        f"▪️ Обнулит счётчики пересадок у всех\n"
        f"▪️ Обновит сообщение в теме\n\n"
        f"Для подтверждения напиши точно:\n<code>СБРОС</code>",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


@router.message(AdminStates.waiting_wipe_confirm, F.chat.type == ChatType.PRIVATE)
async def handle_wipe_confirm(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    if message.text.strip() != "СБРОС":
        await message.answer(
            f"❌ Неверное слово. Напиши точно: <code>СБРОС</code>\n"
            f"Или нажми «В админ-панель» для отмены.",
            parse_mode="HTML",
            reply_markup=back_to_admin_kb()
        )
        return

    count = wipe_all_registrations()
    year = get_current_year()
    bot = message.bot

    await _update_reg_msg(bot, year)

    await message.answer(
        f"✅ <b>Сброс выполнен!</b>\n\n"
        f"🗑️ Удалено регистраций: <b>{count}</b>\n"
        f"🔄 Счётчики пересадок: обнулены\n"
        f"📋 Сообщение регистрации: обновлено",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )
    await state.clear()
    log.info(f"Владелец сбросил все регистрации. Удалено: {count}")


# ===================== ВЫКЛЮЧЕНИЕ БОТА (ТЕХОБСЛУЖИВАНИЕ) =====================

@router.callback_query(F.data == "admin_shutdown")
async def admin_shutdown(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, выключить", callback_data="shutdown_confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="back_admin"),
            ]
        ]
    )

    await callback.message.edit_text(
        f"🛑 <b>Выключение бота (техобслуживание)</b>\n\n"
        f"Вы уверены, что хотите выключить бота?\n"
        f"Все пользователи получат уведомление о техническом обслуживании.\n\n"
        f"Бот перестанет отвечать на команды, пока вы не включите его снова.",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "shutdown_confirm")
async def shutdown_confirm(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    # Устанавливаем статус OFF
    set_bot_status("off")

    # Рассылаем уведомление
    users = get_all_users()
    sent = 0
    for user in users:
        try:
            await callback.bot.send_message(
                chat_id=user["user_id"],
                text="🔧 <b>Бот временно отключён на техническое обслуживание.</b>\n\nМы скоро вернёмся!",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)

    await callback.message.edit_text(
        f"🛑 <b>Бот выключен</b>\n\n"
        f"Уведомлено пользователей: {sent}\n"
        f"Теперь бот не отвечает на команды.\n"
        f"Чтобы включить, нажмите «Включить бота» в админ-панели.",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )
    await callback.answer("Бот выключен")


# ===================== ВКЛЮЧЕНИЕ БОТА =====================

@router.callback_query(F.data == "admin_start_bot")
async def admin_start_bot(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    # Устанавливаем статус ON
    set_bot_status("on")

    # Рассылаем уведомление
    users = get_all_users()
    sent = 0
    for user in users:
        try:
            await callback.bot.send_message(
                chat_id=user["user_id"],
                text="🟢 <b>Бот снова работает!</b>\n\n"
                     "Техническое обслуживание завершено.\n"
                     "Все функции доступны. Приятной игры!",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)

    # Обновляем сообщение регистрации
    await _update_reg_msg(callback.bot, get_current_year())

    await callback.message.edit_text(
        f"✅ <b>Бот включён</b>\n\n"
        f"Уведомлено пользователей: {sent}\n"
        f"Бот снова отвечает на команды.",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )
    await callback.answer("Бот включён")


# ===================== КОМАНДА В ГРУППЕ !снятие =====================

@router.message(F.text.lower().startswith("!снятие"))
async def group_remove_command(message: Message):
    if message.chat.id != GROUP_ID:
        return
    if message.from_user.id != OWNER_ID:
        return

    bot = message.bot
    year = get_current_year()
    target_user_id = None
    target_name = "?"

    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        if target_user:
            target_user_id = target_user.id
            target_name = target_user.full_name
    else:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            arg = parts[1].strip()
            if arg.isdigit():
                target_user_id = int(arg)
            elif arg.startswith("@"):
                udata = get_user_by_username(arg.lstrip("@"))
                if udata:
                    target_user_id = udata["user_id"]
                    target_name = udata.get("full_name", "?")
            else:
                slot = dl_find_slot_by_name(arg, year)
                if slot:
                    reg = get_registrations().get(slot["key"])
                    if reg:
                        removed = unregister_slot(slot["key"])
                        if removed:
                            await log_unregister(
                                bot,
                                reg.get("user_id", 0),
                                removed.get("username", ""),
                                removed.get("full_name", "?"),
                                removed.get("slot_name", "?"),
                                by_admin=True
                            )
                            await _update_reg_msg(bot, year)
                            await message.reply(
                                f"✅ Снял с <b>{esc(removed.get('slot_name', '?'))}</b>",
                                parse_mode="HTML"
                            )
                        else:
                            await message.reply("❌ Пользователь не зарегистрирован")
                        return

    if target_user_id:
        reg = get_user_registration(target_user_id)
        if reg:
            slot_name = reg["slot_name"]
            removed = unregister_slot(reg["slot_key"])
            if removed:
                await log_unregister(
                    bot,
                    target_user_id,
                    removed.get("username", ""),
                    removed.get("full_name", target_name),
                    slot_name,
                    by_admin=True
                )
                await _update_reg_msg(bot, year)
                await message.reply(f"✅ Снял с <b>{esc(slot_name)}</b>", parse_mode="HTML")
                try:
                    await bot.send_message(
                        chat_id=target_user_id,
                        text=f"{pe('⚠️')} Администрация сняла вас с позиции <b>{esc(slot_name)}</b>.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        else:
            await message.reply("❌ Пользователь не зарегистрирован")
    else:
        await message.reply(
            "❌ Не удалось определить пользователя\n\n"
            "Использование:\n"
            "<code>!снятие</code> — в ответ на сообщение\n"
            "<code>!снятие @юзернейм</code>\n"
            "<code>!снятие 123456789</code>\n"
            "<code>!снятие Польша</code>",
            parse_mode="HTML"
        )
