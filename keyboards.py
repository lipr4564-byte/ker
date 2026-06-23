"""
Клавиатуры (inline кнопки) для бота
"""

import uuid
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import is_slot_occupied, get_current_year, is_slot_conquered, get_bot_status
from data_loader import (
    get_pmcs, get_mo, get_vice, get_terror, get_other,
    get_interesting_countries,
)
from config import DATA_YEARS
from premium_emoji import btn


# ===================== ГЛАВНОЕ МЕНЮ =====================

def main_menu_kb(has_registration: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        btn("Регистрация", "reg_start", "📋"),
        btn("Бронь сверхдержавы", "reg_superpower", "👑"),
    )
    if has_registration:
        builder.row(btn("Сняться со страны", "unregister_start", "🚪"))
    return builder.as_markup()


# ===================== РЕГИСТРАЦИЯ — ТИП =====================

def reg_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(btn("Страна", "type_country", "🏳️"))
    builder.row(btn("ЧВК", "type_pmc", "🛡️"))
    builder.row(btn("Министерство обороны / Вице-президент", "type_mo_vice", "⚔️"))
    builder.row(btn("Террористическая организация", "type_terror", "💣"))
    builder.row(btn("Иное движение (с разрешением владельца)", "type_other", "🌐"))
    builder.row(btn("Назад", "back_main", "🔙"))
    return builder.as_markup()


def mo_vice_choice_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(btn("Министерство обороны", "type_mo", "⚔️"))
    builder.row(btn("Вице-президент/Вице-лидер", "type_vice", "🤝"))
    builder.row(btn("Назад", "back_reg_type", "🔙"))
    return builder.as_markup()


# ===================== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ КНОПОК СЛОТОВ =====================

def _slot_buttons(
    builder: InlineKeyboardBuilder,
    slots: list,
    back_cb: str,
    storage: dict
) -> None:
    for slot in slots:
        key = slot.get("key", "")
        if not key:
            continue
        if is_slot_occupied(key) or is_slot_conquered(key):
            continue
        rid = str(uuid.uuid4())[:8]
        storage[rid] = key
        label = f"{slot.get('flag', '🏳️')} {slot.get('name', '?')}"
        builder.row(btn(label, f"select_{rid}"))
    builder.row(btn("Назад", back_cb, "🔙"))


# ===================== КЛАВИАТУРЫ СЛОТОВ =====================

def interesting_countries_kb(year: int, storage: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    interesting = get_interesting_countries(year)
    free = [
        c for c in interesting
        if not is_slot_occupied(c["key"]) and not is_slot_conquered(c["key"])
    ]
    _slot_buttons(builder, free[:8], "back_reg_type", storage)
    return builder.as_markup()


def pmc_kb(year: int, storage: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    free = [
        p for p in get_pmcs(year)
        if not is_slot_occupied(p["key"]) and not is_slot_conquered(p["key"])
    ]
    _slot_buttons(builder, free, "back_reg_type", storage)
    return builder.as_markup()


def mo_kb(year: int, storage: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    free = [
        m for m in get_mo(year)
        if not is_slot_occupied(m["key"]) and not is_slot_conquered(m["key"])
    ]
    _slot_buttons(builder, free, "back_mo_vice", storage)
    return builder.as_markup()


def vice_kb(year: int, storage: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    free = [
        v for v in get_vice(year)
        if not is_slot_occupied(v["key"]) and not is_slot_conquered(v["key"])
    ]
    _slot_buttons(builder, free, "back_mo_vice", storage)
    return builder.as_markup()


def terror_kb(year: int, storage: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    free = [
        t for t in get_terror(year)
        if not is_slot_occupied(t["key"]) and not is_slot_conquered(t["key"])
    ]
    _slot_buttons(builder, free, "back_reg_type", storage)
    return builder.as_markup()


def other_kb(year: int, storage: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    free = [
        o for o in get_other(year)
        if not is_slot_occupied(o["key"]) and not is_slot_conquered(o["key"])
    ]
    _slot_buttons(builder, free, "back_reg_type", storage)
    return builder.as_markup()


# ===================== ПОДТВЕРЖДЕНИЕ =====================

def confirm_kb(action: str, confirm_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        btn("✅ Да", f"confirm_{action}_{confirm_id}"),
        btn("❌ Нет", "cancel_confirm"),
    )
    return builder.as_markup()


def unregister_confirm_kb(rid: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        btn("✅ Да, сняться", f"unregister_{rid}"),
        btn("❌ Нет", "back_main"),
    )
    return builder.as_markup()


# ===================== ОДОБРЕНИЕ/ОТКЛОНЕНИЕ =====================

def approve_deny_kb(request_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        btn("✅ Разрешить", f"approve_{request_id}"),
        btn("❌ Запретить", f"deny_{request_id}"),
    )
    return builder.as_markup()


# ===================== АДМИН-ПАНЕЛЬ =====================

def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(btn("📅 Выбрать год", "admin_year"))
    builder.row(btn("📋 Список пользователей", "admin_users"))
    builder.row(btn("📢 Рассылка", "admin_broadcast"))
    builder.row(btn("🗑️ Снять пользователя", "admin_remove"))
    builder.row(btn("👤 Ручная регистрация", "admin_manual_reg"))
    builder.row(btn("🔧 Управление пользователем", "admin_user_manage"))
    builder.row(btn("➕ Создать кастомный слот", "admin_create_slot"))
    builder.row(btn("🔄 Обновить сообщение регистрации", "admin_update_msg"))
    builder.row(btn("📊 Статистика", "admin_stats"))
    builder.row(
        btn("🏴 Завоёвано", "admin_conquer"),
        btn("✅ Снять завоёвано", "admin_unconquer"),
    )
    builder.row(btn("📜 Посмотреть логи", "admin_logs"))
    builder.row(btn("🔄 Перезагрузить кэш", "admin_reload_cache"))
    builder.row(btn("⚠️ Сбросить все регистрации", "admin_wipe_regs"))
    
    # Кнопка управления статусом
    status = get_bot_status()
    if status == "on":
        builder.row(btn("🛑 Выключить бота", "admin_shutdown"))
    else:
        builder.row(btn("✅ Включить бота", "admin_start_bot"))
    
    return builder.as_markup()


def year_select_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    current = get_current_year()
    for year in DATA_YEARS:
        label = f"✓ {year}" if year == current else str(year)
        builder.button(text=label, callback_data=f"set_year_{year}")
    builder.adjust(3)
    builder.row(btn("✏️ Свой год", "admin_custom_year"))
    builder.row(btn("🔙 Назад", "back_admin"))
    return builder.as_markup()


def back_to_admin_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(btn("🔙 В админ-панель", "back_admin"))
    return builder.as_markup()
