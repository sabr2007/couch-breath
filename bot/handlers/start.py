"""
Обработчик /start и активации по коду доступа
"""

from telegram import Update
from telegram.ext import ContextTypes


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    # TODO: Реализовать
    pass


async def code_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода кода доступа"""
    # TODO: Реализовать
    pass
