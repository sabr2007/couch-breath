"""
Обработчики сдачи домашних заданий
"""

import logging
import re
import random
from telegram import Update
from telegram.ext import ContextTypes

from bot.states import UserState
from bot.keyboards import main_menu_keyboard, cancel_keyboard
from bot.database import queries as db
from bot.database.connection import get_pool
from bot.config import config

logger = logging.getLogger(__name__)

# Простые ответы для файлов/видео
FILE_VIDEO_RESPONSES = [
    "Отлично! Твоё домашнее задание принято. Так держать!",
    "Супер! Получил твою работу. Молодец, что выполнил!",
    "Принято! Видно, что ты стараешься. Продолжай в том же духе!",
    "Класс! Домашка зачтена. Двигаемся дальше!",
    "Получил! Отличная работа. Ты на правильном пути!",
]


async def submit_hw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: начать сдачу ДЗ"""
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id
    data = query.data  # submit_hw:5
    lesson_id = int(data.split(":")[1])

    # Проверяем rate limit
    recent = await db.count_recent_submissions(tg_id, lesson_id, hours=1)
    if recent >= config.RATE_LIMIT_PER_HOUR:
        await query.answer(
            f"Превышен лимит попыток ({config.RATE_LIMIT_PER_HOUR}/час). Попробуйте позже.",
            show_alert=True
        )
        return

    lesson = await db.get_lesson(lesson_id)
    if not lesson:
        return

    # Сохраняем lesson_id в context
    context.user_data["current_lesson_id"] = lesson_id

    await db.update_user_state(tg_id, UserState.WAITING_HW.value)

    hw_type_text = {
        "text": "текстовый ответ",
        "video_link": "ссылку на YouTube видео",
        "file": "файл (PDF или DOCX)"
    }.get(lesson.homework_type, "ответ")

    await query.edit_message_text(
        f"Отправьте {hw_type_text} следующим сообщением:",
        reply_markup=cancel_keyboard()
    )


async def receive_hw_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение текстового ответа на ДЗ"""
    tg_id = update.effective_user.id
    text = update.message.text

    # Проверяем состояние
    user = await db.get_user(tg_id)
    if not user or user.state != UserState.WAITING_HW.value:
        return

    lesson_id = context.user_data.get("current_lesson_id")
    if not lesson_id:
        return

    lesson = await db.get_lesson(lesson_id)
    if not lesson:
        return

    # Проверка на минимальную длину
    if len(text) < config.MIN_ANSWER_LENGTH:
        await update.message.reply_text(
            f"Ответ слишком короткий. Минимум {config.MIN_ANSWER_LENGTH} символов.",
            reply_markup=cancel_keyboard()
        )
        return

    # Для video_link — проверяем YouTube ссылку
    if lesson.homework_type == "video_link":
        if not is_youtube_link(text):
            await update.message.reply_text(
                "Пожалуйста, отправьте ссылку на YouTube видео.",
                reply_markup=cancel_keyboard()
            )
            return
        # Принимаем видео-ссылку
        await accept_homework(update, context, tg_id, lesson, text, "video_link")
        return

    # Для text — принимаем (без AI пока)
    if lesson.homework_type == "text":
        await accept_homework(update, context, tg_id, lesson, text, "text")
        return

    await update.message.reply_text(
        "Ожидался другой формат ответа.",
        reply_markup=cancel_keyboard()
    )


async def receive_hw_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение файла как ДЗ"""
    tg_id = update.effective_user.id

    # Проверяем состояние
    user = await db.get_user(tg_id)
    if not user or user.state != UserState.WAITING_HW.value:
        return

    lesson_id = context.user_data.get("current_lesson_id")
    if not lesson_id:
        return

    lesson = await db.get_lesson(lesson_id)
    if not lesson or lesson.homework_type != "file":
        await update.message.reply_text(
            "Этот урок не требует файл.",
            reply_markup=cancel_keyboard()
        )
        return

    document = update.message.document
    if not document:
        return

    # Проверяем формат
    file_name = document.file_name.lower() if document.file_name else ""
    if not (file_name.endswith(".pdf") or file_name.endswith(".docx")):
        await update.message.reply_text(
            "Принимаем только PDF или DOCX файлы.",
            reply_markup=cancel_keyboard()
        )
        return

    # Проверяем размер
    if document.file_size < 1024:
        await update.message.reply_text(
            "Файл слишком маленький или пустой.",
            reply_markup=cancel_keyboard()
        )
        return

    if document.file_size > 20 * 1024 * 1024:
        await update.message.reply_text(
            "Файл слишком большой (максимум 20 МБ).",
            reply_markup=cancel_keyboard()
        )
        return

    # Принимаем файл
    await accept_homework(update, context, tg_id, lesson, f"file:{document.file_id}", "file")


async def accept_homework(update, context, tg_id: int, lesson, content: str, content_type: str):
    """Принять и засчитать домашнее задание"""

    # Сохраняем submission
    await db.create_submission(
        user_id=tg_id,
        lesson_id=lesson.id,
        content_text=content,
        content_type=content_type,
        ai_verdict="ACCEPT",
        ai_message="Принято"
    )

    # Завершаем урок
    await db.complete_lesson(tg_id, lesson.id)

    # Переводим на следующий урок
    if lesson.order_num < 18:
        next_lesson = await db.get_lesson_by_order(lesson.order_num + 1)
        if next_lesson:
            pool = await get_pool()
            await pool.execute(
                "UPDATE enrollments SET current_lesson_id = $1 WHERE user_id = $2",
                next_lesson.id, tg_id
            )
            await db.set_lesson_status(tg_id, next_lesson.id, "OPEN")

    await db.update_user_state(tg_id, UserState.IDLE.value)

    logger.info(f"ДЗ принято: user={tg_id}, lesson={lesson.id}")

    response = random.choice(FILE_VIDEO_RESPONSES)
    await update.message.reply_text(
        f"{response}\n\nУрок {lesson.order_num} завершён! Следующий урок откроется через 1 день.",
        reply_markup=main_menu_keyboard()
    )


def is_youtube_link(text: str) -> bool:
    """Проверка YouTube ссылки"""
    patterns = [
        r"youtube\.com/watch\?v=",
        r"youtu\.be/",
        r"youtube\.com/shorts/"
    ]
    return any(re.search(p, text) for p in patterns)
