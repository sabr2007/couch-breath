"""
Обработчики сдачи домашних заданий
"""

from telegram import Update
from telegram.ext import ContextTypes


async def submit_hw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать сдачу ДЗ (переход в WAITING_HW)"""
    # TODO: Реализовать
    pass


async def receive_hw_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение текстового ответа на ДЗ"""
    # TODO: Реализовать
    pass


async def receive_hw_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение файла (PDF/DOCX) как ДЗ"""
    # TODO: Реализовать
    pass


async def receive_hw_video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение ссылки на YouTube как ДЗ"""
    # TODO: Реализовать
    pass
