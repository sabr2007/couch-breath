"""
Админ-команды
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import config
from bot.database import queries as db
from bot.database.connection import get_pool

logger = logging.getLogger(__name__)


def admin_only(func):
    """Декоратор: только для админов"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in config.ADMIN_IDS:
            await update.message.reply_text("Нет доступа")
            return
        return await func(update, context)
    return wrapper


@admin_only
async def stat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика курса"""
    pool = await get_pool()

    total_users = await pool.fetchval("SELECT COUNT(*) FROM enrollments")
    completed_all = await pool.fetchval(
        "SELECT COUNT(DISTINCT user_id) FROM user_progress WHERE status = 'COMPLETED' GROUP BY user_id HAVING COUNT(*) = 18"
    ) or 0

    text = f"Статистика курса\n\nВсего студентов: {total_users}\nЗавершили курс: {completed_all}"

    await update.message.reply_text(text)


@admin_only
async def users_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список пользователей"""
    users = await db.get_all_enrolled_users()

    if not users:
        await update.message.reply_text("Нет зачисленных студентов")
        return

    lines = []
    for u in users[:20]:  # Ограничиваем до 20
        lines.append(f"- @{u.username or u.tg_id}")

    text = f"Студенты ({len(users)}):\n" + "\n".join(lines)
    if len(users) > 20:
        text += f"\n... и ещё {len(users) - 20}"

    await update.message.reply_text(text)


@admin_only
async def add_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить код доступа"""
    if not context.args:
        await update.message.reply_text("Использование: /add_code <код>")
        return

    code = context.args[0]

    # Проверяем существование
    existing = await db.get_access_code(code)
    if existing:
        await update.message.reply_text(f"Код уже существует: {code}")
        return

    await db.create_access_code(code)
    logger.info(f"Добавлен код доступа: {code}")

    await update.message.reply_text(f"Код добавлен: {code}")


@admin_only
async def codes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список неиспользованных кодов"""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT code FROM access_codes WHERE is_used = FALSE ORDER BY created_at DESC LIMIT 20"
    )

    if not rows:
        await update.message.reply_text("Нет свободных кодов")
        return

    codes = [row["code"] for row in rows]
    text = "Свободные коды:\n" + "\n".join(codes)

    await update.message.reply_text(text)


@admin_only
async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка всем студентам"""
    if not context.args:
        await update.message.reply_text("Использование: /broadcast <текст>")
        return

    message_text = " ".join(context.args)
    users = await db.get_all_enrolled_users()

    sent = 0
    failed = 0

    for user in users:
        try:
            await context.bot.send_message(user.tg_id, message_text)
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"Рассылка завершена\nОтправлено: {sent}\nОшибок: {failed}"
    )


@admin_only
async def unlock_all_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открыть все уроки пользователю"""
    if not context.args:
        await update.message.reply_text("Использование: /unlock_all <tg_id>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Неверный ID")
        return

    # Открываем все уроки
    for i in range(1, 19):
        await db.set_lesson_status(target_id, i, "OPEN")

    await update.message.reply_text(f"Все уроки открыты для {target_id}")


@admin_only
async def force_accept_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Засчитать урок вручную"""
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /force_accept <tg_id> <lesson_num>")
        return

    try:
        target_id = int(context.args[0])
        lesson_num = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Неверные параметры")
        return

    lesson = await db.get_lesson_by_order(lesson_num)
    if not lesson:
        await update.message.reply_text("Урок не найден")
        return

    await db.complete_lesson(target_id, lesson.id)
    await update.message.reply_text(f"Урок {lesson_num} засчитан для {target_id}")


@admin_only
async def backup_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создать и отправить бэкап БД"""
    await update.message.reply_text("Функция бэкапа пока не реализована")
