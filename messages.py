"""
Формирование сообщений бота
"""

from html import escape
from typing import List
from database import get_registrations, get_current_year
from data_loader import (
    get_all_countries, get_mo, get_vice, get_pmcs,
    get_terror, get_other, get_superpowers, get_data_year,
)
from config import STAFF, BOT_USERNAME
from premium_emoji import ce


def format_user_mention(reg: dict) -> str:
    if reg.get("username"):
        return f"@{escape(reg['username'])}"
    if reg.get("full_name"):
        return escape(reg["full_name"])
    return f"#{reg.get('user_id', '?')}"


def _build_section_lines(slots: List[dict], regs: dict, data_year: int) -> str:
    lines = []
    for slot in slots:
        key = slot.get("key", "")
        if not key:
            continue
        reg = regs.get(key)
        if reg:
            mention = format_user_mention(reg)
            flag = slot.get("flag", "🏳️")
            name = escape(slot.get("name", "?"))
            lines.append(f"{flag} {name} — {mention}")
    return "\n".join(lines) if lines else "Свободны"


def _blockquote(content: str) -> str:
    return f"<blockquote>{content}</blockquote>"


def build_reg_message(display_year: int = None) -> str:
    if display_year is None:
        display_year = get_current_year()

    data_year = get_data_year(display_year)
    regs = get_registrations()

    countries = get_all_countries(data_year)
    superpowers = get_superpowers(data_year)
    # Объединяем страны и сверхдержавы в одну секцию
    all_countries = countries + superpowers
    mo_vice = get_mo(data_year) + get_vice(data_year)
    pmcs = get_pmcs(data_year)
    terror_other = get_terror(data_year) + get_other(data_year)

    countries_text = _build_section_lines(all_countries, regs, data_year)
    mo_vice_text = _build_section_lines(mo_vice, regs, data_year)
    pmc_text = _build_section_lines(pmcs, regs, data_year)
    terror_text = _build_section_lines(terror_other, regs, data_year)

    staff_lines = [
        f"{escape(role)} — {uname}"
        for role, uname in STAFF.items()
    ]
    staff_text = "\n".join(staff_lines)

    msg = (
        f"{ce('5291778653636551643', '🌍')} "
        f"<b>Привет! Добро пожаловать в Rise of Europe!</b>\n\n"
        f"ДЛЯ РЕГИСТРАЦИИ напиши боту — @{BOT_USERNAME}\n\n"
        f"{ce('5291920885773526040', '📅')} "
        f"<b>Текущий вайп:</b> {display_year} год\n\n"
        f"─────────────────────\n"
        f"{ce('5291925893705398356', '🏳️')} <b>Занятые страны (включая сверхдержавы):</b>\n"
        f"{_blockquote(countries_text)}\n\n"
        f"{ce('5292251447931461936', '⚔️')} <b>Занятые МО/Вице стран:</b>\n"
        f"{_blockquote(mo_vice_text)}\n\n"
        f"{ce('5289736924968283535', '🛡️')} <b>Занятые ЧВК:</b>\n"
        f"{_blockquote(pmc_text)}\n\n"
        f"{ce('5292251447931461936', '💣')} "
        f"<b>Занятые террористические организации / движения / партии:</b>\n"
        f"{_blockquote(terror_text)}\n\n"
        f"─────────────────────\n"
        f"{ce('5291926718339114379', '👥')} <b>Основные лица проекта:</b>\n"
        f"{_blockquote(staff_text)}"
    )
    return msg


TYPE_NAMES = {
    "country": "страну",
    "superpower": "сверхдержаву",
    "pmc": "ЧВК",
    "mo": "Министерство обороны",
    "vice": "Вице-президента/Вице-лидера",
    "terror": "Террористическую организацию",
    "other": "Иное движение/формирование",
}

TYPE_NAMES_ACCUSATIVE = {
    "country": "Страну",
    "superpower": "Сверхдержаву",
    "pmc": "ЧВК",
    "mo": "Министерство обороны",
    "vice": "Вице-президента/Вице-лидера",
    "terror": "Террористическую организацию",
    "other": "Иное движение/формирование",
}
