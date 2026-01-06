"""
Планировщик задач — открытие уроков, напоминания
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import config
from bot.database import queries as db

logger = logging.getLogger(__name__)

# Глобальный планировщик
scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)

# Ссылка на бота (устанавливается при старте)
_bot = None


def set_bot(bot):
    """Установить ссылку на бота для отправки уведомлений"""
    global _bot
    _bot = bot


async def check_lesson_unlocks():
    """
    Job: Проверка и открытие уроков для всех студентов.
    Условие: прошло >= 1 день с завершения текущего урока.
    """
    logger.info("Scheduler: проверяю открытие уроков...")

    try:
        users = await db.get_users_ready_for_next_lesson()
        unlocked_count = 0

        for user_data in users:
            user_id = user_data["user_id"]
            current_order = user_data["current_order"]

            next_lesson_id = await db.unlock_next_lesson(user_id, current_order)

            if next_lesson_id and _bot:
                # Отправляем уведомление
                try:
                    next_lesson = await db.get_lesson(next_lesson_id)
                    await _bot.send_message(
                        user_id,
                        f"🔓 Открыт новый урок!\n\n"
                        f"Урок {next_lesson.order_num}: {next_lesson.title}\n\n"
                        f"Нажми /start чтобы продолжить обучение."
                    )
                    unlocked_count += 1
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление {user_id}: {e}")

        logger.info(f"Scheduler: открыто уроков: {unlocked_count}")

    except Exception as e:
        logger.error(f"Scheduler error in check_lesson_unlocks: {e}")


async def send_reminders():
    """
    Job: Отправка напоминаний неактивным студентам.
    Запускается ежедневно в 18:00.

    Логика (без спама):
    - 3 дня неактивности → мягкое напоминание (единоразово)
    - 7 дней неактивности → настойчивое напоминание (единоразово)
    - После 14 дней → не беспокоим
    """
    logger.info("Scheduler: отправляю напоминания...")

    try:
        sent_count = 0

        # 1. Мягкое напоминание (3 дня)
        soft_users = await db.get_users_for_reminder(days=3, reminder_type="soft")
        for user in soft_users:
            if _bot:
                try:
                    await _bot.send_message(
                        user.tg_id,
                        "👋 Привет! Заметил, что ты давно не заходил.\n\n"
                        "Не забрось курс — каждый урок важен для твоего развития как тренера.\n\n"
                        "Нажми /start чтобы продолжить обучение."
                    )
                    await db.log_reminder(user.tg_id, "soft")
                    sent_count += 1
                except Exception as e:
                    logger.warning(f"Не удалось отправить мягкое напоминание {user.tg_id}: {e}")

        # 2. Настойчивое напоминание (7 дней)
        strong_users = await db.get_users_for_reminder(days=7, reminder_type="strong")
        for user in strong_users:
            if _bot:
                try:
                    await _bot.send_message(
                        user.tg_id,
                        "🔔 Ты не заходил уже неделю!\n\n"
                        "Курс ждёт тебя. Помни: регулярность — ключ к успеху.\n\n"
                        "Нажми /start чтобы вернуться к обучению."
                    )
                    await db.log_reminder(user.tg_id, "strong")
                    sent_count += 1
                except Exception as e:
                    logger.warning(f"Не удалось отправить настойчивое напоминание {user.tg_id}: {e}")

        logger.info(f"Scheduler: отправлено напоминаний: {sent_count}")

    except Exception as e:
        logger.error(f"Scheduler error in send_reminders: {e}")


def setup_scheduler():
    """Настройка планировщика"""

    # Проверка открытия уроков — каждый день в 10:00
    scheduler.add_job(
        check_lesson_unlocks,
        CronTrigger(hour=10, minute=0, timezone=config.TIMEZONE),
        id="check_lesson_unlocks",
        replace_existing=True
    )

    # Напоминания — каждый день в 18:00
    scheduler.add_job(
        send_reminders,
        CronTrigger(hour=18, minute=0, timezone=config.TIMEZONE),
        id="send_reminders",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler запущен")


def shutdown_scheduler():
    """Остановка планировщика"""
    scheduler.shutdown()
    logger.info("Scheduler остановлен")
