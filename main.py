"""
Главный файл бота Rise of Europe
"""

import asyncio
import logging
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from aiogram import Bot, Dispatcher, Router
from aiogram.types import ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter
from aiogram.filters.chat_member_updated import MEMBER, LEFT, KICKED
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, GROUP_ID, TOPIC_ID
from database import (
    get_current_year, get_user_registration, unregister_slot
)
from start import router as start_router
from registration import router as reg_router, update_reg_message
from admin import router as admin_router
from logger import log, send_log

try:
    from wipe import router as wipe_router, wipe_scheduler
except ImportError:
    wipe_router = None
    wipe_scheduler = None
    log.warning("wipe.py не найден, планировщик вайпа отключён")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/bot.log", encoding="utf-8", mode="a")
    ]
)

# ===================== РОУТЕР ВЫХОДА =====================

leave_router = Router()


@leave_router.chat_member(
    ChatMemberUpdatedFilter(member_status_changed=MEMBER >> (LEFT | KICKED))
)
async def on_user_left(event: ChatMemberUpdated, bot: Bot):
    if event.chat.id != GROUP_ID:
        return

    user = event.new_chat_member.user
    user_id = user.id
    username = user.username or ""
    full_name = user.full_name or str(user_id)
    status = event.new_chat_member.status
    action = "вышел" if status == "left" else "был кикнут"

    reg = get_user_registration(user_id)

    if reg:
        slot_name = reg["slot_name"]
        slot_flag = reg.get("slot_flag", "")
        unregister_slot(reg["slot_key"])

        year = get_current_year()
        await update_reg_message(bot, year)

        log.info(
            f"LEAVE+UNREG: {full_name} (@{username}) [{user_id}] "
            f"статус={status} слот={slot_name}"
        )

        await send_log(
            bot,
            f"🚪 <b>Выход из группы</b>\n\n"
            f"👤 <code>{full_name}</code> | @{username or 'нет'} | "
            f"ID: <code>{user_id}</code>\n"
            f"Статус: {action}\n"
            f"📍 Снят с: <b>{slot_flag} {slot_name}</b>"
        )
    else:
        log.info(
            f"LEAVE: {full_name} (@{username}) [{user_id}] "
            f"статус={status} (не был зарегистрирован)"
        )
        await send_log(
            bot,
            f"🚪 <b>Выход из группы</b>\n\n"
            f"👤 <code>{full_name}</code> | @{username or 'нет'} | "
            f"ID: <code>{user_id}</code>\n"
            f"Статус: {action}\n"
            f"📍 Регистрации не было"
        )


# ===================== STARTUP =====================

async def on_startup(bot: Bot):
    log.info("Бот запускается...")
    os.makedirs("data", exist_ok=True)

    if wipe_scheduler:
        asyncio.create_task(wipe_scheduler(bot))
        log.info("Планировщик вайпа запущен")

    # Проверка группы
    try:
        chat = await bot.get_chat(GROUP_ID)
        log.info(f"Группа найдена: {chat.title} (ID: {GROUP_ID})")
    except Exception as e:
        log.error(f"Не удалось подключиться к группе {GROUP_ID}: {e}")
        log.error("Проверьте настройки GROUP_ID и права бота.")

    year = get_current_year()
    await update_reg_message(bot, year)

    me = await bot.get_me()
    log.info(f"Бот @{me.username} запущен!")


# ===================== MAIN =====================

async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан!")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(leave_router)
    dp.include_router(admin_router)
    if wipe_router:
        dp.include_router(wipe_router)
    dp.include_router(start_router)
    dp.include_router(reg_router)

    dp.startup.register(on_startup)

    log.info("Запуск polling...")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "chat_member"],
            drop_pending_updates=True
        )
    finally:
        await bot.session.close()
        log.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
