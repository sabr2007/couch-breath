"""
Unit-тесты для SQL-запросов

Проверяем корректность запросов к базе данных без зависимостей от scheduler.
"""

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]
from datetime import datetime, timedelta

from bot.database import queries as db
from bot.database.connection import get_pool


# ============================================
# Tests: get_users_ready_for_next_lesson()
# ============================================

@pytest.mark.asyncio
async def test_get_users_ready_for_next_lesson_basic(sample_lessons, enrolled_user):
    """
    Тест: пользователь завершил урок 2 дня назад → должен попасть в список
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок 2 дня назад
    completed_at = datetime.utcnow() - timedelta(days=2)
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

    # Проверяем
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 1
    assert users[0]["user_id"] == user_id
    assert users[0]["current_order"] == 1


@pytest.mark.asyncio
async def test_get_users_ready_not_enough_time(sample_lessons, enrolled_user):
    """
    Тест: урок завершён менее 1 дня назад → НЕ попадает в список
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок 12 часов назад (меньше 1 дня)
    completed_at = datetime.utcnow() - timedelta(hours=12)
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

    # Проверяем
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 0


@pytest.mark.asyncio
async def test_get_users_ready_exactly_1_day_not_enough(sample_lessons, enrolled_user):
    """
    Тест: урок завершён ровно 1 день назад → НЕ попадает в список (нужно 2 дня)
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок ровно 1 день назад
    completed_at = datetime.utcnow() - timedelta(days=1)
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

    # Проверяем — НЕ должен попасть (логика +2 дня)
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 0


@pytest.mark.asyncio
async def test_get_users_ready_exactly_2_days(sample_lessons, enrolled_user):
    """
    Тест: урок завершён ровно 2 дня назад → попадает в список
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок ровно 2 дня назад
    completed_at = datetime.utcnow() - timedelta(days=2)
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

    # Проверяем
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 1


@pytest.mark.asyncio
async def test_get_users_ready_already_unlocked(sample_lessons, enrolled_user):
    """
    Тест: следующий урок уже открыт → НЕ попадает в список (защита от дубликатов)
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]
    next_lesson_id = sample_lessons[1]["id"]

    # Завершаем урок 2 дня назад
    completed_at = datetime.utcnow() - timedelta(days=2)
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

    # Открываем следующий урок вручную
    await pool.execute(
        """
        INSERT INTO user_progress (user_id, lesson_id, status)
        VALUES ($1, $2, 'OPEN')
        """,
        user_id,
        next_lesson_id
    )

    # Проверяем — не должен попасть в список
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 0


@pytest.mark.asyncio
async def test_get_users_ready_last_lesson(sample_lessons, db_pool):
    """
    Тест: пользователь на 18 уроке (последнем) → НЕ попадает в список
    """
    pool = await get_pool()

    # Создаём пользователя на 18 уроке
    user_id = 999999
    last_lesson_id = sample_lessons[17]["id"]  # 18-й урок

    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, NOW())
        """,
        user_id, "last_user", "Last User", "idle"
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, last_lesson_id
    )

    # Завершаем 18 урок 2 дня назад
    completed_at = datetime.utcnow() - timedelta(days=2)
    await pool.execute(
        """
        INSERT INTO user_progress (user_id, lesson_id, status, completed_at)
        VALUES ($1, $2, 'COMPLETED', $3)
        """,
        user_id, last_lesson_id, completed_at
    )

    # Проверяем — не должно быть 19-го урока
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 0


@pytest.mark.asyncio
async def test_get_users_ready_not_completed(sample_lessons, enrolled_user):
    """
    Тест: урок открыт, но не завершён → НЕ попадает в список
    """
    # Урок открыт, но не завершён (status = OPEN)
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 0


# ============================================
# Tests: unlock_next_lesson()
# ============================================

@pytest.mark.asyncio
async def test_unlock_next_lesson_success(sample_lessons, enrolled_user):
    """
    Тест: открытие следующего урока — обновляется enrollment и user_progress
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    current_order = 1

    # Открываем урок 2
    next_lesson_id = await db.unlock_next_lesson(user_id, current_order)

    assert next_lesson_id is not None
    assert next_lesson_id == sample_lessons[1]["id"]

    # Проверяем, что enrollment обновился
    enrollment = await pool.fetchrow(
        "SELECT current_lesson_id FROM enrollments WHERE user_id = $1",
        user_id
    )
    assert enrollment["current_lesson_id"] == next_lesson_id

    # Проверяем, что user_progress создался со статусом OPEN
    progress = await pool.fetchrow(
        "SELECT status FROM user_progress WHERE user_id = $1 AND lesson_id = $2",
        user_id,
        next_lesson_id
    )
    assert progress["status"] == "OPEN"


@pytest.mark.asyncio
async def test_unlock_next_lesson_no_next(sample_lessons, db_pool):
    """
    Тест: нет следующего урока (18 → 19) → возвращает None
    """
    pool = await get_pool()
    user_id = 888888

    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, NOW())
        """,
        user_id, "test", "Test", "idle"
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[17]["id"]
    )

    # Пытаемся открыть урок 19 (не существует)
    next_lesson_id = await db.unlock_next_lesson(user_id, 18)
    assert next_lesson_id is None


@pytest.mark.asyncio
async def test_unlock_next_lesson_idempotent(sample_lessons, enrolled_user):
    """
    Тест: повторный вызов unlock_next_lesson не создаёт дубликатов
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    current_order = 1

    # Открываем урок 2 дважды
    next_lesson_id_1 = await db.unlock_next_lesson(user_id, current_order)
    next_lesson_id_2 = await db.unlock_next_lesson(user_id, current_order)

    assert next_lesson_id_1 == next_lesson_id_2

    # Проверяем, что в user_progress только одна запись
    count = await pool.fetchval(
        "SELECT COUNT(*) FROM user_progress WHERE user_id = $1 AND lesson_id = $2",
        user_id,
        next_lesson_id_1
    )
    assert count == 1


# ============================================
# Tests: get_users_for_reminder()
# ============================================

@pytest.mark.asyncio
async def test_get_users_for_reminder_soft_3_days(sample_lessons, db_pool):
    """
    Тест: пользователь неактивен 3 дня → получает мягкое напоминание
    """
    pool = await get_pool()
    user_id = 222222

    # Создаём пользователя с last_activity = 3 дня назад
    last_activity = datetime.utcnow() - timedelta(days=3)
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id, "inactive_user", "Inactive User", "idle", last_activity
    )

    # Зачисляем
    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[0]["id"]
    )

    # Проверяем
    users = await db.get_users_for_reminder(days=3, reminder_type="soft")
    assert len(users) == 1
    assert users[0].tg_id == user_id


@pytest.mark.asyncio
async def test_get_users_for_reminder_already_sent(sample_lessons, db_pool):
    """
    Тест: напоминание уже отправлено → НЕ попадает в список
    """
    pool = await get_pool()
    user_id = 333333

    # Создаём пользователя
    last_activity = datetime.utcnow() - timedelta(days=3)
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id, "reminded_user", "Reminded User", "idle", last_activity
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[0]["id"]
    )

    # Логируем напоминание
    await db.log_reminder(user_id, "soft")

    # Проверяем — не должен попасть в список
    users = await db.get_users_for_reminder(days=3, reminder_type="soft")
    assert len(users) == 0


@pytest.mark.asyncio
async def test_get_users_for_reminder_strong_7_days(sample_lessons, db_pool):
    """
    Тест: пользователь неактивен 7 дней → получает настойчивое напоминание
    """
    pool = await get_pool()
    user_id = 444444

    last_activity = datetime.utcnow() - timedelta(days=7)
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id, "very_inactive", "Very Inactive", "idle", last_activity
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[0]["id"]
    )

    # Проверяем
    users = await db.get_users_for_reminder(days=7, reminder_type="strong")
    assert len(users) == 1
    assert users[0].tg_id == user_id


@pytest.mark.asyncio
async def test_get_users_for_reminder_too_old(sample_lessons, db_pool):
    """
    Тест: пользователь неактивен 15 дней → НЕ получает напоминание (не спамим)
    """
    pool = await get_pool()
    user_id = 555555

    last_activity = datetime.utcnow() - timedelta(days=15)
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id, "too_old", "Too Old", "idle", last_activity
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[0]["id"]
    )

    # Проверяем — не должен попасть
    users = await db.get_users_for_reminder(days=3, reminder_type="soft")
    assert len(users) == 0


@pytest.mark.asyncio
async def test_get_users_for_reminder_not_enrolled(sample_lessons, db_pool):
    """
    Тест: пользователь не зачислен → НЕ получает напоминание
    """
    pool = await get_pool()
    user_id = 666666

    last_activity = datetime.utcnow() - timedelta(days=3)
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id, "not_enrolled", "Not Enrolled", "idle", last_activity
    )

    # НЕ создаём enrollment

    # Проверяем
    users = await db.get_users_for_reminder(days=3, reminder_type="soft")
    assert len(users) == 0


# ============================================
# Tests: log_reminder()
# ============================================

@pytest.mark.asyncio
async def test_log_reminder_creates_record(sample_lessons, enrolled_user):
    """
    Тест: log_reminder создаёт запись в таблице reminders
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]

    await db.log_reminder(user_id, "soft")

    # Проверяем
    reminder = await pool.fetchrow(
        "SELECT * FROM reminders WHERE user_id = $1 AND reminder_type = $2",
        user_id, "soft"
    )

    assert reminder is not None
    assert reminder["user_id"] == user_id
    assert reminder["reminder_type"] == "soft"


@pytest.mark.asyncio
async def test_log_reminder_idempotent(sample_lessons, enrolled_user):
    """
    Тест: повторный вызов log_reminder не создаёт дубликатов
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]

    await db.log_reminder(user_id, "soft")
    await db.log_reminder(user_id, "soft")

    # Проверяем — только одна запись
    count = await pool.fetchval(
        "SELECT COUNT(*) FROM reminders WHERE user_id = $1 AND reminder_type = $2",
        user_id, "soft"
    )
    assert count == 1


# ============================================
# Tests: update_last_activity()
# ============================================

@pytest.mark.asyncio
async def test_update_last_activity_clears_reminders(sample_lessons, enrolled_user):
    """
    Тест: update_last_activity очищает напоминания
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]

    # Создаём напоминания
    await db.log_reminder(user_id, "soft")
    await db.log_reminder(user_id, "strong")

    # Обновляем активность
    await db.update_last_activity(user_id)

    # Проверяем — напоминания удалены
    count = await pool.fetchval(
        "SELECT COUNT(*) FROM reminders WHERE user_id = $1",
        user_id
    )
    assert count == 0
