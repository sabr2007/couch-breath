"""
Обработчики вопросов куратору (прокси-поддержка)
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.states import UserState
from bot.keyboards import main_menu_keyboard, cancel_keyboard
from bot.database import queries as db
from bot.config import config

logger = logging.getLogger(__name__)


async def ask_curator_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: начать задавать вопрос куратору"""
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id

    # Сохраняем lesson_id если есть (из callback_data "ask_curator:5")
    data = query.data
    if ":" in data:
        lesson_id = int(data.split(":")[1])
        context.user_data["question_lesson_id"] = lesson_id

    await db.update_user_state(tg_id, UserState.WAITING_QUESTION.value)

    await query.edit_message_text(
        "Напишите ваш вопрос куратору.\n\n"
        "Можете отправить текст, фото или голосовое сообщение.",
        reply_markup=cancel_keyboard()
    )


async def receive_question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение вопроса и пересылка куратору"""
    tg_id = update.effective_user.id
    user = await db.get_user(tg_id)

    # Проверяем состояние
    if not user or user.state != UserState.WAITING_QUESTION.value:
        return

    # Формируем информацию о студенте
    username = update.effective_user.username
    full_name = update.effective_user.full_name or ""
    lesson_id = context.user_data.get("question_lesson_id")

    lesson_info = ""
    if lesson_id:
        lesson = await db.get_lesson(lesson_id)
        if lesson:
            lesson_info = f"\nУрок: {lesson.order_num}. {lesson.title}"

    header = (
        f"📩 Вопрос от студента\n"
        f"ID: {tg_id}\n"
        f"Username: @{username or 'нет'}\n"
        f"Имя: {full_name}"
        f"{lesson_info}\n"
        f"{'─' * 20}"
    )

    try:
        # Отправляем заголовок куратору
        header_msg = await context.bot.send_message(config.CURATOR_ID, header)

        # Пересылаем оригинальное сообщение
        forwarded = await update.message.forward(config.CURATOR_ID)

        # Сохраняем связь message_id -> user_id для ответа
        # Используем bot_data для хранения маппинга
        if "question_mapping" not in context.bot_data:
            context.bot_data["question_mapping"] = {}

        context.bot_data["question_mapping"][forwarded.message_id] = tg_id
        context.bot_data["question_mapping"][header_msg.message_id] = tg_id

        logger.info(f"Вопрос от {tg_id} переслан куратору")

        # Возвращаем пользователя в IDLE
        await db.update_user_state(tg_id, UserState.IDLE.value)
        context.user_data.pop("question_lesson_id", None)

        await update.message.reply_text(
            "✅ Ваш вопрос отправлен куратору.\n\n"
            "Ответ придёт в этот чат.",
            reply_markup=main_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Ошибка пересылки вопроса куратору: {e}")
        await update.message.reply_text(
            "❌ Не удалось отправить вопрос. Попробуйте позже.",
            reply_markup=main_menu_keyboard()
        )
        await db.update_user_state(tg_id, UserState.IDLE.value)


async def curator_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа куратора (reply) и пересылка студенту"""
    # Проверяем что это куратор
    if update.effective_user.id != config.CURATOR_ID:
        return

    # Проверяем что это reply
    if not update.message.reply_to_message:
        return

    replied_msg_id = update.message.reply_to_message.message_id

    # Ищем студента по message_id
    mapping = context.bot_data.get("question_mapping", {})
    student_id = mapping.get(replied_msg_id)

    if not student_id:
        return

    try:
        # Отправляем ответ студенту
        await context.bot.send_message(
            student_id,
            f"💬 Ответ от куратора:\n\n{update.message.text}"
        )

        # Подтверждаем куратору
        await update.message.reply_text("✅ Ответ отправлен студенту")

        logger.info(f"Ответ куратора отправлен студенту {student_id}")

    except Exception as e:
        logger.error(f"Ошибка отправки ответа студенту {student_id}: {e}")
        await update.message.reply_text(f"❌ Не удалось отправить: {e}")
