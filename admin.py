"""
Обработчики команд администратора
"""

import io
from html import escape
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatType

from config import OWNER_ID, DATA_YEARS, GROUP_ID, TOPIC_ID
from database import (
    get_current_year, set_year, get_all_users,
    get_registrations, find_slot_by_name, unregister_slot,
    unregister_user, get_user_registration, get_user_by_username,
    conquer_slot, unconquer_slot, get_conquered_slots,
    find_conquered_by_name, is_slot_conquered,
    get_reg_message_id, set_reg_message_id, increment_relocations
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

group_admin_router = Router()


class AdminStates(StatesGroup):
    waiting_broadcast = State()
    waiting_remove_id = State()
    waiting_remove_confirm = State()
    waiting_custom_year = State()
    waiting_conquer_name = State()
    waiting_unconquer_name = State()


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def esc(text: str) -> str:
    return escape(str(text))


async def _update_reg_msg(bot, year: int):
    """Вспомогательная функция обновления сообщения регистрации из admin."""
    from registration import update_reg_message
    await update_reg_message(bot, year)


# ===================== ADMIN ПАНЕЛЬ =====================

@router.message(Command("admin"), F.chat.type == ChatType.PRIVATE)
async def cmd_admin(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    await state.clear()

    year = get_current_year()
    regs = get_registrations()
    users = get_all_users()
    conquered = get_conquered_slots()

    await message.answer(
        f"{pe('🔧')} <b>Панель администратора</b>\n\n"
        f"{pe('📅')} Текущий вайп: <b>{year}</b>\n"
        f"{pe('👥')} Пользователей в базе: <b>{len(users)}</b>\n"
        f"{pe('📋')} Активных регистраций: <b>{len(regs)}</b>\n"
        f"🏴 Завоёванных слотов: <b>{len(conquered)}</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb()
    )


@router.callback_query(F.data == "back_admin")
async def back_admin(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return
    await state.clear()

    year = get_current_year()
    regs = get_registrations()
    users = get_all_users()
    conquered = get_conquered_slots()

    await callback.message.edit_text(
        f"{pe('🔧')} <b>Панель администратора</b>\n\n"
        f"{pe('📅')} Текущий вайп: <b>{year}</b>\n"
        f"{pe('👥')} Пользователей в базе: <b>{len(users)}</b>\n"
        f"{pe('📋')} Активных регистраций: <b>{len(regs)}</b>\n"
        f"🏴 Завоёванных слотов: <b>{len(conquered)}</b>",
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

    year = get_current_year()
    await callback.message.edit_text(
        f"{pe('📅')} <b>Выбор года вайпа</b>\n\n"
        f"Текущий год: <b>{year}</b>\n\nВыбери новый год:",
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
        f"{pe('✅')} Год успешно изменён: <b>{old_year}</b> → <b>{new_year}</b>\n\n"
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
        f"Введи год числом (например: 1941).\n"
        f"Если для этого года нет данных, бот возьмёт ближайший из "
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
            f"{pe('❌')} Введи корректный год (4 цифры, например 1941).",
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
        note = (
            f"\n{pe('📋')} Слоты берутся из <b>{data_year}</b> "
            f"(см. <code>data/year_map.txt</code>)"
        )

    await message.answer(
        f"{pe('✅')} Год изменён: <b>{old_year}</b> → <b>{new_year}</b>"
        f"{note}\n\nСообщение регистрации обновлено.",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )
    await state.clear()


# ===================== ЗАВОЁВАНО =====================

@router.callback_query(F.data == "admin_conquer")
async def admin_conquer(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    conquered = get_conquered_slots()
    conquered_list = ""
    if conquered:
        lines = [
            f"🏴 {info['slot_flag']} {info['slot_name']}"
            for info in conquered.values()
        ]
        conquered_list = "\n\nСейчас завоёваны:\n" + "\n".join(lines)

    await state.set_state(AdminStates.waiting_conquer_name)
    await callback.message.edit_text(
        f"🏴 <b>Завоёвано</b>\n\n"
        f"Введи название страны, ЧВК или организации, "
        f"которую хочешь пометить как завоёванную.\n"
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
        slot = next(
            (s for s in all_slots if text.lower() in s["name"].lower()),
            None
        )

    if not slot:
        await message.answer(
            f"{pe('❓')} Не нашёл слот <b>{esc(text)}</b>.\n"
            f"Проверь правильность написания.",
            parse_mode="HTML",
            reply_markup=back_to_admin_kb()
        )
        return

    if is_slot_conquered(slot["key"]):
        await message.answer(
            f"{pe('⚠️')} <b>{esc(slot['flag'])} {esc(slot['name'])}</b> "
            f"уже помечена как завоёванная.",
            parse_mode="HTML",
            reply_markup=admin_panel_kb()
        )
        await state.clear()
        return

    conquer_slot(slot["key"], slot["name"], slot["flag"])
    await _update_reg_msg(bot, year)

    await message.answer(
        f"🏴 <b>{esc(slot['flag'])} {esc(slot['name'])}</b> помечена как завоёванная.\n"
        f"Игроки не смогут её выбрать.",
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

    lines = [
        f"🏴 {info['slot_flag']} {info['slot_name']}"
        for info in conquered.values()
    ]
    conquered_list = "\n".join(lines)

    await state.set_state(AdminStates.waiting_unconquer_name)
    await callback.message.edit_text(
        f"{pe('✅')} <b>Снять метку завоёвано</b>\n\n"
        f"Текущие завоёванные слоты:\n{conquered_list}\n\n"
        f"Введи название слота для снятия метки:",
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
        f"{pe('✅')} Метка завоёвано снята с "
        f"<b>{esc(info['slot_flag'])} {esc(info['slot_name'])}</b>.\n"
        f"Слот снова доступен для выбора.",
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
        reg_info = (
            f"Позиция: {reg['slot_flag']} {reg['slot_name']}"
            if reg else "Позиция: нет"
        )
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
        reg_info = (
            f"Позиция: {reg['slot_flag']} {reg['slot_name']}"
            if reg else "Позиция: нет"
        )
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
    await callback.message.answer_document(
        file, caption=f"👥 Пользователей: {len(users)}"
    )
    await callback.answer()


# ===================== РАССЫЛКА =====================

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    await state.set_state(AdminStates.waiting_broadcast)
    await callback.message.edit_text(
        f"{pe('📢')} <b>Рассылка</b>\n\n"
        f"Напиши текст сообщения для рассылки всем пользователям:",
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
                await status_msg.edit_text(
                    f"📢 Рассылка... {sent + failed}/{len(users)}"
                )
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
        f"{pe('🗑️')} <b>Снятие пользователя</b>\n\n"
        f"Введи ID, @юзернейм или название страны/позиции:",
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
            from database import find_slot_by_name as db_find_slot
            result = db_find_slot(text)
            if result:
                slot_key, reg_data = result
                removed = unregister_slot(slot_key)
                removed_user_id = reg_data.get("user_id")

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
                    text=(
                        f"{pe('⚠️')} Администрация сняла вас с позиции "
                        f"<b>{esc(slot_name)}</b>."
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass

        await message.answer(
            f"{pe('✅')} Снят с <b>{esc(slot_name)}</b>: "
            f"<code>{esc(user_name)}</code>",
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


# ===================== ОБНОВИТЬ СООБЩЕНИЕ =====================

@router.callback_query(F.data == "admin_update_msg")
async def admin_update_msg(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Нет доступа!")
        return

    year = get_current_year()
    await _update_reg_msg(callback.bot, year)
    await callback.answer("✅ Сообщение регистрации обновлено!", show_alert=True)


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

    stats_lines = [f"  {esc(t)}: {c}" for t, c in type_counts.items()]
    stats_text = "\n".join(stats_lines) if stats_lines else "  Нет регистраций"

    await callback.message.edit_text(
        f"{pe('📊')} <b>Статистика Rise of Europe</b>\n\n"
        f"{pe('📅')} Текущий вайп: <b>{year}</b>\n"
        f"{pe('👥')} Всего пользователей: <b>{len(users)}</b>\n"
        f"{pe('📋')} Активных регистраций: <b>{len(regs)}</b>\n"
        f"🏴 Завоёванных слотов: <b>{len(conquered)}</b>\n\n"
        f"По типам:\n{stats_text}",
        parse_mode="HTML",
        reply_markup=back_to_admin_kb()
    )
    await callback.answer()


# ===================== СНЯТИЕ В ГРУППЕ (!Снятие) =====================

@router.message(F.text.lower().startswith("!снятие"))
async def group_remove_command(message: Message):
    """Работает ТОЛЬКО в рп-группе и только для владельца."""
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
                from database import find_slot_by_name as db_find
                result = db_find(arg)
                if result:
                    slot_key, reg_data = result
                    removed = unregister_slot(slot_key)
                    if removed:
                        await log_unregister(
                            bot, reg_data.get("user_id", 0),
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
                    bot, target_user_id,
                    removed.get("username", ""),
                    removed.get("full_name", target_name),
                    slot_name, by_admin=True
                )
                await _update_reg_msg(bot, year)
                await message.reply(
                    f"✅ Снял с <b>{esc(slot_name)}</b>",
                    parse_mode="HTML"
                )
                try:
                    await bot.send_message(
                        chat_id=target_user_id,
                        text=(
                            f"{pe('⚠️')} Администрация сняла вас с позиции "
                            f"<b>{esc(slot_name)}</b>."
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        else:
            await message.reply("❌ Пользователь не зарегистрирован")
    else:
        await message.reply("❌ Не удалось определить пользователя")