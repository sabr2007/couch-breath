"""
Главная точка входа бота
"""

import asyncio
import logging

from telegram.ext import Application

from bot.config import config


# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def main():
    """Запуск бота"""
    
    # Проверка конфигурации
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(f"❌ {error}")
        return
    
    # Создание приложения
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    # TODO: Регистрация хендлеров
    # TODO: Запуск планировщика
    
    logger.info("🚀 Бот запущен!")
    
    # Запуск
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
