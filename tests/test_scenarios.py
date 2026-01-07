"""
Сценарные тесты (End-to-End симуляция)

Проверяем полный путь пользователя через весь курс с использованием временных симуляций.
"""

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.scenario]

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from bot.database import queries as db
from bot.database.connection import get_pool
from bot.services import scheduler


class CourseSimulator:
    """
    Симулятор прохождения курса.
    Позволяет "перематывать" время и проверять состояние пользователя.
    """

    def __init__(self, pool, user_id, mock_bot):
        self.pool = pool
        self.user_id = user_id
        self.mock_bot = mock_bot
        self.current_date = datetime.utcnow()

    async def advance_days(self, days: int):
        """Продвинуть время вперёд на N дней"""
        self.current_date += timedelta(days=days)

        # Обновляем completed_at для всех завершённых уроков
        # (симулируем прошедшее время)
        await self.pool.execute(
            """
            UPDATE user_progress
            SET completed_at = completed_at - INTERVAL '1 day' * $2
            WHERE user_id = $1 AND status = 'COMPLETED'
            """,
            self.user_id, days
        )

    async def complete_current_lesson(self):
        """Завершить текущий урок (симуляция сдачи ДЗ)"""
        # Получаем текущий урок
        enrollment = await self.pool.fetchrow(
            "SELECT current_lesson_id FROM enrollments WHERE user_id = $1",
            self.user_id
        )

        if not enrollment:
            raise ValueError("User not enrolled")

        current_lesson_id = enrollment["current_lesson_id"]

        # Завершаем урок
        await db.complete_lesson(self.user_id, current_lesson_id)

        # Обновляем last_activity
        await db.update_last_activity(self.user_id)

    async def run_scheduler(self):
        """Запустить scheduler (симуляция cron job)"""
        scheduler.set_bot(self.mock_bot)
        await scheduler.check_lesson_unlocks()

    async def get_current_lesson_order(self) -> int:
        """Получить номер текущего урока"""
        enrollment = await self.pool.fetchrow(
            """
            SELECT l.order_num
            FROM enrollments e
            INNER JOIN lessons l ON l.id = e.current_lesson_id
            WHERE e.user_id = $1
            """,
            self.user_id
        )
        return enrollment["order_num"] if enrollment else None

    async def get_completed_lessons_count(self) -> int:
        """Получить количество завершённых уроков"""
        count = await self.pool.fetchval(
            """
            SELECT COUNT(*) FROM user_progress
            WHERE user_id = $1 AND status = 'COMPLETED'
            """,
            self.user_id
        )
        return count or 0


# ============================================
# Scenario Tests
# ============================================

@pytest.mark.asyncio
async def test_scenario_ideal_path(sample_lessons, enrolled_user, mock_bot):
    """
    Сценарий: Идеальный путь
    - Видео → ДЗ в тот же день → +2 дня → следующее видео
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    sim = CourseSimulator(pool, user_id, mock_bot)

    # День 1: Получили урок 1, сдали ДЗ
    await sim.complete_current_lesson()
    assert await sim.get_current_lesson_order() == 1

    # День 2: Ничего не происходит (ждём +2 дня)
    await sim.advance_days(1)
    await sim.run_scheduler()
    assert await sim.get_current_lesson_order() == 1  # Всё ещё урок 1

    # День 3: Открывается урок 2
    await sim.advance_days(1)
    await sim.run_scheduler()
    assert await sim.get_current_lesson_order() == 2
    assert mock_bot.send_message.call_count == 1

    # День 3: Сдаём ДЗ урока 2
    await sim.complete_current_lesson()

    # День 5: Открывается урок 3
    await sim.advance_days(2)
    await sim.run_scheduler()
    assert await sim.get_current_lesson_order() == 3
    assert mock_bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_scenario_delay_3_days(sample_lessons, enrolled_user, mock_bot):
    """
    Сценарий: Задержка 3 дня
    - Урок получен → ДЗ через 3 дня → видео через +2 дня после ДЗ
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    sim = CourseSimulator(pool, user_id, mock_bot)

    # День 1: Получили урок 1, НЕ сдали ДЗ
    assert await sim.get_current_lesson_order() == 1

    # День 4: Сдаём ДЗ через 3 дня
    await sim.advance_days(3)
    await sim.complete_current_lesson()
    assert await sim.get_current_lesson_order() == 1

    # День 5: Ничего не происходит
    await sim.advance_days(1)
    await sim.run_scheduler()
    assert await sim.get_current_lesson_order() == 1

    # День 6: Открывается урок 2
    await sim.advance_days(1)
    await sim.run_scheduler()
    assert await sim.get_current_lesson_order() == 2
    assert mock_bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_scenario_skip_lesson_reminder(sample_lessons, enrolled_user, mock_bot):
    """
    Сценарий: Пропуск урока
    - Не сдаёт ДЗ 7 дней → получает напоминание (один раз)
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    sim = CourseSimulator(pool, user_id, mock_bot)

    # День 1: Получили урок 1, НЕ сдали ДЗ
    assert await sim.get_current_lesson_order() == 1

    # День 4: Проходит 3 дня → напоминания ещё нет (scheduler.send_reminders не запускали)
    await sim.advance_days(3)

    # Обновляем last_activity вручную (симулируем неактивность)
    last_activity = datetime.utcnow() - timedelta(days=3)
    await pool.execute(
        "UPDATE users SET last_activity = $2 WHERE tg_id = $1",
        user_id, last_activity
    )

    # Запускаем отправку напоминаний
    scheduler.set_bot(mock_bot)
    await scheduler.send_reminders()

    # Проверяем — получил мягкое напоминание
    assert mock_bot.send_message.call_count == 1
    call_args = mock_bot.send_message.call_args[0]
    assert "давно не заходил" in call_args[1]

    # День 8: Проходит 7 дней
    await sim.advance_days(4)
    last_activity = datetime.utcnow() - timedelta(days=7)
    await pool.execute(
        "UPDATE users SET last_activity = $2 WHERE tg_id = $1",
        user_id, last_activity
    )

    await scheduler.send_reminders()

    # Проверяем — получил настойчивое напоминание
    assert mock_bot.send_message.call_count == 2
    call_args = mock_bot.send_message.call_args[0]
    assert "не заходил уже неделю" in call_args[1]

    # Повторный вызов — напоминание не отправляется
    await scheduler.send_reminders()
    assert mock_bot.send_message.call_count == 2  # Всё ещё 2


@pytest.mark.asyncio
async def test_scenario_full_course(sample_lessons, enrolled_user, mock_bot):
    """
    Сценарий: Курс до конца
    - Все 18 уроков — нет 19-го урока, нет ошибок
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    sim = CourseSimulator(pool, user_id, mock_bot)

    # Проходим все 18 уроков
    for i in range(1, 19):
        # Сдаём текущий урок
        await sim.complete_current_lesson()
        assert await sim.get_completed_lessons_count() == i

        # Ждём 2 дня и запускаем scheduler
        await sim.advance_days(2)
        await sim.run_scheduler()

        if i < 18:
            # Должен открыться следующий урок
            assert await sim.get_current_lesson_order() == i + 1
            assert mock_bot.send_message.call_count == i
        else:
            # После 18-го урока ничего не открывается
            assert await sim.get_current_lesson_order() == 18
            assert mock_bot.send_message.call_count == 17  # Только 17 уведомлений (2-18)

    # Проверяем финальное состояние
    assert await sim.get_completed_lessons_count() == 18
    assert await sim.get_current_lesson_order() == 18


@pytest.mark.asyncio
async def test_scenario_fast_student(sample_lessons, enrolled_user, mock_bot):
    """
    Сценарий: Быстрый студент
    - Сдаёт ДЗ сразу после получения урока — всё равно ждёт +2 дня
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    sim = CourseSimulator(pool, user_id, mock_bot)

    # День 1: Сдали урок 1 сразу
    await sim.complete_current_lesson()

    # День 1: Пытаемся открыть урок 2 сразу — НЕ должно сработать
    await sim.run_scheduler()
    assert await sim.get_current_lesson_order() == 1

    # День 2: Всё ещё ждём
    await sim.advance_days(1)
    await sim.run_scheduler()
    assert await sim.get_current_lesson_order() == 1

    # День 3: Открывается урок 2
    await sim.advance_days(1)
    await sim.run_scheduler()
    assert await sim.get_current_lesson_order() == 2
    assert mock_bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_scenario_irregular_pattern(sample_lessons, enrolled_user, mock_bot):
    """
    Сценарий: Нерегулярное прохождение
    - Урок 1: сдал сразу → +2 дня → урок 2
    - Урок 2: сдал через 5 дней → +2 дня → урок 3
    - Урок 3: сдал через 1 день → +2 дня → урок 4
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    sim = CourseSimulator(pool, user_id, mock_bot)

    # Урок 1: сдал сразу
    await sim.complete_current_lesson()
    await sim.advance_days(2)
    await sim.run_scheduler()
    assert await sim.get_current_lesson_order() == 2

    # Урок 2: сдал через 5 дней
    await sim.advance_days(5)
    await sim.complete_current_lesson()
    await sim.advance_days(2)
    await sim.run_scheduler()
    assert await sim.get_current_lesson_order() == 3

    # Урок 3: сдал через 1 день
    await sim.advance_days(1)
    await sim.complete_current_lesson()
    await sim.advance_days(2)
    await sim.run_scheduler()
    assert await sim.get_current_lesson_order() == 4

    # Проверяем количество уведомлений (уроки 2, 3, 4)
    assert mock_bot.send_message.call_count == 3


@pytest.mark.asyncio
async def test_scenario_return_after_long_break(sample_lessons, enrolled_user, mock_bot):
    """
    Сценарий: Возвращение после долгого перерыва
    - Сдал урок 1 → долгий перерыв 20 дней → возвращается → открывается урок 2
    """
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    sim = CourseSimulator(pool, user_id, mock_bot)

    # Сдаём урок 1
    await sim.complete_current_lesson()

    # Перерыв 20 дней
    await sim.advance_days(20)

    # Возвращается — scheduler открывает урок 2
    await sim.run_scheduler()
    assert await sim.get_current_lesson_order() == 2
    assert mock_bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_scenario_multiple_students_parallel(sample_lessons, db_clean, mock_bot):
    """
    Сценарий: Несколько студентов проходят курс параллельно
    - 3 студента на разных этапах курса
    """
    pool = await get_pool()

    # Создаём 3 студентов
    students = []
    for i in range(3):
        user_id = 111111 + i
        await pool.execute(
            """
            INSERT INTO users (tg_id, username, full_name, state, last_activity)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            user_id, f"student_{i}", f"Student {i}", "idle"
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
            INSERT INTO user_progress (user_id, lesson_id, status)
            VALUES ($1, $2, 'OPEN')
            """,
            user_id, sample_lessons[0]["id"]
        )

        students.append(CourseSimulator(pool, user_id, mock_bot))

    # Студент 0: сдаёт урок 1 сразу
    await students[0].complete_current_lesson()

    # Студент 1: сдаёт урок 1 через 3 дня
    await students[1].advance_days(3)
    await students[1].complete_current_lesson()

    # Студент 2: не сдаёт урок 1

    # Через 2 дня запускаем scheduler
    await students[0].advance_days(2)
    scheduler.set_bot(mock_bot)
    await scheduler.check_lesson_unlocks()

    # Проверяем — студенту 0 открылся урок 2
    assert await students[0].get_current_lesson_order() == 2
    assert mock_bot.send_message.call_count == 1

    # Студент 1 ещё ждёт
    assert await students[1].get_current_lesson_order() == 1

    # Студент 2 всё ещё на уроке 1
    assert await students[2].get_current_lesson_order() == 1
