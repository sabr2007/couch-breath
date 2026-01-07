"""
Integration-тесты для scheduler функций

Проверяем полный цикл работы: от состояния БД до отправки сообщений.
"""

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, call

from bot.database import queries as db
from bot.database.connection import get_pool
from bot.services import scheduler


# ============================================
# Tests: check_lesson_unlocks()
# ============================================

@pytest.mark.asyncio
async def test_check_lesson_unlocks_sends_notification(sample_lessons, enrolled_user, mock_bot):
    """
    Тест: check_lesson_unlocks находит пользователя и отправляет уведомление
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
        user_id, lesson_id, completed_at
    )

    # Устанавливаем мок бота
    scheduler.set_bot(mock_bot)

    # Запускаем scheduler
    await scheduler.check_lesson_unlocks()

    # Проверяем, что бот вызвал send_message
    assert mock_bot.send_message.called
    assert mock_bot.send_message.call_count == 1

    # Проверяем аргументы вызова
    call_args = mock_bot.send_message.call_args[0]
    assert call_args[0] == user_id  # Первый аргумент — user_id
    assert "Урок 2" in call_args[1]  # Второй аргумент — текст сообщения


@pytest.mark.asyncio
async def test_check_lesson_unlocks_updates_enrollment(sample_lessons, enrolled_user, mock_bot):
    """
    Тест: check_lesson_unlocks обновляет enrollment и user_progress
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
        user_id, lesson_id, completed_at
    )

    # Устанавливаем мок бота
    scheduler.set_bot(mock_bot)

    # Запускаем scheduler
    await scheduler.check_lesson_unlocks()

    # Проверяем enrollment
    enrollment = await pool.fetchrow(
        "SELECT current_lesson_id FROM enrollments WHERE user_id = $1",
        user_id
    )
    assert enrollment["current_lesson_id"] == sample_lessons[1]["id"]

    # Проверяем user_progress
    progress = await pool.fetchrow(
        "SELECT status FROM user_progress WHERE user_id = $1 AND lesson_id = $2",
        user_id, sample_lessons[1]["id"]
    )
    assert progress["status"] == "OPEN"


@pytest.mark.asyncio
async def test_check_lesson_unlocks_no_users(sample_lessons, enrolled_user, mock_bot):
    """
    Тест: нет пользователей для открытия уроков → ничего не отправляется
    """
    # Урок не завершён — пользователь не попадёт в список
    scheduler.set_bot(mock_bot)
    await scheduler.check_lesson_unlocks()

    # Проверяем, что send_message не вызывался
    assert not mock_bot.send_message.called


@pytest.mark.asyncio
async def test_check_lesson_unlocks_multiple_users(sample_lessons, db_pool, mock_bot):
    """
    Тест: несколько пользователей готовы к открытию → всем отправляется уведомление
    """
    pool = await get_pool()

    # Создаём 3 пользователей
    user_ids = [111111, 222222, 333333]
    completed_at = datetime.utcnow() - timedelta(days=2)

    for user_id in user_ids:
        await pool.execute(
            """
            INSERT INTO users (tg_id, username, full_name, state, last_activity)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            user_id, f"user_{user_id}", f"User {user_id}", "idle"
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

    # Проверяем — 3 уведомления отправлено
    assert mock_bot.send_message.call_count == 3


@pytest.mark.asyncio
async def test_check_lesson_unlocks_idempotent(sample_lessons, enrolled_user, mock_bot):
    """
    Тест: повторный вызов check_lesson_unlocks не создаёт дубликатов
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
        user_id, lesson_id, completed_at
    )

    # Устанавливаем мок бота
    scheduler.set_bot(mock_bot)

    # Запускаем scheduler ДВАЖДЫ
    await scheduler.check_lesson_unlocks()
    await scheduler.check_lesson_unlocks()

    # Проверяем — send_message вызван только ОДИН РАЗ
    assert mock_bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_check_lesson_unlocks_bot_error_continues(sample_lessons, db_pool, mock_bot):
    """
    Тест: ошибка отправки сообщения не останавливает обработку других пользователей
    """
    pool = await get_pool()

    # Создаём 2 пользователей
    user_ids = [111111, 222222]
    completed_at = datetime.utcnow() - timedelta(days=2)

    for user_id in user_ids:
        await pool.execute(
            """
            INSERT INTO users (tg_id, username, full_name, state, last_activity)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            user_id, f"user_{user_id}", f"User {user_id}", "idle"
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

    # Настраиваем мок: первый вызов с ошибкой, второй успешный
    mock_bot.send_message.side_effect = [Exception("Network error"), AsyncMock()]

    # Запускаем scheduler
    scheduler.set_bot(mock_bot)
    await scheduler.check_lesson_unlocks()

    # Проверяем — send_message вызван 2 раза (не остановился на ошибке)
    assert mock_bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_check_lesson_unlocks_last_lesson_no_notification(sample_lessons, db_pool, mock_bot):
    """
    Тест: последний урок (18) завершён → уведомление НЕ отправляется
    """
    pool = await get_pool()
    user_id = 888888

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
        user_id, sample_lessons[17]["id"]
    )

    completed_at = datetime.utcnow() - timedelta(days=2)
    await pool.execute(
        """
        INSERT INTO user_progress (user_id, lesson_id, status, completed_at)
        VALUES ($1, $2, 'COMPLETED', $3)
        """,
        user_id, sample_lessons[17]["id"], completed_at
    )

    # Запускаем scheduler
    scheduler.set_bot(mock_bot)
    await scheduler.check_lesson_unlocks()

    # Проверяем — send_message НЕ вызван
    assert not mock_bot.send_message.called


# ============================================
# Tests: send_reminders()
# ============================================

@pytest.mark.asyncio
async def test_send_reminders_soft_3_days(sample_lessons, db_pool, mock_bot):
    """
    Тест: пользователь неактивен 3 дня → получает мягкое напоминание
    """
    pool = await get_pool()
    user_id = 111111

    last_activity = datetime.utcnow() - timedelta(days=3)
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id, "inactive", "Inactive User", "idle", last_activity
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[0]["id"]
    )

    # Запускаем scheduler
    scheduler.set_bot(mock_bot)
    await scheduler.send_reminders()

    # Проверяем — отправлено 1 сообщение
    assert mock_bot.send_message.call_count == 1

    # Проверяем текст сообщения
    call_args = mock_bot.send_message.call_args[0]
    assert call_args[0] == user_id
    assert "давно не заходил" in call_args[1]


@pytest.mark.asyncio
async def test_send_reminders_strong_7_days(sample_lessons, db_pool, mock_bot):
    """
    Тест: пользователь неактивен 7 дней → получает настойчивое напоминание.
    Примечание: пользователь с 7 днями попадает и в soft (3 дня), и в strong.
    Чтобы тестировать только strong, сначала логируем soft.
    """
    pool = await get_pool()
    user_id = 222222

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

    # Логируем soft напоминание, чтобы тестировать только strong
    await db.log_reminder(user_id, "soft")

    # Запускаем scheduler
    scheduler.set_bot(mock_bot)
    await scheduler.send_reminders()

    # Проверяем — отправлено 1 сообщение (только strong)
    assert mock_bot.send_message.call_count == 1

    # Проверяем текст сообщения
    call_args = mock_bot.send_message.call_args[0]
    assert call_args[0] == user_id
    assert "не заходил уже неделю" in call_args[1]


@pytest.mark.asyncio
async def test_send_reminders_both_types(sample_lessons, db_pool, mock_bot):
    """
    Тест: два пользователя — один на 3 дня (soft), другой на 7 дней (strong).
    Примечание: пользователь с 7 днями попадает и в soft, и в strong.
    Логируем soft для user_id_2, чтобы он получил только strong.
    """
    pool = await get_pool()

    # Пользователь 1: 3 дня → получит soft
    user_id_1 = 111111
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id_1, "user1", "User 1", "idle", datetime.utcnow() - timedelta(days=3)
    )
    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id_1, sample_lessons[0]["id"]
    )

    # Пользователь 2: 7 дней → получит strong (после того как soft уже был)
    user_id_2 = 222222
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id_2, "user2", "User 2", "idle", datetime.utcnow() - timedelta(days=7)
    )
    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id_2, sample_lessons[0]["id"]
    )
    # Логируем soft для user_id_2, чтобы он получил только strong
    await db.log_reminder(user_id_2, "soft")

    # Запускаем scheduler
    scheduler.set_bot(mock_bot)
    await scheduler.send_reminders()

    # Проверяем — отправлено 2 сообщения (soft для user1, strong для user2)
    assert mock_bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_send_reminders_logs_reminder(sample_lessons, db_pool, mock_bot):
    """
    Тест: после отправки напоминания создаётся запись в reminders
    """
    pool = await get_pool()
    user_id = 111111

    last_activity = datetime.utcnow() - timedelta(days=3)
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id, "inactive", "Inactive User", "idle", last_activity
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[0]["id"]
    )

    # Запускаем scheduler
    scheduler.set_bot(mock_bot)
    await scheduler.send_reminders()

    # Проверяем запись в reminders
    reminder = await pool.fetchrow(
        "SELECT * FROM reminders WHERE user_id = $1 AND reminder_type = $2",
        user_id, "soft"
    )
    assert reminder is not None


@pytest.mark.asyncio
async def test_send_reminders_idempotent(sample_lessons, db_pool, mock_bot):
    """
    Тест: повторный вызов send_reminders не отправляет дубликатов
    """
    pool = await get_pool()
    user_id = 111111

    last_activity = datetime.utcnow() - timedelta(days=3)
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id, "inactive", "Inactive User", "idle", last_activity
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[0]["id"]
    )

    # Запускаем scheduler ДВАЖДЫ
    scheduler.set_bot(mock_bot)
    await scheduler.send_reminders()
    await scheduler.send_reminders()

    # Проверяем — send_message вызван только ОДИН РАЗ
    assert mock_bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_send_reminders_no_spam_after_14_days(sample_lessons, db_pool, mock_bot):
    """
    Тест: пользователь неактивен 15 дней → НЕ получает напоминание
    """
    pool = await get_pool()
    user_id = 333333

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

    # Запускаем scheduler
    scheduler.set_bot(mock_bot)
    await scheduler.send_reminders()

    # Проверяем — send_message НЕ вызван
    assert not mock_bot.send_message.called


@pytest.mark.asyncio
async def test_send_reminders_bot_error_continues(sample_lessons, db_pool, mock_bot):
    """
    Тест: ошибка отправки сообщения не останавливает обработку
    """
    pool = await get_pool()

    # Создаём 2 пользователей
    for i, user_id in enumerate([111111, 222222]):
        await pool.execute(
            """
            INSERT INTO users (tg_id, username, full_name, state, last_activity)
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id, f"user{i}", f"User {i}", "idle", datetime.utcnow() - timedelta(days=3)
        )
        await pool.execute(
            """
            INSERT INTO enrollments (user_id, current_lesson_id)
            VALUES ($1, $2)
            """,
            user_id, sample_lessons[0]["id"]
        )

    # Настраиваем мок: первый вызов с ошибкой, второй успешный
    mock_bot.send_message.side_effect = [Exception("Network error"), AsyncMock()]

    # Запускаем scheduler
    scheduler.set_bot(mock_bot)
    await scheduler.send_reminders()

    # Проверяем — send_message вызван 2 раза
    assert mock_bot.send_message.call_count == 2
