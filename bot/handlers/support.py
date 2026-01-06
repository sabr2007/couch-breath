"""
Обработчики вопросов куратору (прокси-поддержка)
"""

from telegram import Update
from telegram.ext import ContextTypes


async def ask_curator_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать задавать вопрос куратору"""
    # TODO: Реализовать
    pass


async def receive_question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение вопроса и пересылка куратору"""
    # TODO: Реализовать
    pass


async def curator_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа куратора (reply) и пересылка студенту"""
    # TODO: Реализовать
    pass
