"""
Отправка уведомлений пользователям
"""

from telegram import Bot
from telegram.error import TelegramError

from bot.config import config


async def send_lesson_notification(bot: Bot, user_id: int, lesson_num: int, lesson_title: str):
    """Уведомление об открытии нового урока"""
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"🎉 Открылся Урок {lesson_num}: {lesson_title}!\n\n"
                f"Нажми кнопку ниже, чтобы начать."
            )
            # TODO: добавить reply_markup с кнопкой урока
        )
        return True
    except TelegramError:
        return False


async def send_reminder(bot: Bot, user_id: int, message: str):
    """Отправка напоминания неактивному студенту"""
    try:
        await bot.send_message(chat_id=user_id, text=message)
        return True
    except TelegramError:
        return False


async def forward_to_curator(bot: Bot, user_id: int, username: str, lesson_num: int, question: str):
    """Пересылка вопроса куратору"""
    try:
        await bot.send_message(
            chat_id=config.CURATOR_ID,
            text=(
                f"👤 User: @{username} (ID: {user_id})\n"
                f"Урок: {lesson_num}\n"
                f"───────────────────────────\n"
                f"{question}"
            )
        )
        return True
    except TelegramError:
        return False
