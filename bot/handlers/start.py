"""
Обработчик /start и активации по коду доступа
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.states import UserState
from bot.keyboards import no_auth_keyboard, main_menu_keyboard
from bot.database import queries as db

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    user = update.effective_user
    tg_id = user.id
    username = user.username or ""
    full_name = user.full_name or ""

    # Проверяем/создаём пользователя
    existing_user = await db.get_user(tg_id)
    if not existing_user:
        await db.create_user(tg_id, username, full_name)
        logger.info(f"Новый пользователь: {tg_id} (@{username})")

    # Проверяем зачисление
    enrollment = await db.get_enrollment(tg_id)

    if enrollment:
        # Авторизован — главное меню
        await db.update_user_state(tg_id, UserState.IDLE.value)
        await update.message.reply_text(
            f"С возвращением, {full_name}!\n\nВыберите действие:",
            reply_markup=main_menu_keyboard()
        )
    else:
        # Не авторизован — заглушка
        await db.update_user_state(tg_id, UserState.NO_AUTH.value)
        await update.message.reply_text(
            "Добро пожаловать в курс «Дыхание Тренера»!\n\nДля доступа к урокам введите код активации.",
            reply_markup=no_auth_keyboard()
        )


async def enter_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: нажатие 'Ввести код доступа'"""
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id
    await db.update_user_state(tg_id, UserState.WAITING_CODE.value)

    await query.edit_message_text(
        "Отправьте ваш код доступа следующим сообщением:"
    )


async def code_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода кода доступа"""
    tg_id = update.effective_user.id
    code = update.message.text.strip()

    # Проверяем состояние
    user = await db.get_user(tg_id)
    if not user or user.state != UserState.WAITING_CODE.value:
        return

    # Проверяем код
    access_code = await db.get_access_code(code)

    if not access_code:
        await update.message.reply_text(
            "Код не найден. Проверьте правильность ввода.",
            reply_markup=no_auth_keyboard()
        )
        await db.update_user_state(tg_id, UserState.NO_AUTH.value)
        return

    if access_code.is_used:
        await update.message.reply_text(
            "Этот код уже использован.",
            reply_markup=no_auth_keyboard()
        )
        await db.update_user_state(tg_id, UserState.NO_AUTH.value)
        return

    # Активируем код
    await db.use_access_code(code, tg_id)
    await db.create_enrollment(tg_id)

    # Открываем первый урок
    await db.set_lesson_status(tg_id, 1, "OPEN")

    await db.update_user_state(tg_id, UserState.IDLE.value)

    logger.info(f"Активация кода: {tg_id} -> {code}")

    await update.message.reply_text(
        "Код активирован! Добро пожаловать на курс!\n\nНажмите кнопку ниже, чтобы начать первый урок.",
        reply_markup=main_menu_keyboard()
    )


async def contact_support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: написать в поддержку"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "Для получения кода доступа или по другим вопросам\nнапишите куратору: @your_curator_username\n\nИли попробуйте ввести код ещё раз:",
        reply_markup=no_auth_keyboard()
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: главное меню"""
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id
    await db.update_user_state(tg_id, UserState.IDLE.value)

    await query.edit_message_text(
        "Главное меню\n\nВыберите действие:",
        reply_markup=main_menu_keyboard()
    )


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: отмена действия"""
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id
    await db.update_user_state(tg_id, UserState.IDLE.value)

    await query.edit_message_text(
        "Действие отменено.\n\nВыберите действие:",
        reply_markup=main_menu_keyboard()
    )
