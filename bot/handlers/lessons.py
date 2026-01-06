"""
Обработчики просмотра уроков
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.states import UserState
from bot.keyboards import lesson_keyboard, main_menu_keyboard
from bot.database import queries as db
from bot.database.connection import get_pool

logger = logging.getLogger(__name__)


async def current_lesson_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: показать текущий урок"""
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id

    # Получаем зачисление
    enrollment = await db.get_enrollment(tg_id)
    if not enrollment:
        await query.edit_message_text(
            "У вас нет доступа к курсу.",
            reply_markup=main_menu_keyboard()
        )
        return

    # Получаем текущий урок
    lesson = await db.get_lesson(enrollment.current_lesson_id)
    if not lesson:
        await query.edit_message_text(
            "Урок не найден.",
            reply_markup=main_menu_keyboard()
        )
        return

    await show_lesson(query, lesson)


async def view_lesson_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: показать конкретный урок"""
    query = update.callback_query
    await query.answer()

    # Парсим lesson_id из callback_data
    data = query.data  # view_lesson:5
    lesson_id = int(data.split(":")[1])

    lesson = await db.get_lesson(lesson_id)
    if not lesson:
        await query.edit_message_text(
            "Урок не найден.",
            reply_markup=main_menu_keyboard()
        )
        return

    await show_lesson(query, lesson)


async def show_lesson(query, lesson):
    """Отображение урока"""
    tg_id = query.from_user.id
    await db.update_user_state(tg_id, UserState.VIEWING_LESSON.value)

    # Формируем текст урока
    text = f"Урок {lesson.order_num}: {lesson.title}\n\n"

    if lesson.video_url:
        text += f"Видео: {lesson.video_url}\n\n"

    if lesson.content_text:
        text += f"{lesson.content_text}\n\n"

    if lesson.has_homework:
        hw_type_text = {
            "text": "текстовый ответ",
            "video_link": "ссылку на YouTube",
            "file": "файл (PDF или DOCX)"
        }.get(lesson.homework_type, "ответ")
        text += f"Домашнее задание: отправьте {hw_type_text}"
    else:
        text += "Этот урок без домашнего задания."

    await query.edit_message_text(
        text,
        reply_markup=lesson_keyboard(lesson.has_homework, lesson.id),
        disable_web_page_preview=True
    )


async def mark_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: отметить урок без ДЗ как изученный"""
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id
    data = query.data  # mark_done:8
    lesson_id = int(data.split(":")[1])

    lesson = await db.get_lesson(lesson_id)
    if not lesson:
        return

    # Проверяем что урок без ДЗ
    if lesson.has_homework:
        await query.answer("Этот урок требует сдачи ДЗ", show_alert=True)
        return

    # Завершаем урок
    await db.complete_lesson(tg_id, lesson_id)

    # Переводим на следующий урок
    enrollment = await db.get_enrollment(tg_id)
    if enrollment and lesson.order_num < 18:
        next_lesson = await db.get_lesson_by_order(lesson.order_num + 1)
        if next_lesson:
            # Обновляем current_lesson_id
            pool = await get_pool()
            await pool.execute(
                "UPDATE enrollments SET current_lesson_id = $1 WHERE user_id = $2",
                next_lesson.id, tg_id
            )
            await db.set_lesson_status(tg_id, next_lesson.id, "OPEN")

    logger.info(f"Урок {lesson_id} отмечен изученным: {tg_id}")

    await query.edit_message_text(
        f"Урок {lesson.order_num} завершён!\n\nСледующий урок откроется через 1 день.",
        reply_markup=main_menu_keyboard()
    )


async def my_progress_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: показать прогресс"""
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id

    enrollment = await db.get_enrollment(tg_id)
    if not enrollment:
        await query.edit_message_text(
            "У вас нет доступа к курсу.",
            reply_markup=main_menu_keyboard()
        )
        return

    # Считаем завершённые уроки
    pool = await get_pool()
    completed = await pool.fetchval(
        "SELECT COUNT(*) FROM user_progress WHERE user_id = $1 AND status = 'COMPLETED'",
        tg_id
    )

    current_lesson = await db.get_lesson(enrollment.current_lesson_id)
    current_name = current_lesson.title if current_lesson else "—"

    progress_pct = int((completed / 18) * 100) if completed else 0

    text = f"Ваш прогресс\n\nПройдено: {completed} из 18 уроков ({progress_pct}%)\nТекущий урок: {current_name}"

    await query.edit_message_text(
        text,
        reply_markup=main_menu_keyboard()
    )
