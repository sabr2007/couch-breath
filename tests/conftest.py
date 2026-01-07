"""
Pytest конфигурация и фикстуры для тестирования
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator

import asyncpg
import pytest
from unittest.mock import AsyncMock, Mock

# Устанавливаем тестовые переменные окружения до импорта bot
os.environ.update({
    "BOT_TOKEN": "test_token",
    "DATABASE_URL": os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/couch_breath_test"),
    "OPENAI_API_KEY": "test_key",
    "CURATOR_ID": "123456789",
    "ADMIN_IDS": "123456789",
    "TIMEZONE": "UTC"
})

from bot.database import queries as db
from bot.database.connection import get_pool, init_db, close_db


# ============================================
# Pytest Configuration
# ============================================

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Создать event loop для всей сессии тестов"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================
# Database Fixtures
# ============================================

@pytest.fixture(scope="session")
async def test_db():
    """
    Инициализация тестовой БД для всей сессии тестов.
    Создаёт схему БД один раз в начале.
    """
    await init_db()
    yield
    await close_db()


@pytest.fixture
async def db_clean(test_db):
    """
    Очистка БД перед каждым тестом.
    Удаляет все данные, но сохраняет схему.
    """
    pool = await get_pool()

    # Очищаем все таблицы в правильном порядке (из-за foreign keys)
    await pool.execute("TRUNCATE TABLE support_questions CASCADE")
    await pool.execute("TRUNCATE TABLE reminders CASCADE")
    await pool.execute("TRUNCATE TABLE submissions CASCADE")
    await pool.execute("TRUNCATE TABLE user_progress CASCADE")
    await pool.execute("TRUNCATE TABLE enrollments CASCADE")
    await pool.execute("TRUNCATE TABLE access_codes CASCADE")
    await pool.execute("TRUNCATE TABLE lessons CASCADE")
    await pool.execute("TRUNCATE TABLE users CASCADE")

    yield pool


# ============================================
# Data Fixtures
# ============================================

@pytest.fixture
async def sample_lessons(db_clean):
    """Создать тестовые уроки (18 штук)"""
    pool = await get_pool()

    lessons = []
    for i in range(1, 19):
        lesson = await pool.fetchrow(
            """
            INSERT INTO lessons (order_num, title, content_text, video_url, has_homework, homework_type)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, order_num
            """,
            i,
            f"Урок {i}: Тестовый урок",
            f"Контент урока {i}",
            f"https://example.com/video{i}",
            True,
            "text"
        )
        lessons.append({"id": lesson["id"], "order_num": lesson["order_num"]})

    return lessons


@pytest.fixture
async def sample_user(db_clean):
    """Создать тестового пользователя"""
    pool = await get_pool()

    user = await pool.fetchrow(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, NOW())
        RETURNING *
        """,
        111111111,
        "test_user",
        "Test User",
        "idle"
    )

    return dict(user)


@pytest.fixture
async def enrolled_user(sample_user, sample_lessons):
    """Создать зачисленного пользователя на первом уроке"""
    pool = await get_pool()

    first_lesson_id = sample_lessons[0]["id"]

    # Создаём enrollment
    enrollment = await pool.fetchrow(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        RETURNING *
        """,
        sample_user["tg_id"],
        first_lesson_id
    )

    # Открываем первый урок
    await pool.execute(
        """
        INSERT INTO user_progress (user_id, lesson_id, status)
        VALUES ($1, $2, 'OPEN')
        """,
        sample_user["tg_id"],
        first_lesson_id
    )

    return {
        "user": sample_user,
        "enrollment": dict(enrollment),
        "lessons": sample_lessons,
        "current_lesson_id": first_lesson_id
    }


@pytest.fixture
async def completed_lesson_user(enrolled_user):
    """Пользователь с завершённым первым уроком N дней назад"""
    async def _factory(days_ago: int = 2):
        pool = await get_pool()
        user_id = enrolled_user["user"]["tg_id"]
        lesson_id = enrolled_user["current_lesson_id"]

        # Завершаем урок с заданной датой
        completed_at = datetime.utcnow() - timedelta(days=days_ago)
        await pool.execute(
            """
            UPDATE user_progress
            SET status = 'COMPLETED', completed_at = $3
            WHERE user_id = $1 AND lesson_id = $2
            """,
            user_id,
            lesson_id,
            completed_at
        )

        return enrolled_user

    return _factory


# ============================================
# Mock Fixtures
# ============================================

@pytest.fixture
def mock_bot():
    """Мок Telegram бота"""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def mock_time():
    """
    Фикстура для управления временем в тестах.
    Возвращает функцию для установки фиксированного времени.
    """
    class TimeMocker:
        def __init__(self):
            self.current_time = datetime.utcnow()

        def set(self, dt: datetime):
            """Установить текущее время"""
            self.current_time = dt

        def advance_days(self, days: int):
            """Продвинуть время вперёд на N дней"""
            self.current_time += timedelta(days=days)

        def now(self):
            """Получить текущее время"""
            return self.current_time

    return TimeMocker()


# ============================================
# Utility Functions
# ============================================

@pytest.fixture
async def create_user_with_progress():
    """
    Фабрика для создания пользователя с прогрессом на определённом уроке.
    """
    async def _factory(
        tg_id: int,
        current_lesson_order: int,
        lessons_completed: list[int] = None,
        last_activity_days_ago: int = 0
    ):
        pool = await get_pool()

        # Создаём пользователя
        last_activity = datetime.utcnow() - timedelta(days=last_activity_days_ago)
        await pool.execute(
            """
            INSERT INTO users (tg_id, username, full_name, state, last_activity)
            VALUES ($1, $2, $3, $4, $5)
            """,
            tg_id,
            f"user_{tg_id}",
            f"User {tg_id}",
            "idle",
            last_activity
        )

        # Получаем урок
        current_lesson = await pool.fetchrow(
            "SELECT id FROM lessons WHERE order_num = $1",
            current_lesson_order
        )

        if not current_lesson:
            raise ValueError(f"Lesson {current_lesson_order} not found")

        current_lesson_id = current_lesson["id"]

        # Создаём enrollment
        await pool.execute(
            """
            INSERT INTO enrollments (user_id, current_lesson_id)
            VALUES ($1, $2)
            """,
            tg_id,
            current_lesson_id
        )

        # Завершаем указанные уроки
        if lessons_completed:
            for lesson_order in lessons_completed:
                lesson = await pool.fetchrow(
                    "SELECT id FROM lessons WHERE order_num = $1",
                    lesson_order
                )
                if lesson:
                    await pool.execute(
                        """
                        INSERT INTO user_progress (user_id, lesson_id, status, completed_at)
                        VALUES ($1, $2, 'COMPLETED', NOW() - INTERVAL '3 days')
                        """,
                        tg_id,
                        lesson["id"]
                    )

        # Открываем текущий урок
        await pool.execute(
            """
            INSERT INTO user_progress (user_id, lesson_id, status)
            VALUES ($1, $2, 'OPEN')
            ON CONFLICT (user_id, lesson_id) DO NOTHING
            """,
            tg_id,
            current_lesson_id
        )

        return {
            "tg_id": tg_id,
            "current_lesson_id": current_lesson_id,
            "current_lesson_order": current_lesson_order
        }

    return _factory
