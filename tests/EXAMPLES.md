# Примеры использования тестов

Практические примеры написания и запуска тестов для scheduler-функций.

## Пример 1: Простой Unit-тест

**Цель:** Проверить, что пользователь попадает в список для открытия урока через 2 дня.

```python
@pytest.mark.asyncio
async def test_user_ready_after_2_days(sample_lessons, enrolled_user):
    """Пользователь завершил урок 2 дня назад → попадает в список"""
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

    # Проверяем
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 1
    assert users[0]["user_id"] == user_id
```

**Запуск:**
```bash
pytest tests/test_queries.py::test_user_ready_after_2_days -v
```

---

## Пример 2: Integration-тест с моком бота

**Цель:** Проверить, что scheduler отправляет уведомление через бота.

```python
@pytest.mark.asyncio
async def test_scheduler_sends_notification(sample_lessons, enrolled_user, mock_bot):
    """Scheduler находит пользователя и отправляет уведомление"""
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

    # Проверяем вызовы
    assert mock_bot.send_message.called
    assert mock_bot.send_message.call_count == 1

    # Проверяем аргументы
    call_args = mock_bot.send_message.call_args[0]
    assert call_args[0] == user_id  # Первый аргумент — user_id
    assert "Урок 2" in call_args[1]  # Второй аргумент — текст сообщения
```

**Запуск:**
```bash
pytest tests/test_scheduler.py::test_scheduler_sends_notification -v
```

---

## Пример 3: Сценарный тест с CourseSimulator

**Цель:** Симулировать полное прохождение курса.

```python
@pytest.mark.asyncio
async def test_full_course_completion(sample_lessons, enrolled_user, mock_bot):
    """Пользователь проходит все 18 уроков"""
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    sim = CourseSimulator(pool, user_id, mock_bot)

    # Проходим все 18 уроков
    for i in range(1, 19):
        # Сдаём текущий урок
        await sim.complete_current_lesson()

        # Ждём 2 дня
        await sim.advance_days(2)

        # Запускаем scheduler
        await sim.run_scheduler()

        if i < 18:
            # Должен открыться следующий урок
            assert await sim.get_current_lesson_order() == i + 1
        else:
            # После 18-го урока ничего не открывается
            assert await sim.get_current_lesson_order() == 18

    # Финальные проверки
    assert await sim.get_completed_lessons_count() == 18
```

**Запуск:**
```bash
pytest tests/test_scenarios.py::test_full_course_completion -v
```

---

## Пример 4: Edge Case тест

**Цель:** Проверить поведение на временной границе (ровно 24 часа).

```python
@pytest.mark.asyncio
async def test_exactly_24_hours_boundary(sample_lessons, enrolled_user):
    """Урок завершён ровно 24 часа назад → попадает в список"""
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

    # Проверяем
    users = await db.get_users_ready_for_next_lesson()
    assert len(users) == 1
```

**Запуск:**
```bash
pytest tests/test_edge_cases.py::test_exactly_24_hours_boundary -v
```

---

## Пример 5: Тест идемпотентности

**Цель:** Убедиться, что повторный вызов не создаёт дубликатов.

```python
@pytest.mark.asyncio
async def test_unlock_lesson_idempotent(sample_lessons, enrolled_user, mock_bot):
    """Повторный вызов unlock_next_lesson не создаёт дубликатов"""
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

    # Запускаем scheduler ДВАЖДЫ
    scheduler.set_bot(mock_bot)
    await scheduler.check_lesson_unlocks()
    await scheduler.check_lesson_unlocks()

    # Проверяем — урок открыт только ОДИН РАЗ
    count = await pool.fetchval(
        """
        SELECT COUNT(*) FROM user_progress
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, sample_lessons[1]["id"]
    )
    assert count == 1

    # Уведомление отправлено только ОДИН РАЗ
    assert mock_bot.send_message.call_count == 1
```

**Запуск:**
```bash
pytest tests/test_scheduler.py::test_unlock_lesson_idempotent -v
```

---

## Пример 6: Создание пользователя с прогрессом (фабрика)

**Цель:** Использовать фабрику для создания пользователя на определённом уроке.

```python
@pytest.mark.asyncio
async def test_user_on_lesson_5(sample_lessons, create_user_with_progress, mock_bot):
    """Тест пользователя на уроке 5"""

    # Создаём пользователя на уроке 5 с завершёнными уроками 1-4
    user_data = await create_user_with_progress(
        tg_id=555555,
        current_lesson_order=5,
        lessons_completed=[1, 2, 3, 4],
        last_activity_days_ago=0
    )

    # Проверяем
    pool = await get_pool()
    enrollment = await pool.fetchrow(
        "SELECT current_lesson_id FROM enrollments WHERE user_id = $1",
        user_data["tg_id"]
    )

    lesson = await pool.fetchrow(
        "SELECT order_num FROM lessons WHERE id = $1",
        enrollment["current_lesson_id"]
    )

    assert lesson["order_num"] == 5

    # Проверяем завершённые уроки
    completed = await pool.fetchval(
        "SELECT COUNT(*) FROM user_progress WHERE user_id = $1 AND status = 'COMPLETED'",
        user_data["tg_id"]
    )
    assert completed == 4
```

---

## Пример 7: Тест напоминаний

**Цель:** Проверить систему напоминаний для неактивных пользователей.

```python
@pytest.mark.asyncio
async def test_reminder_system(sample_lessons, db_clean, mock_bot):
    """Система напоминаний: 3 дня → мягкое, 7 дней → настойчивое"""
    pool = await get_pool()

    # Создаём пользователя неактивного 3 дня
    user_id = 111111
    await pool.execute(
        """
        INSERT INTO users (tg_id, username, full_name, state, last_activity)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id, "inactive_user", "Inactive User", "idle",
        datetime.utcnow() - timedelta(days=3)
    )

    await pool.execute(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, $2)
        """,
        user_id, sample_lessons[0]["id"]
    )

    # Запускаем отправку напоминаний
    scheduler.set_bot(mock_bot)
    await scheduler.send_reminders()

    # Проверяем — получил мягкое напоминание
    assert mock_bot.send_message.call_count == 1
    call_args = mock_bot.send_message.call_args[0]
    assert "давно не заходил" in call_args[1]

    # Проверяем запись в БД
    reminder = await pool.fetchrow(
        "SELECT * FROM reminders WHERE user_id = $1 AND reminder_type = 'soft'",
        user_id
    )
    assert reminder is not None

    # Повторный вызов — напоминание не отправляется
    await scheduler.send_reminders()
    assert mock_bot.send_message.call_count == 1  # Всё ещё 1
```

**Запуск:**
```bash
pytest tests/test_scheduler.py::test_reminder_system -v
```

---

## Пример 8: Отладка теста

**Цель:** Запустить тест с отладчиком и проверить состояние БД.

```python
@pytest.mark.asyncio
async def test_with_debugging(sample_lessons, enrolled_user, mock_bot):
    """Тест с точками останова"""
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]

    # Завершаем урок
    await pool.execute(
        """
        UPDATE user_progress
        SET status = 'COMPLETED', completed_at = $3
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, enrolled_user["current_lesson_id"],
        datetime.utcnow() - timedelta(days=2)
    )

    # Точка останова для отладки
    import pdb; pdb.set_trace()

    # Проверяем состояние БД
    users = await db.get_users_ready_for_next_lesson()
    print(f"Найдено пользователей: {len(users)}")

    # Запускаем scheduler
    scheduler.set_bot(mock_bot)
    await scheduler.check_lesson_unlocks()

    # Проверяем вызовы
    print(f"Вызовов send_message: {mock_bot.send_message.call_count}")
```

**Запуск:**
```bash
pytest tests/test_queries.py::test_with_debugging --pdb
```

При запуске тест остановится на `pdb.set_trace()` и откроется интерактивная отладка.

---

## Пример 9: Параметризованный тест

**Цель:** Запустить один тест с разными параметрами.

```python
@pytest.mark.asyncio
@pytest.mark.parametrize("days_ago,should_unlock", [
    (0, False),      # 0 дней назад → НЕ открывается
    (1, True),       # 1 день назад → открывается
    (2, True),       # 2 дня назад → открывается
    (5, True),       # 5 дней назад → открывается
])
async def test_unlock_after_n_days(sample_lessons, enrolled_user, days_ago, should_unlock):
    """Проверка открытия урока через N дней"""
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]
    lesson_id = enrolled_user["current_lesson_id"]

    # Завершаем урок N дней назад
    completed_at = datetime.utcnow() - timedelta(days=days_ago)
    await pool.execute(
        """
        UPDATE user_progress
        SET status = 'COMPLETED', completed_at = $3
        WHERE user_id = $1 AND lesson_id = $2
        """,
        user_id, lesson_id, completed_at
    )

    # Проверяем
    users = await db.get_users_ready_for_next_lesson()

    if should_unlock:
        assert len(users) == 1
    else:
        assert len(users) == 0
```

**Запуск:**
```bash
pytest tests/test_queries.py::test_unlock_after_n_days -v
```

Запустится 4 теста с разными параметрами.

---

## Пример 10: Проверка производительности

**Цель:** Проверить, что scheduler справляется с большим количеством пользователей.

```python
@pytest.mark.asyncio
@pytest.mark.slow
async def test_performance_100_users(sample_lessons, db_clean, mock_bot):
    """Scheduler обрабатывает 100 пользователей"""
    import time

    pool = await get_pool()
    completed_at = datetime.utcnow() - timedelta(days=2)

    # Создаём 100 пользователей
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

    # Запускаем scheduler и измеряем время
    scheduler.set_bot(mock_bot)
    start = time.time()
    await scheduler.check_lesson_unlocks()
    duration = time.time() - start

    # Проверки
    assert mock_bot.send_message.call_count == 100
    assert duration < 10  # Должно выполниться меньше чем за 10 секунд

    print(f"Обработано 100 пользователей за {duration:.2f}с")
```

**Запуск:**
```bash
# Пропустить медленные тесты
pytest -m "not slow"

# Запустить только медленные тесты
pytest -m slow -v
```

---

## Полезные команды

```bash
# Запуск всех примеров
pytest tests/ -v

# Запуск с фильтром по имени
pytest -k "ready_after" -v

# Запуск с подробным выводом
pytest -vv -s

# Запуск с покрытием
pytest --cov=bot --cov-report=term-missing

# Запуск с профилированием
pytest --durations=10

# Запуск параллельно (требует pytest-xdist)
pytest -n auto
```

---

## Шаблон для нового теста

```python
import pytest
from datetime import datetime, timedelta

from bot.database import queries as db
from bot.database.connection import get_pool
from bot.services import scheduler


@pytest.mark.asyncio
async def test_my_new_feature(sample_lessons, enrolled_user, mock_bot):
    """Описание теста"""

    # Подготовка (Arrange)
    pool = await get_pool()
    user_id = enrolled_user["user"]["tg_id"]

    # Действие (Act)
    # ... ваш код ...

    # Проверка (Assert)
    # assert expected == actual
```

---

**Дополнительные примеры смотрите в:**
- `tests/test_queries.py`
- `tests/test_scheduler.py`
- `tests/test_scenarios.py`
- `tests/test_edge_cases.py`
