"""
Проверка членства пользователя в группе через Bot API
"""

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from config import GROUP_ID
from logger import log


async def check_member(bot: Bot, user_id: int) -> bool:
    """
    Проверить, является ли пользователь членом группы.
    Возвращает True если состоит, False если нет/кикнут/забанен.
    """
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status not in ("left", "kicked", "banned", "restricted")
    except TelegramBadRequest as e:
        log.warning(f"check_member TelegramBadRequest для {user_id}: {e}")
        # Если бот не может проверить — пропускаем (не блокируем пользователя)
        return True
    except TelegramForbiddenError as e:
        log.warning(f"check_member TelegramForbiddenError для {user_id}: {e}")
        return True
    except Exception as e:
        log.error(f"check_member неизвестная ошибка для {user_id}: {e}")
        return True


async def check_admin(bot: Bot, user_id: int, chat_id: int = GROUP_ID) -> bool:
    """
    Проверить, является ли пользователь администратором группы.
    """
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ("administrator", "creator")
    except TelegramBadRequest as e:
        log.warning(f"check_admin TelegramBadRequest для {user_id}: {e}")
        return False
    except TelegramForbiddenError as e:
        log.warning(f"check_admin TelegramForbiddenError для {user_id}: {e}")
        return False
    except Exception as e:
        log.error(f"check_admin неизвестная ошибка для {user_id}: {e}")
        return False