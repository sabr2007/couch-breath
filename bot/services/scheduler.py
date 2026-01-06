"""
Планировщик задач — открытие уроков, напоминания
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import config


# Глобальный планировщик
scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)


async def check_lesson_unlocks():
    """
    Job: Проверка и открытие уроков для всех студентов.
    Запускается ежедневно в 10:00.
    """
    # TODO: Реализовать
    pass


async def send_reminders():
    """
    Job: Отправка напоминаний неактивным студентам.
    Запускается ежедневно в 18:00.
    """
    # TODO: Реализовать
    pass


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


def shutdown_scheduler():
    """Остановка планировщика"""
    scheduler.shutdown()
