"""
Логгирование действий в чат и в консоль
"""

import logging
from datetime import datetime
from aiogram import Bot
from config import LOG_CHAT_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("data/bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("ROE_Bot")


def _ts() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


async def send_log(bot: Bot, text: str):
    """Отправить лог в группу логов"""
    try:
        await bot.send_message(
            chat_id=LOG_CHAT_ID,
            text=f"📋 <b>[Лог]</b> <code>{_ts()}</code>\n\n{text}",
            parse_mode="HTML"
        )
    except Exception as e:
        log.error(f"Ошибка отправки лога: {e}")


async def log_start(bot: Bot, user_id: int, username: str, full_name: str):
    msg = (
        f"🟢 <b>Запуск бота</b>\n"
        f"👤 <code>{full_name}</code> | @{username or 'нет'} | ID: <code>{user_id}</code>"
    )
    log.info(f"START: {full_name} (@{username}) [{user_id}]")
    await send_log(bot, msg)


async def log_registration(bot: Bot, user_id: int, username: str, full_name: str, slot_name: str, slot_type: str):
    msg = (
        f"✅ <b>Регистрация</b>\n"
        f"👤 <code>{full_name}</code> | @{username or 'нет'} | ID: <code>{user_id}</code>\n"
        f"📍 Слот: <b>{slot_name}</b> ({slot_type})"
    )
    log.info(f"REG: {full_name} (@{username}) [{user_id}] -> {slot_name}")
    await send_log(bot, msg)


async def log_unregister(bot: Bot, user_id: int, username: str, full_name: str, slot_name: str, by_admin: bool = False):
    who = "Администратором" if by_admin else "Игроком"
    msg = (
        f"🔴 <b>Снятие с позиции</b> ({who})\n"
        f"👤 <code>{full_name}</code> | @{username or 'нет'} | ID: <code>{user_id}</code>\n"
        f"📍 Слот: <b>{slot_name}</b>"
    )
    log.info(f"UNREG: {full_name} (@{username}) [{user_id}] from {slot_name} (admin={by_admin})")
    await send_log(bot, msg)


async def log_year_change(bot: Bot, admin_id: int, old_year: int, new_year: int):
    msg = (
        f"📅 <b>Смена года</b>\n"
        f"Admin ID: <code>{admin_id}</code>\n"
        f"Год: <code>{old_year}</code> → <code>{new_year}</code>"
    )
    log.info(f"YEAR CHANGE: {old_year} -> {new_year} by {admin_id}")
    await send_log(bot, msg)


async def log_broadcast(bot: Bot, admin_id: int, text: str, count: int):
    msg = (
        f"📢 <b>Рассылка</b>\n"
        f"Admin ID: <code>{admin_id}</code>\n"
        f"Текст: {text[:100]}...\n"
        f"Отправлено: <code>{count}</code> пользователям"
    )
    log.info(f"BROADCAST by {admin_id}: {count} users")
    await send_log(bot, msg)


async def log_relocation_request(bot: Bot, user_id: int, username: str, full_name: str,
                                  from_slot: str, to_slot: str, count: int):
    msg = (
        f"⚠️ <b>Запрос на пересадку (лимит превышен)</b>\n"
        f"👤 <code>{full_name}</code> | @{username or 'нет'} | ID: <code>{user_id}</code>\n"
        f"📍 С: <b>{from_slot}</b>\n"
        f"📍 На: <b>{to_slot}</b>\n"
        f"🔄 Пересадок: <code>{count}</code>"
    )
    log.info(f"RELOC REQUEST: {full_name} [{user_id}] from {from_slot} to {to_slot} (count={count})")
    await send_log(bot, msg)


async def log_superpower_request(bot: Bot, user_id: int, username: str, full_name: str, slot_name: str):
    msg = (
        f"👑 <b>Запрос на сверхдержаву</b>\n"
        f"👤 <code>{full_name}</code> | @{username or 'нет'} | ID: <code>{user_id}</code>\n"
        f"🌍 Страна: <b>{slot_name}</b>"
    )
    log.info(f"SUPERPOWER REQUEST: {full_name} [{user_id}] -> {slot_name}")
    await send_log(bot, msg)


async def log_other_request(bot: Bot, user_id: int, username: str, full_name: str, formation: str):
    msg = (
        f"🌐 <b>Запрос на иное движение</b>\n"
        f"👤 <code>{full_name}</code> | @{username or 'нет'} | ID: <code>{user_id}</code>\n"
        f"📝 Формирование: <b>{formation}</b>"
    )
    log.info(f"OTHER REQUEST: {full_name} [{user_id}] -> {formation}")
    await send_log(bot, msg)