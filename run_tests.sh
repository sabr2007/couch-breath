#!/bin/bash

# Скрипт для запуска тестов
# Использование: ./run_tests.sh [options]

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Тестирование Scheduler ===${NC}\n"

# Проверка установленных зависимостей
echo -e "${YELLOW}Проверка зависимостей...${NC}"
if ! python -c "import pytest" 2>/dev/null; then
    echo -e "${RED}Ошибка: pytest не установлен${NC}"
    echo "Установите зависимости: pip install -r requirements-test.txt"
    exit 1
fi

# Проверка переменной TEST_DATABASE_URL
if [ -z "$TEST_DATABASE_URL" ]; then
    echo -e "${YELLOW}WARNING: TEST_DATABASE_URL не установлена${NC}"
    echo "Используется значение по умолчанию: postgresql://postgres:postgres@localhost:5432/couch_breath_test"
    export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/couch_breath_test"
fi

echo -e "${GREEN}DATABASE: $TEST_DATABASE_URL${NC}\n"

# Парсинг аргументов
case "${1:-all}" in
    unit)
        echo -e "${YELLOW}Запуск unit-тестов...${NC}"
        pytest tests/test_queries.py -v
        ;;
    integration)
        echo -e "${YELLOW}Запуск integration-тестов...${NC}"
        pytest tests/test_scheduler.py -v
        ;;
    scenario)
        echo -e "${YELLOW}Запуск сценарных тестов...${NC}"
        pytest tests/test_scenarios.py -v
        ;;
    edge)
        echo -e "${YELLOW}Запуск тестов граничных условий...${NC}"
        pytest tests/test_edge_cases.py -v
        ;;
    coverage)
        echo -e "${YELLOW}Запуск с покрытием кода...${NC}"
        pytest --cov=bot/services/scheduler.py --cov=bot/database/queries.py \
               --cov-report=html --cov-report=term-missing
        echo -e "\n${GREEN}HTML-отчёт доступен в: htmlcov/index.html${NC}"
        ;;
    fast)
        echo -e "${YELLOW}Запуск быстрых тестов...${NC}"
        pytest -m "not slow" -v
        ;;
    all)
        echo -e "${YELLOW}Запуск всех тестов...${NC}"
        pytest -v
        ;;
    *)
        echo "Использование: ./run_tests.sh [unit|integration|scenario|edge|coverage|fast|all]"
        echo ""
        echo "Опции:"
        echo "  unit        - Только unit-тесты (test_queries.py)"
        echo "  integration - Только integration-тесты (test_scheduler.py)"
        echo "  scenario    - Только сценарные тесты (test_scenarios.py)"
        echo "  edge        - Только тесты граничных условий (test_edge_cases.py)"
        echo "  coverage    - Все тесты с отчётом покрытия"
        echo "  fast        - Только быстрые тесты"
        echo "  all         - Все тесты (по умолчанию)"
        exit 1
        ;;
esac

echo -e "\n${GREEN}✓ Тесты завершены${NC}"
