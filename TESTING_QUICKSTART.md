# Быстрый старт: Тестирование Scheduler

Краткое руководство по запуску тестов для scheduler-функций бота "Дыхание Тренера".

## Шаг 1: Установка зависимостей

```bash
pip install -r requirements-test.txt
```

## Шаг 2: Настройка тестовой БД

### PostgreSQL (рекомендуется)

```bash
# Создать БД
createdb couch_breath_test

# Установить переменную окружения
export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/couch_breath_test"

# Инициализировать БД (применить миграции)
python scripts/init_test_db.py
```

### SQLite (альтернатива)

```bash
export TEST_DATABASE_URL="sqlite:///test.db"
```

> **Примечание:** SQLite не рекомендуется для полноценного тестирования из-за различий в SQL-диалектах.

## Шаг 3: Запуск тестов

### Все тесты

```bash
pytest
```

### По категориям

```bash
# Unit-тесты (быстрые)
pytest tests/test_queries.py

# Integration-тесты
pytest tests/test_scheduler.py

# Сценарные тесты
pytest tests/test_scenarios.py

# Граничные условия
pytest tests/test_edge_cases.py
```

### С покрытием кода

```bash
pytest --cov=bot --cov-report=html
# Открыть htmlcov/index.html в браузере
```

## Шаг 4: Использование скрипта запуска (опционально)

```bash
# Сделать скрипт исполняемым (Linux/Mac)
chmod +x run_tests.sh

# Запустить все тесты
./run_tests.sh

# Запустить конкретную категорию
./run_tests.sh unit
./run_tests.sh integration
./run_tests.sh scenario
./run_tests.sh edge
./run_tests.sh coverage
```

## Структура тестов

```
tests/
├── conftest.py          # Фикстуры (fixtures)
├── test_queries.py      # Unit-тесты SQL-запросов
├── test_scheduler.py    # Integration-тесты scheduler
├── test_scenarios.py    # Сценарные E2E тесты
└── test_edge_cases.py   # Граничные условия
```

## Что тестируется?

### ✅ Unit-тесты (`test_queries.py`)
- Корректность SQL-запросов
- Условия открытия уроков (completed_at + 2 дня)
- Фильтрация напоминаний
- Идемпотентность операций

### ✅ Integration-тесты (`test_scheduler.py`)
- Отправка уведомлений через бота
- Обновление БД при открытии уроков
- Обработка ошибок
- Работа с несколькими пользователями

### ✅ Сценарные тесты (`test_scenarios.py`)
- Идеальный путь: ДЗ → +2 дня → следующий урок
- Задержка: ДЗ через 3 дня → +2 дня → урок
- Напоминания: 3 дня и 7 дней неактивности
- Полный курс: 18 уроков без ошибок
- Нерегулярное прохождение

### ✅ Edge Cases (`test_edge_cases.py`)
- Временные границы (24:00, 23:59)
- Переходы между уроками (1→2, 17→18, 18→∅)
- Конкурентные операции (race conditions)
- Повреждённые данные в БД
- Ошибки коммуникации с ботом

## Отладка

### Запуск с подробным выводом

```bash
pytest -vv
```

### Запуск с отладчиком

```bash
pytest --pdb
```

При ошибке тест остановится и откроется интерактивная отладка.

### Просмотр SQL-запросов

```bash
pytest -v --log-cli-level=DEBUG
```

### Запуск конкретного теста

```bash
pytest tests/test_queries.py::test_get_users_ready_for_next_lesson_basic -v
```

## Полезные команды

```bash
# Только быстрые тесты (исключая медленные)
pytest -m "not slow"

# Только unit-тесты
pytest -m unit

# Только integration-тесты
pytest -m integration

# Остановиться на первой ошибке
pytest -x

# Запустить последние упавшие тесты
pytest --lf

# Параллельный запуск (требует pytest-xdist)
pytest -n auto
```

## Проблемы и решения

### Ошибка: "database does not exist"

```bash
# Создайте БД и примените миграции
createdb couch_breath_test
python scripts/init_test_db.py
```

### Ошибка: "TEST_DATABASE_URL not set"

```bash
export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/couch_breath_test"
```

### Тесты очень медленные

```bash
# Запустите только быстрые тесты
pytest -m "not slow"
```

## CI/CD Integration

Тесты автоматически запускаются в CI/CD pipeline при каждом push и pull request.

Смотрите `.github/workflows/test.yml` для настройки.

## Дополнительная документация

Полная документация доступна в `tests/README.md`.

---

**Вопросы?** Проверьте `tests/README.md` или логи тестов с флагом `-vv`.
