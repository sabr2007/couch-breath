# Тестирование Scheduler

Комплексная система тестирования для scheduler-функций бота "Дыхание Тренера".

## Структура тестов

```
tests/
├── conftest.py          # Фикстуры и конфигурация
├── test_queries.py      # Unit-тесты SQL-запросов
├── test_scheduler.py    # Integration-тесты scheduler
├── test_scenarios.py    # Сценарные тесты (E2E)
├── test_edge_cases.py   # Граничные условия
└── README.md           # Эта документация
```

## Установка зависимостей

```bash
# Установить тестовые зависимости
pip install -r requirements-test.txt
```

## Настройка тестовой БД

### Вариант 1: PostgreSQL (рекомендуется)

1. Создайте тестовую БД:
```bash
createdb couch_breath_test
```

2. Установите переменную окружения:
```bash
export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/couch_breath_test"
```

3. Примените миграции к тестовой БД:
```bash
python -c "
import asyncio
import os
os.environ['DATABASE_URL'] = os.getenv('TEST_DATABASE_URL')
from bot.database.migrations import run_migrations
asyncio.run(run_migrations())
"
```

### Вариант 2: SQLite (для локальной разработки)

SQLite можно использовать для быстрых тестов без установки PostgreSQL, но некоторые тесты могут работать некорректно из-за различий в SQL-диалектах.

## Запуск тестов

### Запустить все тесты

```bash
pytest
```

### Запустить конкретный файл

```bash
pytest tests/test_queries.py
```

### Запустить конкретный тест

```bash
pytest tests/test_queries.py::test_get_users_ready_for_next_lesson_basic
```

### Запустить тесты по категориям

```bash
# Только юнит-тесты (быстрые)
pytest -m unit

# Только integration-тесты
pytest -m integration

# Только сценарные тесты
pytest -m scenario

# Только граничные условия
pytest -m edge
```

### Запуск с покрытием кода

```bash
pytest --cov=bot --cov-report=html --cov-report=term-missing
```

HTML-отчёт будет доступен в `htmlcov/index.html`

### Запуск с подробным выводом

```bash
pytest -vv
```

### Запуск с выводом print-сообщений

```bash
pytest -s
```

## Описание тестовых модулей

### 1. `test_queries.py` — Unit-тесты SQL-запросов

**Цель:** Проверить корректность SQL-запросов без зависимостей от scheduler.

**Что тестируется:**
- `get_users_ready_for_next_lesson()` — корректность условия `completed_at::date + 2 <= CURRENT_DATE`
- `unlock_next_lesson()` — корректное обновление `enrollments` и `user_progress`
- `get_users_for_reminder()` — правильность фильтрации по дням и типу напоминания
- `log_reminder()` — создание записей в таблице `reminders`
- `update_last_activity()` — очистка напоминаний

**Примеры тестов:**
- Урок завершён 2 дня назад → попадает в список
- Урок завершён менее 1 дня назад → НЕ попадает в список
- Повторный вызов `unlock_next_lesson` не создаёт дубликатов
- Напоминание уже отправлено → НЕ попадает в список

**Запуск:**
```bash
pytest tests/test_queries.py -v
```

---

### 2. `test_scheduler.py` — Integration-тесты scheduler

**Цель:** Проверить полный цикл: от состояния БД до отправки уведомлений.

**Что тестируется:**
- `check_lesson_unlocks()` — находит правильных пользователей и отправляет сообщения
- `send_reminders()` — не отправляет повторно, учитывает флаг в таблице `reminders`
- Обработка ошибок при отправке сообщений
- Идемпотентность scheduler-функций

**Примеры тестов:**
- Scheduler находит пользователя и отправляет уведомление
- Повторный вызов не создаёт дубликатов
- Ошибка отправки не останавливает обработку других пользователей
- После 18-го урока уведомление НЕ отправляется

**Запуск:**
```bash
pytest tests/test_scheduler.py -v
```

---

### 3. `test_scenarios.py` — Сценарные тесты (E2E)

**Цель:** Проверить полный путь пользователя через весь курс.

**Сценарии:**

| Сценарий | Описание |
|----------|----------|
| `test_scenario_ideal_path` | Видео → ДЗ в тот же день → +2 дня → следующее видео |
| `test_scenario_delay_3_days` | ДЗ через 3 дня → видео через +2 дня |
| `test_scenario_skip_lesson_reminder` | Не сдаёт ДЗ 7 дней → получает напоминание (один раз) |
| `test_scenario_full_course` | Все 18 уроков — нет 19-го урока, нет ошибок |
| `test_scenario_fast_student` | Сдаёт ДЗ сразу — всё равно ждёт +2 дня |
| `test_scenario_irregular_pattern` | Нерегулярное прохождение курса |
| `test_scenario_return_after_long_break` | Возвращение после долгого перерыва |
| `test_scenario_multiple_students_parallel` | Несколько студентов на разных этапах |

**Как работает:**
- Используется `CourseSimulator` для симуляции прохождения курса
- Время "перематывается" методом `advance_days()`
- После каждого дня вызывается `run_scheduler()`
- Проверяется состояние пользователя в БД

**Запуск:**
```bash
pytest tests/test_scenarios.py -v
```

---

### 4. `test_edge_cases.py` — Граничные условия

**Цель:** Найти edge-case ошибки.

**Категории тестов:**

#### Временные границы
- Урок завершён ровно 24 часа назад
- Урок завершён 23:59 назад (меньше 1 дня)
- Урок завершён 24:01 назад

#### Границы уроков
- Переход 1 → 2
- Переход 17 → 18 (предпоследний → последний)
- Попытка открыть урок 19 (не существует)

#### Конкурентные операции
- Два scheduler запуска одновременно (race condition)
- Пользователь активен во время открытия урока

#### Состояние БД
- Пользователь без enrollment
- Enrollment без user_progress
- `completed_at = NULL` для завершённого урока

#### Напоминания
- `last_activity` ровно 3 дня назад
- `last_activity` ровно 14 дней назад (граница)
- Оба типа напоминаний уже отправлены

#### Коммуникация с ботом
- `_bot = None` (не установлен)
- `bot.send_message()` выбрасывает исключение

#### Производительность
- Большое количество пользователей (100)

**Запуск:**
```bash
pytest tests/test_edge_cases.py -v
```

---

## Ключевые фикстуры

### `db_clean`
Очищает БД перед каждым тестом (удаляет данные, но сохраняет схему).

### `sample_lessons`
Создаёт 18 тестовых уроков.

### `sample_user`
Создаёт одного тестового пользователя.

### `enrolled_user`
Создаёт зачисленного пользователя на первом уроке.

### `completed_lesson_user`
Фабрика для создания пользователя с завершённым уроком N дней назад.

### `mock_bot`
Мок Telegram бота для проверки вызовов `send_message()`.

### `create_user_with_progress`
Фабрика для создания пользователя с произвольным прогрессом.

---

## Лучшие практики

### 1. Изоляция тестов
Каждый тест должен быть независимым. Используйте фикстуру `db_clean` для очистки БД.

### 2. Мокирование времени
Не ждите реального времени — используйте фикстуру `mock_time` или `freezegun`.

### 3. Мокирование Telegram API
Используйте `mock_bot` для проверки вызовов `send_message()` без реальной отправки.

### 4. Проверка состояния БД
После каждого действия убеждайтесь, что данные в БД корректны.

### 5. Идемпотентность
Проверяйте, что повторный вызов функции не создаёт дубликатов.

---

## Отладка тестов

### Запуск с отладчиком

```bash
pytest --pdb
```

При ошибке тест остановится и откроется интерактивная отладка.

### Просмотр SQL-запросов

Установите уровень логирования:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Проверка состояния БД

В тесте можно напрямую выполнить SQL:
```python
pool = await get_pool()
result = await pool.fetch("SELECT * FROM users")
print(result)
```

---

## CI/CD Integration

### GitHub Actions

Пример `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: couch_breath_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt

    - name: Run migrations
      env:
        TEST_DATABASE_URL: postgresql://postgres:postgres@localhost:5432/couch_breath_test
      run: |
        python -c "..."

    - name: Run tests
      env:
        TEST_DATABASE_URL: postgresql://postgres:postgres@localhost:5432/couch_breath_test
      run: pytest --cov=bot --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## Метрики и цели покрытия

**Целевые метрики:**
- **Покрытие кода:** ≥ 80% для `bot/services/scheduler.py`
- **Покрытие кода:** ≥ 90% для `bot/database/queries.py`
- **Время выполнения:** < 30 секунд для всех тестов

**Проверка покрытия:**
```bash
pytest --cov=bot/services/scheduler.py --cov=bot/database/queries.py --cov-report=term-missing
```

---

## FAQ

### Q: Тесты падают с ошибкой "database does not exist"
**A:** Убедитесь, что создали тестовую БД и установили переменную `TEST_DATABASE_URL`.

### Q: Тесты очень медленные
**A:** Используйте фильтры:
```bash
pytest -m "not slow"
```

### Q: Как тестировать конкретный сценарий?
**A:** Используйте `CourseSimulator` в `test_scenarios.py` как пример.

### Q: Можно ли использовать SQLite вместо PostgreSQL?
**A:** Да, но некоторые тесты могут работать некорректно из-за различий в SQL (например, `INTERVAL`).

---

## Поддержка

При возникновении проблем:
1. Проверьте логи: `pytest -v --log-cli-level=DEBUG`
2. Проверьте состояние БД вручную
3. Убедитесь, что миграции применены

---

## Changelog

**v1.0.0** (2026-01-07)
- Создана комплексная система тестирования
- Добавлены unit, integration, scenario и edge-case тесты
- Покрытие: 4 модуля, 60+ тестов
