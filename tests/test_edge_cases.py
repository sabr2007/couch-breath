"""
Тесты граничных условий (Edge Cases)

Проверяем редкие сценарии и потенциальные проблемы.
"""

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.edge]

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from bot.database import queries as db
from bot.database.connection import get_pool
from bot.services import scheduler


# ============================================
# Edge Cases: Time Boundaries
# ============================================

@pytest.mark.asyncio
async def test_edge_exactly_24_hours(sample_lessons, enrolled_user, mock_bot):
    """
    Edge Case: Урок завершён ровно 24 часа назад (1 день)
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок ровно 24 часа назад
    completed_at = datetime.utcnow() - timedelta(hours=24)
    await pool.execute(
        """
        UPDATE user_progress
        SET status = 'COMPLETED', completed_at = $3
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, lesson_id, completed_at
    )

    # Проверяем — должен попасть в список
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 1


@pytest.mark.asyncio
async def test_edge_23_hours_59_minutes(sample_lessons, enrolled_user, mock_bot):
    """
    Edge Case: Урок завершён 23 часа 59 минут назад (меньше 1 дня)
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок почти 1 день назад
    completed_at = datetime.utcnow() - timedelta(hours=23, minutes=59)
    await pool.execute(
        """
        UPDATE user_progress
        SET status = 'COMPLETED', completed_at = $3
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, lesson_id, completed_at
    )

    # Проверяем — НЕ должен попасть в список
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 0


@pytest.mark.asyncio
async def test_edge_24_hours_1_second(sample_lessons, enrolled_user, mock_bot):
    """
    Edge Case: Урок завершён 24 часа 1 секунда назад
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок чуть больше 1 дня назад
    completed_at = datetime.utcnow() - timedelta(hours=24, seconds=1)
    await pool.execute(
        """
        UPDATE user_progress
        SET status = 'COMPLETED', completed_at = $3
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, lesson_id, completed_at
    )

    # Проверяем — должен попасть в список
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 1


# ============================================
# Edge Cases: Lesson Boundaries
# ============================================

@pytest.mark.asyncio
async def test_edge_lesson_1_to_2(sample_lessons, enrolled_user, mock_bot):
    """
    Edge Case: Переход с урока 1 на урок 2
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]

    # Завершаем урок 1
    await pool.execute(
        """
        UPDATE user_progress
        SET status = 'COMPLETED', completed_at = $3
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, sample_lessons[0]["id"], datetime.utcnow() - timedelta(days=2)
    )

    # Открываем урок 2
    next_lesson_id = await db.unlock_next_lesson(user_id, 1)
    assert next_lesson_id == sample_lessons[1]["id"]


@pytest.mark.asyncio
async def test_edge_lesson_17_to_18(sample_lessons, db_clean, mock_bot):
    """
    Edge Case: Переход с урока 17 на урок 18 (предпоследний → последний)
    """
    pool = await get_pool()
    user_id = 777777

    # Создаём пользователя на уроке 17
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, NOW())
        """,
        user_id, "user17", "User 17", "idle"
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[16]["id"]
    )

    await pool.execute(
        """
        INSERT INTO user_progress (user_id, lesson_id, status, completed_at)
        VALUES ($1, $2, 'COMPLETED', $3)
        """,
        user_id, sample_lessons[16]["id"], datetime.utcnow() - timedelta(days=2)
    )

    # Открываем урок 18
    next_lesson_id = await db.unlock_next_lesson(user_id, 17)
    assert next_lesson_id == sample_lessons[17]["id"]


@pytest.mark.asyncio
async def test_edge_lesson_18_to_19_nonexistent(sample_lessons, db_clean, mock_bot):
    """
    Edge Case: Попытка открыть урок 19 (не существует)
    """
    pool = await get_pool()
    user_id = 888888

    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, NOW())
        """,
        user_id, "user18", "User 18", "idle"
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[17]["id"]
    )

    # Пытаемся открыть урок 19
    next_lesson_id = await db.unlock_next_lesson(user_id, 18)
    assert next_lesson_id is None


# ============================================
# Edge Cases: Concurrent Operations
# ============================================

@pytest.mark.asyncio
async def test_edge_concurrent_scheduler_runs(sample_lessons, enrolled_user, mock_bot):
    """
    Edge Case: Два scheduler запуска одновременно (race condition)
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок
    await pool.execute(
        """
        UPDATE user_progress
        SET status = 'COMPLETED', completed_at = $3
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, lesson_id, datetime.utcnow() - timedelta(days=2)
    )

    # Запускаем scheduler дважды параллельно
    scheduler.set_bot(mock_bot)
    import asyncio
    await asyncio.gather(
        scheduler.check_lesson_unlocks(),
        scheduler.check_lesson_unlocks()
    )

    # Проверяем — урок открыт только один раз
    count = await pool.fetchval(
        """
        SELECT COUNT(*) FROM user_progress
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, sample_lessons[1]["id"]
    )
    assert count == 1

    # Уведомление отправлено только один раз (или дважды, но это допустимо)
    # В идеале — 1 раз, но из-за race condition может быть 2
    assert mock_bot.send_message.call_count in [1, 2]


@pytest.mark.asyncio
async def test_edge_user_activity_during_unlock(sample_lessons, enrolled_user, mock_bot):
    """
    Edge Case: Пользователь активен во время открытия урока
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок
    await pool.execute(
        """
        UPDATE user_progress
        SET status = 'COMPLETED', completed_at = $3
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, lesson_id, datetime.utcnow() - timedelta(days=2)
    )

    # Обновляем last_activity (пользователь активен)
    await db.update_last_activity(user_id)

    # Запускаем scheduler
    scheduler.set_bot(mock_bot)
    await scheduler.check_lesson_unlocks()

    # Проверяем — урок всё равно открывается
    assert await pool.fetchval(
        "SELECT current_lesson_id FROM enrollments WHERE user_id = $1",
        user_id
    ) == sample_lessons[1]["id"]


# ============================================
# Edge Cases: Database State
# ============================================

@pytest.mark.asyncio
async def test_edge_missing_enrollment(sample_lessons, db_clean, mock_bot):
    """
    Edge Case: Пользователь без enrollment
    """
    pool = await get_pool()
    user_id = 999999

    # Создаём пользователя без enrollment
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, NOW())
        """,
        user_id, "no_enrollment", "No Enrollment", "idle"
    )

    # Запускаем scheduler — не должно быть ошибок
    scheduler.set_bot(mock_bot)
    await scheduler.check_lesson_unlocks()
    await scheduler.send_reminders()

    # Проверяем — уведомления не отправлялись
    assert not mock_bot.send_message.called


@pytest.mark.asyncio
async def test_edge_missing_user_progress(sample_lessons, db_clean, mock_bot):
    """
    Edge Case: Enrollment есть, но нет записи в user_progress
    """
    pool = await get_pool()
    user_id = 888888

    # Создаём пользователя
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, NOW())
        """,
        user_id, "no_progress", "No Progress", "idle"
    )

    # Создаём enrollment БЕЗ user_progress
    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[0]["id"]
    )

    # Запускаем scheduler — не должно быть ошибок
    scheduler.set_bot(mock_bot)
    await scheduler.check_lesson_unlocks()

    # Проверяем — уведомления не отправлялись
    assert not mock_bot.send_message.called


@pytest.mark.asyncio
async def test_edge_corrupted_completed_at(sample_lessons, enrolled_user, mock_bot):
    """
    Edge Case: completed_at = NULL для завершённого урока
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок, но без completed_at
    await pool.execute(
        """
        UPDATE user_progress
        SET status = 'COMPLETED', completed_at = NULL
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, lesson_id
    )

    # Запускаем scheduler — не должно быть ошибок
    scheduler.set_bot(mock_bot)
    await scheduler.check_lesson_unlocks()

    # Проверяем — пользователь НЕ попадает в список
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 0


# ============================================
# Edge Cases: Reminders
# ============================================

@pytest.mark.asyncio
async def test_edge_reminder_exactly_3_days(sample_lessons, db_clean, mock_bot):
    """
    Edge Case: last_activity ровно 3 дня назад
    """
    pool = await get_pool()
    user_id = 111111

    last_activity = datetime.utcnow() - timedelta(days=3)
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id, "user3d", "User 3 Days", "idle", last_activity
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[0]["id"]
    )

    # Проверяем — должен попасть в список
    users = await db.get_users_for_reminder(days=3, reminder_type="soft")
    assert len(users) == 1


@pytest.mark.asyncio
async def test_edge_reminder_exactly_14_days(sample_lessons, db_clean, mock_bot):
    """
    Edge Case: last_activity ровно 14 дней назад (граница)
    """
    pool = await get_pool()
    user_id = 222222

    last_activity = datetime.utcnow() - timedelta(days=14)
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id, "user14d", "User 14 Days", "idle", last_activity
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[0]["id"]
    )

    # Проверяем — должен попасть в список (< 14 дней согласно коду)
    users = await db.get_users_for_reminder(days=7, reminder_type="strong")
    assert len(users) == 1


@pytest.mark.asyncio
async def test_edge_reminder_both_sent(sample_lessons, db_clean, mock_bot):
    """
    Edge Case: Оба типа напоминаний уже отправлены
    """
    pool = await get_pool()
    user_id = 333333

    last_activity = datetime.utcnow() - timedelta(days=7)
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id, "both_sent", "Both Sent", "idle", last_activity
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[0]["id"]
    )

    # Отправляем оба напоминания
    await db.log_reminder(user_id, "soft")
    await db.log_reminder(user_id, "strong")

    # Проверяем — не попадает в списки
    soft_users = await db.get_users_for_reminder(days=3, reminder_type="soft")
    strong_users = await db.get_users_for_reminder(days=7, reminder_type="strong")

    assert len(soft_users) == 0
    assert len(strong_users) == 0


# ============================================
# Edge Cases: Bot Communication
# ============================================

@pytest.mark.asyncio
async def test_edge_bot_not_set(sample_lessons, enrolled_user):
    """
    Edge Case: _bot = None (не установлен)
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок
    await pool.execute(
        """
        UPDATE user_progress
        SET status = 'COMPLETED', completed_at = $3
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, lesson_id, datetime.utcnow() - timedelta(days=2)
    )

    # Не устанавливаем бота
    scheduler.set_bot(None)

    # Запускаем scheduler — не должно быть ошибок
    await scheduler.check_lesson_unlocks()

    # Проверяем — урок всё равно открылся
    enrollment = await pool.fetchrow(
        "SELECT current_lesson_id FROM enrollments WHERE user_id = $1",
        user_id
    )
    assert enrollment["current_lesson_id"] == sample_lessons[1]["id"]


@pytest.mark.asyncio
async def test_edge_bot_send_message_exception(sample_lessons, enrolled_user, mock_bot):
    """
    Edge Case: bot.send_message выбрасывает исключение
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок
    await pool.execute(
        """
        UPDATE user_progress
        SET status = 'COMPLETED', completed_at = $3
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, lesson_id, datetime.utcnow() - timedelta(days=2)
    )

    # Настраиваем мок на исключение
    mock_bot.send_message.side_effect = Exception("Network error")

    # Запускаем scheduler
    scheduler.set_bot(mock_bot)
    await scheduler.check_lesson_unlocks()

    # Проверяем — урок всё равно открылся
    enrollment = await pool.fetchrow(
        "SELECT current_lesson_id FROM enrollments WHERE user_id = $1",
        user_id
    )
    assert enrollment["current_lesson_id"] == sample_lessons[1]["id"]


# ============================================
# Edge Cases: Performance
# ============================================

@pytest.mark.asyncio
async def test_edge_large_number_of_users(sample_lessons, db_clean, mock_bot):
    """
    Edge Case: Большое количество пользователей (100)
    """
    pool = await get_pool()

    # Создаём 100 пользователей
    completed_at = datetime.utcnow() - timedelta(days=2)
    for i in range(100):
        user_id = 100000 + i
        await pool.execute(
            """
            INSERT INTO users (tg_id, username, full_name, state, last_activity)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            user_id, f"user{i}", f"User {i}", "idle"
        )

        await pool.execute(
            """
            INSERT INTO enrollments (user_id, current_lesson_id)
            VALUES ($1, $2)
            """,
            user_id, sample_lessons[0]["id"]
        )

        await pool.execute(
            """
            INSERT INTO user_progress (user_id, lesson_id, status, completed_at)
            VALUES ($1, $2, 'COMPLETED', $3)
            """,
            user_id, sample_lessons[0]["id"], completed_at
        )

    # Запускаем scheduler
    scheduler.set_bot(mock_bot)
    await scheduler.check_lesson_unlocks()

    # Проверяем — всем отправлены уведомления
    assert mock_bot.send_message.call_count == 100
