"""
Админ-команды
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import config


def admin_only(func):
    """Декоратор: только для админов"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in config.ADMIN_IDS:
            await update.message.reply_text("⛔ Нет доступа")
            return
        return await func(update, context)
    return wrapper


@admin_only
async def stat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика курса"""
    # TODO: Реализовать
    pass


@admin_only
async def users_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список пользователей"""
    # TODO: Реализовать
    pass


@admin_only
async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка всем студентам"""
    # TODO: Реализовать
    pass


@admin_only
async def add_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить код доступа"""
    # TODO: Реализовать
    pass


@admin_only
async def unlock_all_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открыть все уроки пользователю"""
    # TODO: Реализовать
    pass


@admin_only
async def force_accept_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Засчитать урок вручную"""
    # TODO: Реализовать
    pass


@admin_only
async def backup_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создать и отправить бэкап БД"""
    # TODO: Реализовать
    pass
