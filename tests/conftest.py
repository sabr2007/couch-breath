"""
Pytest конфигурация и фикстуры для тестирования
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import AsyncGenerator

import asyncpg
import pytest
import pytest_asyncio
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
from bot.database import connection as db_connection
from bot.database.connection import get_pool, close_pool
from bot.database.migrations import run_migrations


# ============================================
# Pytest Configuration
# ============================================

@pytest.fixture(scope="function")
def event_loop():
    """Создать event loop для каждого теста"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    # Закрываем все pending tasks перед закрытием loop
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


# ============================================
# Database Fixtures
# ============================================

@pytest_asyncio.fixture
async def db_pool():
    """
    Фикстура для подключения к БД.
    Создаёт пул, применяет миграции, очищает данные.
    """
    db_url = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/couch_breath_test")
    
    # Создаём новый пул для этого теста
    pool = await asyncpg.create_pool(
        db_url,
        min_size=1,
        max_size=5
    )
    
    # Применяем миграции (создаём таблицы если не существуют)
    async with pool.acquire() as conn:
        # Создаём таблицы если не существуют
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                tg_id BIGINT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                state TEXT DEFAULT 'idle',
                last_activity TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id SERIAL PRIMARY KEY,
                order_num INTEGER NOT NULL UNIQUE,
                title TEXT NOT NULL,
                content_text TEXT,
                video_url TEXT,
                has_homework BOOLEAN DEFAULT FALSE,
                homework_type TEXT DEFAULT 'text',
                homework_description TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS enrollments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(tg_id),
                current_lesson_id INTEGER,
                enrolled_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(tg_id),
                lesson_id INTEGER,
                status TEXT DEFAULT 'OPEN',
                completed_at TIMESTAMP,
                UNIQUE(user_id, lesson_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(tg_id),
                lesson_id INTEGER,
                content_text TEXT,
                content_type TEXT,
                ai_verdict TEXT,
                ai_message TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS access_codes (
                id SERIAL PRIMARY KEY,
                code TEXT NOT NULL UNIQUE,
                is_used BOOLEAN DEFAULT FALSE,
                used_by BIGINT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(tg_id),
                reminder_type TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, reminder_type)
            )
        """)
        # Явно создаём уникальный индекс для ON CONFLICT (если отсутствует)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS reminders_user_type_idx
            ON reminders (user_id, reminder_type)
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS support_questions (
                id SERIAL PRIMARY KEY,
                message_id BIGINT,
                student_id BIGINT,
                lesson_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
    
    # Очищаем данные
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE support_questions CASCADE")
        await conn.execute("TRUNCATE TABLE reminders CASCADE")
        await conn.execute("TRUNCATE TABLE submissions CASCADE")
        await conn.execute("TRUNCATE TABLE user_progress CASCADE")
        await conn.execute("TRUNCATE TABLE enrollments CASCADE")
        await conn.execute("TRUNCATE TABLE access_codes CASCADE")
        await conn.execute("TRUNCATE TABLE lessons CASCADE")
        await conn.execute("TRUNCATE TABLE users CASCADE")
    
    yield pool

    # Сбрасываем глобальный пул из bot.database.connection
    # чтобы следующий тест получил новый пул
    if db_connection._pool is not None:
        try:
            await db_connection._pool.close()
        except Exception:
            pass
        db_connection._pool = None

    # Закрываем пул после теста
    await pool.close()


# ============================================
# Data Fixtures
# ============================================

@pytest_asyncio.fixture
async def sample_lessons(db_pool):
    """Создать тестовые уроки (18 штук)"""
    lessons = []
    async with db_pool.acquire() as conn:
        for i in range(1, 19):
            lesson = await conn.fetchrow(
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


@pytest_asyncio.fixture
async def sample_user(db_pool):
    """Создать тестового пользователя"""
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
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


@pytest_asyncio.fixture
async def enrolled_user(sample_user, sample_lessons, db_pool):
    """Создать зачисленного пользователя на первом уроке"""
    first_lesson_id = sample_lessons[0]["id"]
    
    async with db_pool.acquire() as conn:
        # Создаём enrollment
        enrollment = await conn.fetchrow(
            """
            INSERT INTO enrollments (user_id, current_lesson_id)
            VALUES ($1, $2)
            RETURNING *
            """,
            sample_user["tg_id"],
            first_lesson_id
        )
        
        # Открываем первый урок
        await conn.execute(
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
        "current_lesson_id": first_lesson_id,
        "pool": db_pool
    }


# ============================================
# Mock Fixtures
# ============================================

@pytest.fixture
def mock_bot():
    """Мок Telegram бота"""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot
