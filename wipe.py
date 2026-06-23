"""
Обработчик команды /wipe — планировщик вайпов
"""

import asyncio
from datetime import datetime
from html import escape
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ChatType

from config import OWNER_ID, GROUP_ID, TOPIC_ID
from database import (
    get_all_users, wipe_all_registrations,
    set_planned_wipe, get_planned_wipe,
    mark_wipe_executed, mark_wipe_notified,
    cancel_wipe, set_year, set_registration_open,
    set_reg_message_id, get_current_year
)
from data_loader import reload_caches
from logger import log

router = Router()


def esc(text: str) -> str:
    return escape(str(text))


async def _broadcast(bot: Bot, text: str) -> tuple:
    users = get_all_users()
    sent = 0
    failed = 0

    for user in users:
        try:
            await bot.send_message(
                chat_id=user["user_id"],
                text=text,
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    return sent, failed


async def execute_wipe(bot: Bot, year: int):
    """
    Выполнить вайп:
    1. Сброс регистраций и лимитов
    2. Смена года
    3. Открытие регистрации
    4. Обновление существующего сообщения (НЕ создание нового)
    5. Рассылка
    """
    log.info(f"Выполняю вайп! Год: {year}")

    # 1. Сброс регистраций и лимитов пересадок
    count = wipe_all_registrations()
    log.info(f"Сброшено регистраций: {count}")

    # 2. Меняем год
    set_year(year)
    reload_caches()

    # 3. Открываем регистрацию
    set_registration_open(True)

    # 4. ОБНОВЛЯЕМ СУЩЕСТВУЮЩЕЕ СООБЩЕНИЕ (не создаём новое)
    from registration import update_reg_message
    await update_reg_message(bot, year)

    # 5. Рассылаем уведомление
    sent, failed = await _broadcast(
        bot,
        f"🟢 <b>РЕГИСТРАЦИЯ ОТКРЫТА!</b>\n\n"
        f"⚔️ Новый вайп — <b>{year}</b> год\n\n"
        f"Все позиции свободны!\n"
        f"Нажми кнопку ниже и займи своё место 👇\n\n"
        f"🤖 @{(await bot.get_me()).username}"
    )

    mark_wipe_executed()
    log.info(f"Вайп выполнен! Уведомлено: {sent}, не доставлено: {failed}")


async def wipe_scheduler(bot: Bot):
    """Фоновая задача — проверяет запланированный вайп каждые 30 секунд."""
    log.info("Планировщик вайпа активен")

    while True:
        try:
            wipe_data = get_planned_wipe()

            if wipe_data and not wipe_data.get("executed"):
                planned_str = wipe_data.get("planned_at", "")
                year = wipe_data.get("year", get_current_year())

                try:
                    planned_dt = datetime.strptime(planned_str, "%d.%m.%Y %H:%M")
                except ValueError:
                    log.error(f"Неверный формат даты вайпа: {planned_str}")
                    await asyncio.sleep(60)
                    continue

                now = datetime.now()
                diff = (planned_dt - now).total_seconds()

                # За 30 минут — анонс (только один раз)
                if 0 < diff <= 1800 and not wipe_data.get("notified"):
                    log.info("Отправляю анонс вайпа (за 30 минут)")
                    hours = int(diff // 3600)
                    minutes = int((diff % 3600) // 60)
                    time_text = f"{hours}ч {minutes}м" if hours > 0 else f"{minutes} минут"

                    await _broadcast(
                        bot,
                        f"⚠️ <b>ВНИМАНИЕ! ВАЙП ЧЕРЕЗ {time_text}!</b>\n\n"
                        f"📅 Дата открытия регистрации: <b>{planned_str} МСК</b>\n"
                        f"🗓 Год вайпа: <b>{year}</b>\n\n"
                        f"Все текущие регистрации будут сброшены.\n"
                        f"Готовься занять своё место!"
                    )
                    mark_wipe_notified()

                # Время пришло — выполняем
                if diff <= 0:
                    await execute_wipe(bot, year)

        except Exception as e:
            log.error(f"Ошибка в планировщике вайпа: {e}")

        await asyncio.sleep(30)


# ===================== КОМАНДЫ =====================

@router.message(Command("wipe"), F.chat.type == ChatType.PRIVATE)
async def cmd_wipe(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    args = message.text.split()[1:]

    if len(args) < 3:
        await message.answer(
            f"❌ <b>Неверный формат!</b>\n\n"
            f"Использование:\n"
            f"<code>/wipe ДД.ММ.ГГГГ ЧЧ:ММ ГОД</code>\n\n"
            f"Примеры:\n"
            f"<code>/wipe 22.06.2026 20:00 2025</code>\n"
            f"<code>/wipe 01.07.2026 12:00 1941</code>\n\n"
            f"Где первые два аргумента — дата и время открытия регистрации,\n"
            f"третий — год вайпа.",
            parse_mode="HTML"
        )
        return

    date_str = args[0]
    time_str = args[1]
    year_str = args[2]
    dt_str = f"{date_str} {time_str}"

    try:
        year = int(year_str)
        if not (1900 <= year <= 2100):
            raise ValueError("Год вне диапазона")
    except ValueError:
        await message.answer(
            f"❌ Неверный год: <code>{esc(year_str)}</code>\nУкажи год от 1900 до 2100.",
            parse_mode="HTML"
        )
        return

    try:
        planned_dt = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer(
            f"❌ Неверный формат даты: <code>{esc(dt_str)}</code>\n"
            f"Нужно: ДД.ММ.ГГГГ ЧЧ:ММ\nПример: <code>22.06.2026 20:00</code>",
            parse_mode="HTML"
        )
        return

    now = datetime.now()
    if planned_dt <= now:
        await message.answer(
            f"❌ Дата должна быть в будущем!\nСейчас: <code>{now.strftime('%d.%m.%Y %H:%M')}</code>",
            parse_mode="HTML"
        )
        return

    set_planned_wipe(dt_str, year)

    diff = planned_dt - now
    total_minutes = int(diff.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    await message.answer(
        f"✅ <b>Вайп запланирован!</b>\n\n"
        f"📅 Дата открытия: <b>{dt_str}</b> МСК\n"
        f"🗓 Год вайпа: <b>{year}</b>\n"
        f"⏰ До вайпа: <b>{hours}ч {minutes}м</b>\n\n"
        f"Что произойдёт в момент вайпа:\n"
        f"▪️ Все регистрации сбросятся\n"
        f"▪️ Все лимиты пересадок обнулятся\n"
        f"▪️ Год сменится на {year}\n"
        f"▪️ Регистрация откроется\n"
        f"▪️ Всем придёт уведомление\n\n"
        f"⚠️ За 30 минут — анонс всем игрокам\n\n"
        f"Отмена: <code>/wipecanel</code>\n"
        f"Статус: <code>/wipestatus</code>",
        parse_mode="HTML"
    )

    log.info(f"Вайп запланирован: {dt_str}, год={year}")


@router.message(Command("wipecanel"), F.chat.type == ChatType.PRIVATE)
async def cmd_wipe_cancel(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    wipe_data = get_planned_wipe()
    if not wipe_data:
        await message.answer("❌ Нет активных вайпов для отмены.")
        return

    planned_str = wipe_data.get("planned_at", "?")
    year = wipe_data.get("year", "?")
    cancel_wipe()

    await message.answer(
        f"✅ <b>Вайп отменён</b>\n\nБыл запланирован: <b>{planned_str}</b>\nГод: <b>{year}</b>",
        parse_mode="HTML"
    )
    log.info(f"Вайп отменён владельцем. Был: {planned_str}, год: {year}")


@router.message(Command("wipestatus"), F.chat.type == ChatType.PRIVATE)
async def cmd_wipe_status(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    wipe_data = get_planned_wipe()
    if not wipe_data:
        await message.answer(
            "📋 <b>Вайпов не запланировано</b>\n\n"
            "Запланировать: <code>/wipe ДД.ММ.ГГГГ ЧЧ:ММ ГОД</code>",
            parse_mode="HTML"
        )
        return

    planned_str = wipe_data.get("planned_at", "?")
    year = wipe_data.get("year", "?")
    notified = wipe_data.get("notified", False)

    try:
        planned_dt = datetime.strptime(planned_str, "%d.%m.%Y %H:%M")
        now = datetime.now()
        diff = planned_dt - now
        if diff.total_seconds() > 0:
            total_minutes = int(diff.total_seconds() // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            time_left = f"{hours}ч {minutes}м"
        else:
            time_left = "⚡ Выполняется..."
    except Exception:
        time_left = "?"

    await message.answer(
        f"📋 <b>Статус вайпа</b>\n\n"
        f"📅 Дата открытия: <b>{planned_str}</b>\n"
        f"🗓 Год вайпа: <b>{year}</b>\n"
        f"⏰ До вайпа: <b>{time_left}</b>\n"
        f"📢 Анонс отправлен: <b>{'✅ Да' if notified else '❌ Нет'}</b>\n\n"
        f"Отмена: <code>/wipecanel</code>",
        parse_mode="HTML"
    )


@router.message(Command("wipenow"), F.chat.type == ChatType.PRIVATE)
async def cmd_wipe_now(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    args = message.text.split()[1:]

    if not args:
        await message.answer(
            f"❌ Укажи год!\nПример: <code>/wipenow 2025</code>",
            parse_mode="HTML"
        )
        return

    try:
        year = int(args[0])
        if not (1900 <= year <= 2100):
            raise ValueError
    except ValueError:
        await message.answer(
            f"❌ Неверный год: <code>{esc(args[0])}</code>",
            parse_mode="HTML"
        )
        return

    status_msg = await message.answer(
        f"⚡ <b>Выполняю немедленный вайп...</b>\nГод: <b>{year}</b>",
        parse_mode="HTML"
    )

    try:
        await execute_wipe(message.bot, year)
        await status_msg.edit_text(
            f"✅ <b>Вайп выполнен!</b>\n\n"
            f"🗓 Год: <b>{year}</b>\n"
            f"▪️ Все регистрации сброшены\n"
            f"▪️ Лимиты пересадок обнулены\n"
            f"▪️ Регистрация открыта\n"
            f"▪️ Уведомления разосланы",
            parse_mode="HTML"
        )
    except Exception as e:
        log.error(f"Ошибка немедленного вайпа: {e}")
        await status_msg.edit_text(
            f"❌ Ошибка при вайпе: <code>{esc(str(e))}</code>",
            parse_mode="HTML"
        )
