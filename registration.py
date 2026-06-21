"""
Обработчики регистрации
"""

import re
import uuid
from html import escape
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatType

from config import OWNER_ID, MAX_RELOCATIONS, GROUP_ID, TOPIC_ID
from database import (
    get_current_year, get_user_registration, is_slot_occupied,
    register_slot, unregister_slot, get_user_relocations,
    increment_relocations, is_slot_conquered,
    get_reg_message_id, set_reg_message_id
)
from data_loader import (
    get_all_countries, get_regular_countries, get_superpowers,
    get_pmcs, get_mo, get_vice, get_terror, get_other,
    get_interesting_countries, find_slot_by_name, find_slot_by_key,
    get_data_year, get_slots_for_year,
)
from keyboards import (
    reg_type_kb, mo_vice_choice_kb, interesting_countries_kb,
    pmc_kb, mo_kb, vice_kb, terror_kb, other_kb,
    confirm_kb, unregister_confirm_kb, approve_deny_kb, main_menu_kb
)
from messages import build_reg_message, TYPE_NAMES, TYPE_NAMES_ACCUSATIVE
from logger import (
    log_registration, log_unregister, log_relocation_request,
    log_superpower_request, log_other_request, log
)
from membership import check_member
from premium_emoji import pe

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

class RegStates(StatesGroup):
    choosing_type = State()
    choosing_slot_text = State()
    waiting_slot_key = State()
    confirming_slot = State()
    waiting_other_text = State()
    waiting_superpower_text = State()
    confirming_unregister = State()
    waiting_unregister_name = State()

pending_requests: dict[str, dict] = {}
confirm_data: dict[str, str] = {}
slot_select_data: dict[str, str] = {}
unregister_data: dict[str, str] = {}

def esc(text: str) -> str:
    return escape(str(text))

async def update_reg_message(bot, year: int):
    text = build_reg_message(year)
    msg_id = get_reg_message_id()

    if msg_id:
        try:
            await bot.edit_message_text(
                chat_id=GROUP_ID,
                message_id=msg_id,
                text=text,
                parse_mode="HTML"
            )
            return
        except Exception as e:
            err_msg = str(e)
            if "message is not modified" in err_msg:
                return
            if "message to edit not found" in err_msg or "message not found" in err_msg:
                log.warning(f"Сообщение {msg_id} не найдено, создаю новое.")
                set_reg_message_id(None)
            else:
                log.warning(f"Не удалось отредактировать сообщение регистрации (id={msg_id}): {e}")
                set_reg_message_id(None)

    if not get_reg_message_id():
        try:
            sent = await bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=TOPIC_ID,
                text=text,
                parse_mode="HTML",
            )
            set_reg_message_id(sent.message_id)
            log.info(f"Новое сообщение регистрации отправлено в тему {TOPIC_ID}, id={sent.message_id}")
        except Exception as e:
            log.error(f"Критическая ошибка отправки сообщения регистрации: {e}")

def _check_conquered(slot_key: str) -> bool:
    return is_slot_conquered(slot_key)

@router.callback_query(F.data == "reg_start")
async def reg_start(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    is_member = await check_member(callback.bot, user.id)
    if not is_member:
        await callback.answer("⛔ Сначала вступите в Rise of Europe!", show_alert=True)
        return

    current_reg = get_user_registration(user.id)
    if current_reg:
        rid = str(uuid.uuid4())[:8]
        unregister_data[rid] = current_reg["slot_key"]
        await callback.message.edit_text(
            f"{pe('📍')} Ты уже зарегистрирован за: "
            f"<b>{esc(current_reg['slot_flag'])} {esc(current_reg['slot_name'])}</b>\n\n"
            f"Хочешь сняться с текущей позиции?",
            parse_mode="HTML",
            reply_markup=unregister_confirm_kb(rid)
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"{pe('📋')} Выбери из списка ниже, за кого ты хочешь зарегистрироваться:",
        parse_mode="HTML",
        reply_markup=reg_type_kb()
    )
    await state.set_state(RegStates.choosing_type)
    await callback.answer()

@router.callback_query(RegStates.choosing_type, F.data == "type_country")
async def type_country(callback: CallbackQuery, state: FSMContext):
    year = get_current_year()
    data_year = get_data_year(year)

    interesting = get_interesting_countries(data_year)
    free_interesting = [
        c for c in interesting
        if not is_slot_occupied(c["key"]) and not _check_conquered(c["key"])
    ]

    text = (
        f"{pe('🏳️')} Ты решил играть за <b>Страну</b>!\n\n"
        f"Могу предложить пару интересных вариантов. "
        f"Или напиши название страны ниже.\n\n"
        f"Перед выбором рекомендую ознакомиться с темой регистрации в нашем проекте."
    )

    if not free_interesting:
        text += (
            f"\n\n{pe('😔')} Все интересные варианты заняты, "
            f"но ты можешь написать название любой другой страны."
        )

    await state.update_data(reg_type="country")
    await state.set_state(RegStates.choosing_slot_text)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=interesting_countries_kb(data_year, slot_select_data)
    )
    await callback.answer()

@router.callback_query(RegStates.choosing_type, F.data == "type_pmc")
async def type_pmc(callback: CallbackQuery, state: FSMContext):
    year = get_current_year()
    data_year = get_data_year(year)
    pmcs = get_pmcs(data_year)
    free_pmcs = [
        p for p in pmcs
        if not is_slot_occupied(p["key"]) and not _check_conquered(p["key"])
    ]

    text = (
        f"{pe('🛡️')} Ты решил играть за <b>ЧВК</b>!\n\n"
        f"Выбери из доступных вариантов или напиши название вручную."
    )

    if not free_pmcs:
        text += f"\n\n{pe('😔')} К сожалению, все ЧВК заняты."

    await state.update_data(reg_type="pmc")
    await state.set_state(RegStates.choosing_slot_text)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=pmc_kb(data_year, slot_select_data)
    )
    await callback.answer()

@router.callback_query(RegStates.choosing_type, F.data == "type_mo_vice")
async def type_mo_vice(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"{pe('⚔️')} Ты решил играть за <b>МО / Вице</b>!\n\nВыбери конкретную роль:",
        parse_mode="HTML",
        reply_markup=mo_vice_choice_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "back_mo_vice")
async def back_mo_vice(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"{pe('⚔️')} Выбери конкретную роль:",
        parse_mode="HTML",
        reply_markup=mo_vice_choice_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "type_mo")
async def type_mo(callback: CallbackQuery, state: FSMContext):
    year = get_current_year()
    data_year = get_data_year(year)
    mo_list = get_mo(data_year)
    free_mo = [
        m for m in mo_list
        if not is_slot_occupied(m["key"]) and not _check_conquered(m["key"])
    ]

    text = (
        f"{pe('⚔️')} Ты решил играть за <b>Министерство обороны</b>!\n\n"
        f"Выбери страну или напиши название МО вручную."
    )

    if not free_mo:
        text += f"\n\n{pe('😔')} Все позиции МО заняты."

    await state.update_data(reg_type="mo")
    await state.set_state(RegStates.choosing_slot_text)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=mo_kb(data_year, slot_select_data)
    )
    await callback.answer()

@router.callback_query(F.data == "type_vice")
async def type_vice(callback: CallbackQuery, state: FSMContext):
    year = get_current_year()
    data_year = get_data_year(year)
    vice_list = get_vice(data_year)
    free_vice = [
        v for v in vice_list
        if not is_slot_occupied(v["key"]) and not _check_conquered(v["key"])
    ]

    text = (
        f"{pe('🤝')} Ты решил играть за <b>Вице-президента/Вице-лидера</b>!\n\n"
        f"Выбери страну или напиши название вручную."
    )

    if not free_vice:
        text += f"\n\n{pe('😔')} Все позиции Вице заняты."

    await state.update_data(reg_type="vice")
    await state.set_state(RegStates.choosing_slot_text)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=vice_kb(data_year, slot_select_data)
    )
    await callback.answer()

@router.callback_query(F.data == "type_terror")
async def type_terror(callback: CallbackQuery, state: FSMContext):
    year = get_current_year()
    data_year = get_data_year(year)
    terror_list = get_terror(data_year)
    free_terror = [
        t for t in terror_list
        if not is_slot_occupied(t["key"]) and not _check_conquered(t["key"])
    ]

    text = (
        f"{pe('💣')} Ты решил играть за <b>Террористическую организацию</b>!\n\n"
        f"Выбери из списка или напиши название вручную."
    )

    if not free_terror:
        text += f"\n\n{pe('😔')} Все организации заняты."

    await state.update_data(reg_type="terror")
    await state.set_state(RegStates.choosing_slot_text)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=terror_kb(data_year, slot_select_data)
    )
    await callback.answer()

@router.callback_query(F.data == "type_other")
async def type_other(callback: CallbackQuery, state: FSMContext):
    await state.update_data(reg_type="other")
    await state.set_state(RegStates.waiting_other_text)
    await callback.message.edit_text(
        f"{pe('🌐')} <b>Иное движение / формирование</b>\n\n"
        f"Напиши название формирования, за которое хочешь играть.\n\n"
        f"{pe('⚠️')} Важно: требуется разрешение владельца проекта.",
        parse_mode="HTML",
        reply_markup=None
    )
    await callback.answer()

@router.callback_query(F.data == "reg_superpower")
async def reg_superpower(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RegStates.waiting_superpower_text)

    year = get_current_year()
    data_year = get_data_year(year)
    superpowers = get_superpowers(data_year)

    sp_lines = []
    for s in superpowers:
        if not _check_conquered(s["key"]):
            status = "🔒 Занята" if is_slot_occupied(s["key"]) else "✅ Свободна"
            sp_lines.append(f"{s['flag']} {esc(s['name'])} — {status}")

    sp_list = "\n".join(sp_lines) if sp_lines else "Нет доступных сверхдержав"

    await callback.message.edit_text(
        f"{pe('👑')} <b>Бронь сверхдержавы</b>\n\n"
        f"Сверхдержавы для <b>{year}</b> года:\n"
        f"{sp_list}\n\n"
        f"Напиши название сверхдержавы, которую хочешь занять.\n"
        f"{pe('⚠️')} Регистрация на сверхдержавы — только через владельца!",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(RegStates.waiting_superpower_text, F.text, ~F.text.startswith("/"))
async def handle_superpower_text(message: Message, state: FSMContext):
    user = message.from_user
    bot = message.bot
    year = get_current_year()
    data_year = get_data_year(year)
    text = message.text.strip()

    superpowers = get_superpowers(data_year)

    slot = next(
        (s for s in superpowers if s["name"].lower() == text.lower()),
        None
    )
    if not slot:
        slot = next(
            (s for s in superpowers if text.lower() in s["name"].lower()),
            None
        )

    if not slot:
        sp_names = ", ".join(s["name"] for s in superpowers)
        await message.answer(
            f"{pe('❓')} Не нашёл сверхдержаву <b>{esc(text)}</b>.\n\n"
            f"Доступные сверхдержавы: {sp_names}\n\n"
            f"Проверь правильность написания.",
            parse_mode="HTML"
        )
        return

    if _check_conquered(slot["key"]):
        await message.answer(
            f"{pe('⛔')} <b>{esc(slot['flag'])} {esc(slot['name'])}</b> недоступна для выбора.",
            parse_mode="HTML"
        )
        return

    if is_slot_occupied(slot["key"]):
        await message.answer(
            f"{pe('😔')} <b>{esc(slot['flag'])} {esc(slot['name'])}</b> уже занята.",
            parse_mode="HTML"
        )
        return

    await log_superpower_request(
        bot, user.id, user.username or "",
        user.full_name or "", slot["name"]
    )

    request_id = str(uuid.uuid4())[:8]
    pending_requests[request_id] = {
        "user_id": user.id,
        "slot_key": slot["key"],
        "action": "superpower"
    }

    await message.answer(
        f"{pe('📩')} Я направил твой запрос администрации на рассмотрение. Ожидай!",
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            chat_id=OWNER_ID,
            text=(
                f"👑 <b>Запрос на сверхдержаву</b>\n\n"
                f"Пользователь: <code>{esc(user.full_name)}</code> | "
                f"@{user.username or 'нет'} | ID: <code>{user.id}</code>\n"
                f"Хочет занять: <b>{esc(slot['flag'])} {esc(slot['name'])}</b>\n\nРазрешить?"
            ),
            parse_mode="HTML",
            reply_markup=approve_deny_kb(request_id)
        )
    except Exception as e:
        log.error(f"Не удалось отправить запрос владельцу: {e}")

    await state.clear()

@router.message(RegStates.waiting_other_text, F.text, ~F.text.startswith("/"))
async def handle_other_text(message: Message, state: FSMContext):
    user = message.from_user
    bot = message.bot
    year = get_current_year()
    data_year = get_data_year(year)
    text = message.text.strip()

    other_list = get_other(data_year)
    slot = next(
        (o for o in other_list if o["name"].lower() == text.lower()),
        None
    )

    if slot and _check_conquered(slot["key"]):
        await message.answer(
            f"{pe('⛔')} <b>{esc(slot['flag'])} {esc(slot['name'])}</b> недоступна для выбора.",
            parse_mode="HTML"
        )
        return

    if slot and is_slot_occupied(slot["key"]):
        await message.answer(
            f"{pe('😔')} <b>🏳️ {esc(slot['name'])}</b> уже занято.",
            parse_mode="HTML"
        )
        return

    await log_other_request(
        bot, user.id, user.username or "",
        user.full_name or "", text
    )

    slot_key = (
        slot["key"] if slot
        else f"other_custom_{text.replace(' ', '_')}"
    )

    request_id = str(uuid.uuid4())[:8]
    pending_requests[request_id] = {
        "user_id": user.id,
        "slot_key": slot_key,
        "action": "other",
        "custom_name": None if slot else text
    }

    await message.answer(
        f"{pe('📩')} Я направил твой запрос администрации на рассмотрение. Ожидай!",
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            chat_id=OWNER_ID,
            text=(
                f"🌐 <b>Запрос на иное движение</b>\n\n"
                f"Пользователь: <code>{esc(user.full_name)}</code> | "
                f"@{user.username or 'нет'} | ID: <code>{user.id}</code>\n"
                f"Хочет играть за: <b>{esc(text)}</b>\n\nРазрешить?"
            ),
            parse_mode="HTML",
            reply_markup=approve_deny_kb(request_id)
        )
    except Exception as e:
        log.error(f"Не удалось отправить запрос владельцу: {e}")

    await state.clear()

@router.callback_query(F.data.startswith("select_"))
async def select_slot(callback: CallbackQuery, state: FSMContext):
    select_id = callback.data[len("select_"):]
    slot_key = slot_select_data.pop(select_id, None)
    if not slot_key:
        await callback.answer("❌ Данные устарели, попробуйте снова.", show_alert=True)
        return

    slot = find_slot_by_key(slot_key)
    if not slot:
        await callback.answer("❌ Слот не найден!", show_alert=True)
        return

    if _check_conquered(slot_key):
        await callback.answer("⛔ Этот слот недоступен для выбора!", show_alert=True)
        return

    if is_slot_occupied(slot_key):
        await callback.answer("😔 Этот слот уже занят!", show_alert=True)
        return

    confirm_id = str(uuid.uuid4())[:8]
    confirm_data[confirm_id] = slot_key

    await state.update_data(pending_slot_key=slot_key, pending_slot=slot)

    await callback.message.edit_text(
        f"{pe('🎯')} Ты выбрал: <b>{esc(slot['flag'])} {esc(slot['name'])}</b>\n\n"
        f"Ты уверен в своём выборе?",
        parse_mode="HTML",
        reply_markup=confirm_kb("register", confirm_id)
    )
    await state.set_state(RegStates.confirming_slot)
    await callback.answer()

@router.message(RegStates.choosing_slot_text, F.text, ~F.text.startswith("/"))
async def handle_slot_text(message: Message, state: FSMContext):
    user = message.from_user
    bot = message.bot
    year = get_current_year()
    data_year = get_data_year(year)
    text = message.text.strip()

    data = await state.get_data()
    reg_type = data.get("reg_type", "")

    all_slots = get_slots_for_year(data_year)

    slot = find_slot_by_name(text, data_year)

    if not slot:
        slot = next(
            (s for s in all_slots
             if text.lower() in s["name"].lower() and s.get("type") == reg_type),
            None
        )

    if not slot:
        slot = next(
            (s for s in all_slots if text.lower() in s["name"].lower()),
            None
        )

    if not slot:
        await message.answer(
            f"{pe('❓')} Не нашёл <b>{esc(text)}</b> среди доступных позиций.\n"
            f"Проверь правильность написания или выбери из кнопок выше.",
            parse_mode="HTML"
        )
        return

    if _check_conquered(slot["key"]):
        await message.answer(
            f"{pe('⛔')} <b>{esc(slot['flag'])} {esc(slot['name'])}</b> недоступна для выбора.",
            parse_mode="HTML"
        )
        return

    if slot.get("type") == "superpower":
        await state.clear()
        await log_superpower_request(
            bot, user.id, user.username or "",
            user.full_name or "", slot["name"]
        )

        request_id = str(uuid.uuid4())[:8]
        pending_requests[request_id] = {
            "user_id": user.id,
            "slot_key": slot["key"],
            "action": "superpower"
        }

        await message.answer(
            f"{pe('📩')} Я направил твой запрос администрации на рассмотрение. Ожидай!",
            parse_mode="HTML"
        )

        try:
            await bot.send_message(
                chat_id=OWNER_ID,
                text=(
                    f"👑 <b>Запрос на сверхдержаву</b>\n\n"
                    f"Пользователь: <code>{esc(user.full_name)}</code> | "
                    f"@{user.username or 'нет'} | ID: <code>{user.id}</code>\n"
                    f"Хочет занять: <b>{esc(slot['flag'])} {esc(slot['name'])}</b>\n\nРазрешить?"
                ),
                parse_mode="HTML",
                reply_markup=approve_deny_kb(request_id)
            )
        except Exception as e:
            log.error(f"Не удалось отправить запрос владельцу: {e}")
        return

    if is_slot_occupied(slot["key"]):
        await message.answer(
            f"{pe('😔')} <b>{esc(slot['flag'])} {esc(slot['name'])}</b> уже занято.",
            parse_mode="HTML"
        )
        return

    confirm_id = str(uuid.uuid4())[:8]
    confirm_data[confirm_id] = slot["key"]

    await state.update_data(pending_slot_key=slot["key"], pending_slot=slot)

    await message.answer(
        f"{pe('🎯')} Ты выбрал: <b>{esc(slot['flag'])} {esc(slot['name'])}</b>\n\n"
        f"Ты уверен в своём выборе?",
        parse_mode="HTML",
        reply_markup=confirm_kb("register", confirm_id)
    )
    await state.set_state(RegStates.confirming_slot)

@router.callback_query(F.data.startswith("confirm_register_"))
async def confirm_register(callback: CallbackQuery, state: FSMContext):
    confirm_id = callback.data[len("confirm_register_"):]
    slot_key = confirm_data.pop(confirm_id, None)
    if not slot_key:
        await callback.answer("❌ Данные устарели, попробуйте снова.", show_alert=True)
        return

    user = callback.from_user
    bot = callback.bot
    year = get_current_year()

    current_reg = get_user_registration(user.id)

    slot = find_slot_by_key(slot_key)
    if not slot:
        await callback.answer("❌ Слот не найден!", show_alert=True)
        return

    if _check_conquered(slot_key):
        await callback.answer("⛔ Этот слот недоступен!", show_alert=True)
        return

    if is_slot_occupied(slot_key):
        await callback.answer("😔 Этот слот уже занят кем-то другим!", show_alert=True)
        return

    if current_reg:
        relocations = get_user_relocations(user.id)

        if relocations >= MAX_RELOCATIONS:
            await log_relocation_request(
                bot, user.id, user.username or "", user.full_name or "",
                current_reg["slot_name"], slot["name"], relocations
            )

            request_id = str(uuid.uuid4())[:8]
            pending_requests[request_id] = {
                "user_id": user.id,
                "slot_key": slot_key,
                "action": "relocation"
            }

            try:
                await bot.send_message(
                    chat_id=OWNER_ID,
                    text=(
                        f"⚠️ <b>Запрос на пересадку (лимит превышен)</b>\n\n"
                        f"Пользователь: <code>{esc(user.full_name)}</code> | "
                        f"@{user.username or 'нет'} | ID: <code>{user.id}</code>\n"
                        f"Текущая позиция: <b>{esc(current_reg['slot_name'])}</b>\n"
                        f"Хочет перейти на: <b>{esc(slot['name'])}</b>\n"
                        f"Количество пересадок: <code>{relocations}</code>\n\nРазрешить?"
                    ),
                    parse_mode="HTML",
                    reply_markup=approve_deny_kb(request_id)
                )
            except Exception as e:
                log.error(f"Не удалось отправить запрос владельцу: {e}")

            await callback.message.edit_text(
                f"{pe('⚠️')} Вы превысили лимит количества пересадок.\n\n"
                f"{pe('📩')} Я направил ваш запрос на рассмотрение администрации. Ожидайте!",
                parse_mode="HTML"
            )
            await state.clear()
            await callback.answer()
            return

        old_slot_name = current_reg["slot_name"]
        unregister_slot(current_reg["slot_key"])
        increment_relocations(user.id)
        await log_unregister(
            bot, user.id, user.username or "",
            user.full_name or "", old_slot_name
        )

    register_slot(
        slot_key=slot_key,
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name or str(user.id),
        slot_info=slot
    )

    await log_registration(
        bot, user.id, user.username or "",
        user.full_name or "", slot["name"], slot["type"]
    )
    await update_reg_message(bot, year)

    await callback.message.edit_text(
        f"{pe('✅')} <b>Поздравляем!</b> Ты успешно зарегистрирован за:\n"
        f"<b>{esc(slot['flag'])} {esc(slot['name'])}</b>!\n\n"
        f"Добро пожаловать в Rise of Europe!",
        parse_mode="HTML",
        reply_markup=main_menu_kb(has_registration=True),
    )
    await state.clear()
    await callback.answer("✅ Регистрация успешна!")

@router.callback_query(F.data == "cancel_confirm")
async def cancel_confirm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    current_reg = get_user_registration(callback.from_user.id)
    await callback.message.edit_text(
        f"{pe('❌')} Отменено. Возвращаемся в главное меню.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(has_registration=bool(current_reg)),
    )
    await callback.answer()

@router.callback_query(F.data == "unregister_start")
async def unregister_start(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    current_reg = get_user_registration(user.id)

    if not current_reg:
        await callback.answer("❌ Ты не зарегистрирован!", show_alert=True)
        return

    await state.set_state(RegStates.waiting_unregister_name)
    await callback.message.edit_text(
        f"{pe('🚪')} <b>Снятие с позиции</b>\n\n"
        f"{pe('📍')} Ты сейчас за: "
        f"<b>{esc(current_reg['slot_flag'])} {esc(current_reg['slot_name'])}</b>\n\n"
        f"Напиши название страны/позиции, с которой хочешь сняться.",
        parse_mode="HTML",
    )
    await callback.answer()

@router.message(RegStates.waiting_unregister_name, F.text, ~F.text.startswith("/"))
async def handle_unregister_name(message: Message, state: FSMContext):
    user = message.from_user
    text = message.text.strip()
    current_reg = get_user_registration(user.id)

    if not current_reg:
        await message.answer(
            f"{pe('❌')} Ты не зарегистрирован.",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        await state.clear()
        return

    if text.lower() != current_reg["slot_name"].lower():
        await message.answer(
            f"{pe('❌')} Это не твоя текущая позиция.\n"
            f"{pe('📍')} Ты зарегистрирован за: <b>{esc(current_reg['slot_name'])}</b>",
            parse_mode="HTML",
        )
        return

    rid = str(uuid.uuid4())[:8]
    unregister_data[rid] = current_reg["slot_key"]
    await state.update_data(unregister_slot_key=current_reg["slot_key"])
    await state.set_state(RegStates.confirming_unregister)

    await message.answer(
        f"{pe('⚠️')} Ты уверен, что хочешь сняться с "
        f"<b>{esc(current_reg['slot_name'])}</b>?",
        parse_mode="HTML",
        reply_markup=unregister_confirm_kb(rid),
    )

@router.callback_query(F.data.startswith("unregister_"))
async def unregister(callback: CallbackQuery, state: FSMContext):
    if callback.data == "unregister_start":
        return

    rid = callback.data[len("unregister_"):]
    slot_key = unregister_data.pop(rid, None)
    if not slot_key:
        slot_key = rid
    user = callback.from_user
    bot = callback.bot
    year = get_current_year()

    removed = unregister_slot(slot_key)

    if removed:
        await log_unregister(
            bot, user.id, user.username or "",
            user.full_name or "", removed.get("slot_name", "?")
        )
        increment_relocations(user.id)
        await update_reg_message(bot, year)

        await callback.message.edit_text(
            f"{pe('✅')} Ты успешно снялся с позиции "
            f"<b>{esc(removed.get('slot_name', '?'))}</b>.",
            parse_mode="HTML",
            reply_markup=main_menu_kb(has_registration=False),
        )
    else:
        await callback.message.edit_text(
            f"{pe('❌')} Не удалось снять с позиции. Возможно, ты уже снялся.",
            parse_mode="HTML",
            reply_markup=main_menu_kb(has_registration=False),
        )

    await state.clear()
    await callback.answer()

@router.callback_query(F.data.startswith("approve_"))
async def approve_request(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("⛔ Только для владельца!", show_alert=True)
        return

    request_id = callback.data.split("_", 1)[1]
    req = pending_requests.pop(request_id, None)
    if not req:
        await callback.answer("❌ Запрос не найден или устарел", show_alert=True)
        return

    user_id = req["user_id"]
    slot_key = req["slot_key"]
    action = req["action"]
    bot = callback.bot
    year = get_current_year()

    if action in ("superpower", "other", "relocation"):
        slot = find_slot_by_key(slot_key)

        if action == "other" and "custom_name" in req and req["custom_name"]:
            custom_name = req["custom_name"]
            data_year = get_data_year(year)
            slot = {
                "key": slot_key,
                "name": custom_name,
                "type": "other",
                "flag": "🏳️",
                "year": data_year,
                "superpower": False,
            }

        if action == "relocation":
            current_reg = get_user_registration(user_id)
            if current_reg:
                unregister_slot(current_reg["slot_key"])
                increment_relocations(user_id)

        if slot and not is_slot_occupied(slot_key) and not _check_conquered(slot_key):
            from database import get_user_data
            user_data = get_user_data(user_id)
            username = user_data.get("username", "") if user_data else ""
            full_name = (
                user_data.get("full_name", str(user_id))
                if user_data else str(user_id)
            )

            if slot.get("type") == "other":
                slot = dict(slot)
                slot["flag"] = "🏳️"

            register_slot(
                slot_key=slot_key,
                user_id=user_id,
                username=username,
                full_name=full_name,
                slot_info=slot
            )

            await log_registration(
                bot, user_id, username, full_name,
                slot["name"], slot["type"]
            )
            await update_reg_message(bot, year)

            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"{pe('✅')} <b>Успешно!</b> Администрация одобрила ваш запрос!\n\n"
                        f"{pe('📍')} Вы зарегистрированы за: "
                        f"<b>{esc(slot['flag'])} {esc(slot['name'])}</b>"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass

        elif slot and (is_slot_occupied(slot_key) or _check_conquered(slot_key)):
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"{pe('❌')} К сожалению, этот слот уже недоступен.",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Одобрено",
        parse_mode="HTML"
    )
    await callback.answer("✅ Одобрено!")

@router.callback_query(F.data.startswith("deny_"))
async def deny_request(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("⛔ Только для владельца!", show_alert=True)
        return

    request_id = callback.data.split("_", 1)[1]
    req = pending_requests.pop(request_id, None)
    user_id = req["user_id"] if req else None

    if user_id:
        try:
            await callback.bot.send_message(
                chat_id=user_id,
                text=f"{pe('❌')} <b>Не успешно!</b> Администрация отклонила ваш запрос.",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ Отклонено",
        parse_mode="HTML"
    )
    await callback.answer("❌ Отклонено!")

@router.callback_query(F.data == "back_reg_type")
async def back_reg_type(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RegStates.choosing_type)
    await callback.message.edit_text(
        f"{pe('📋')} Выбери из списка ниже, за кого ты хочешь зарегистрироваться:",
        parse_mode="HTML",
        reply_markup=reg_type_kb()
    )
    await callback.answer()