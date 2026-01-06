"""
Обработчики сдачи домашних заданий
"""

import logging
import re
from telegram import Update
from telegram.ext import ContextTypes

from bot.states import UserState
from bot.keyboards import main_menu_keyboard, cancel_keyboard
from bot.database import queries as db
from bot.database.connection import get_pool
from bot.config import config
from bot.services.llm import check_homework_with_ai, get_file_video_response

logger = logging.getLogger(__name__)


async def submit_hw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: начать сдачу ДЗ"""
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id
    data = query.data  # submit_hw:5
    lesson_id = int(data.split(":")[1])

    # Проверяем, не сдано ли уже ДЗ
    if await db.has_accepted_submission(tg_id, lesson_id):
        await query.edit_message_text(
            "✅ Домашнее задание по этому уроку уже принято!\n\n"
            "Ожидайте открытия следующего урока (через 1 день после сдачи).",
            reply_markup=main_menu_keyboard()
        )
        return

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

    # Формируем текст с заданием
    hw_text = ""
    if lesson.content_text:
        hw_text = f"📝 Задание:\n{lesson.content_text}\n\n"

    await query.edit_message_text(
        f"{hw_text}Отправьте {hw_type_text} следующим сообщением:",
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

    # Для text — проверяем через AI
    if lesson.homework_type == "text":
        # Показываем что проверяем
        await db.update_user_state(tg_id, UserState.PROCESSING.value)
        processing_msg = await update.message.reply_text("⏳ Проверяю ответ...")

        # Вызываем AI
        result = await check_homework_with_ai(
            lesson_number=lesson.order_num,
            lesson_topic=lesson.title,
            homework_task=lesson.content_text or "",
            user_answer=text
        )

        await processing_msg.delete()

        if result["verdict"] == "ACCEPT":
            await accept_homework(update, context, tg_id, lesson, text, "text", result["message"])
        else:
            # REVISE — просим доработать
            await db.create_submission(
                user_id=tg_id,
                lesson_id=lesson.id,
                content_text=text,
                content_type="text",
                ai_verdict="REVISE",
                ai_message=result["message"]
            )
            await db.update_user_state(tg_id, UserState.WAITING_HW.value)
            await update.message.reply_text(
                f"{result['message']}\n\nПопробуй ещё раз:",
                reply_markup=cancel_keyboard()
            )
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


async def accept_homework(update, context, tg_id: int, lesson, content: str, content_type: str, ai_message: str = None):
    """Принять и засчитать домашнее задание"""

    # Для файлов/видео — получаем стандартный ответ
    if ai_message is None:
        response_data = get_file_video_response()
        ai_message = response_data["message"]

    # Сохраняем submission
    await db.create_submission(
        user_id=tg_id,
        lesson_id=lesson.id,
        content_text=content,
        content_type=content_type,
        ai_verdict="ACCEPT",
        ai_message=ai_message
    )

    # Завершаем урок
    await db.complete_lesson(tg_id, lesson.id)

    # НЕ открываем следующий урок сразу — это сделает scheduler через 1 день

    await db.update_user_state(tg_id, UserState.IDLE.value)

    logger.info(f"ДЗ принято: user={tg_id}, lesson={lesson.id}")

    # Определяем финальное сообщение
    if lesson.order_num >= 18:
        final_text = f"{ai_message}\n\n🎉 Поздравляю! Ты прошёл весь курс!"
    else:
        final_text = f"{ai_message}\n\nУрок {lesson.order_num} завершён! Следующий урок откроется через 1 день."

    await update.message.reply_text(final_text, reply_markup=main_menu_keyboard())


def is_youtube_link(text: str) -> bool:
    """Проверка YouTube ссылки"""
    patterns = [
        r"youtube\.com/watch\?v=",
        r"youtu\.be/",
        r"youtube\.com/shorts/"
    ]
    return any(re.search(p, text) for p in patterns)
