"""
Обработчики просмотра уроков
"""

from telegram import Update
from telegram.ext import ContextTypes


async def show_lesson_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущий урок"""
    # TODO: Реализовать
    pass


async def lesson_completed_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отметить урок как изученный (для уроков без ДЗ)"""
    # TODO: Реализовать
    pass
