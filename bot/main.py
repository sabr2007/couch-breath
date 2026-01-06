"""
Главная точка входа бота
"""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from bot.config import config
from bot.database.connection import get_pool, close_pool
from bot.database.migrations import run_migrations
from bot.services.scheduler import setup_scheduler, shutdown_scheduler, set_bot

# Хендлеры
from bot.handlers.start import (
    start_handler,
    enter_code_callback,
    code_input_handler,
    contact_support_callback,
    main_menu_callback,
    cancel_callback
)
from bot.handlers.lessons import (
    current_lesson_callback,
    view_lesson_callback,
    mark_done_callback,
    my_progress_callback
)
from bot.handlers.homework import (
    submit_hw_callback,
    receive_hw_text_handler,
    receive_hw_file_handler
)
from bot.handlers.admin import (
    stat_handler,
    users_handler,
    add_code_handler,
    codes_handler,
    broadcast_handler,
    unlock_all_handler,
    force_accept_handler
)
from bot.handlers.support import (
    ask_curator_callback,
    receive_question_handler,
    curator_reply_handler
)


# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def receive_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Универсальный обработчик текстовых сообщений"""
    # Сначала проверяем ответ куратора
    await curator_reply_handler(update, context)
    # Затем вопрос от студента
    await receive_question_handler(update, context)
    # Пытаемся обработать как код доступа
    await code_input_handler(update, context)
    # Затем как ДЗ
    await receive_hw_text_handler(update, context)


async def receive_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фото и голосовых сообщений (для вопросов куратору)"""
    await receive_question_handler(update, context)


def register_handlers(app: Application):
    """Регистрация всех хендлеров"""

    # Команды пользователей
    app.add_handler(CommandHandler("start", start_handler))

    # Админ-команды
    app.add_handler(CommandHandler("stat", stat_handler))
    app.add_handler(CommandHandler("users", users_handler))
    app.add_handler(CommandHandler("add_code", add_code_handler))
    app.add_handler(CommandHandler("codes", codes_handler))
    app.add_handler(CommandHandler("broadcast", broadcast_handler))
    app.add_handler(CommandHandler("unlock_all", unlock_all_handler))
    app.add_handler(CommandHandler("force_accept", force_accept_handler))

    # Callbacks — start
    app.add_handler(CallbackQueryHandler(enter_code_callback, pattern="^enter_code$"))
    app.add_handler(CallbackQueryHandler(contact_support_callback, pattern="^contact_support$"))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(cancel_callback, pattern="^cancel$"))

    # Callbacks — lessons
    app.add_handler(CallbackQueryHandler(current_lesson_callback, pattern="^current_lesson$"))
    app.add_handler(CallbackQueryHandler(view_lesson_callback, pattern="^view_lesson:"))
    app.add_handler(CallbackQueryHandler(mark_done_callback, pattern="^mark_done:"))
    app.add_handler(CallbackQueryHandler(my_progress_callback, pattern="^my_progress$"))

    # Callbacks — homework
    app.add_handler(CallbackQueryHandler(submit_hw_callback, pattern="^submit_hw:"))

    # Callbacks — support
    app.add_handler(CallbackQueryHandler(ask_curator_callback, pattern="^ask_curator:"))

    # Message handlers
    app.add_handler(MessageHandler(filters.Document.ALL, receive_hw_file_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VOICE, receive_media_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text_handler))


async def post_init(app: Application):
    """Инициализация после запуска"""
    await get_pool()
    await run_migrations()
    logger.info("База данных подключена, миграции выполнены")

    # Запускаем планировщик
    set_bot(app.bot)
    setup_scheduler()
    logger.info("Планировщик запущен")


async def post_shutdown(app: Application):
    """Очистка при завершении"""
    shutdown_scheduler()
    await close_pool()
    logger.info("Соединение с БД закрыто")


def main():
    """Запуск бота"""

    # Проверка конфигурации
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(f"Ошибка конфигурации: {error}")
        return

    # Создание приложения
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Регистрация хендлеров
    register_handlers(app)

    logger.info("Бот запущен!")

    # Запуск
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
