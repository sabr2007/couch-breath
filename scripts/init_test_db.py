#!/usr/bin/env python3
"""
Скрипт для инициализации тестовой БД

Использование:
    python scripts/init_test_db.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


async def init_test_database():
    """Инициализировать тестовую БД"""

    # Проверяем переменную окружения
    test_db_url = os.getenv("TEST_DATABASE_URL")
    if not test_db_url:
        print("❌ Ошибка: TEST_DATABASE_URL не установлена")
        print("Установите переменную окружения:")
        print('  export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/couch_breath_test"')
        sys.exit(1)

    print(f"📦 Инициализация тестовой БД: {test_db_url}")

    # Временно заменяем DATABASE_URL на TEST_DATABASE_URL
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_db_url

    try:
        # Импортируем после установки переменной
        from bot.database.migrations import run_migrations
        from bot.database.connection import init_db, close_db

        # Инициализируем БД
        await init_db()

        # Запускаем миграции
        print("🔧 Применение миграций...")
        await run_migrations()

        print("✅ Тестовая БД успешно инициализирована")

        # Закрываем соединение
        await close_db()

    except Exception as e:
        print(f"❌ Ошибка при инициализации БД: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Восстанавливаем оригинальное значение
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            del os.environ["DATABASE_URL"]


if __name__ == "__main__":
    asyncio.run(init_test_database())
