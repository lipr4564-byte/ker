"""
Обработчики старта и главного меню
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import get_user_registration
from keyboards import main_menu_kb
from membership import check_member
from premium_emoji import pe

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user

    is_member = await check_member(message.bot, user.id)
    if not is_member:
        await message.answer(
            f"{pe('⛔')} Сначала вступите в группу @Rise_of_Europe!",
            parse_mode="HTML"
        )
        return

    await state.clear()

    current_reg = get_user_registration(user.id)

    await message.answer(
        f"{pe('🌍')} Привет, <b>{user.full_name}</b>!\n\n"
        f"Добро пожаловать в бот регистрации <b>Rise of Europe</b>.\n"
        f"Выбери действие в меню ниже:",
        parse_mode="HTML",
        reply_markup=main_menu_kb(has_registration=bool(current_reg))
    )

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    await state.clear()
    current_reg = get_user_registration(user.id)

    await callback.message.edit_text(
        f"{pe('🌍')} Привет, <b>{user.full_name}</b>!\n\n"
        f"Добро пожаловать в бот регистрации <b>Rise of Europe</b>.\n"
        f"Выбери действие в меню ниже:",
        parse_mode="HTML",
        reply_markup=main_menu_kb(has_registration=bool(current_reg))
    )
    await callback.answer()