"""
FSM состояния пользователей
"""

from enum import Enum


class UserState(str, Enum):
    """Состояния пользователя в боте"""
    
    # Начальные состояния
    NO_AUTH = "NO_AUTH"          # Не авторизован (нет кода доступа)
    IDLE = "IDLE"                # Авторизован, ждёт действий
    
    # Ввод кода доступа
    WAITING_CODE = "WAITING_CODE"  # Ожидание ввода кода
    
    # Работа с уроками
    VIEWING_LESSON = "VIEWING_LESSON"  # Смотрит урок
    
    # Сдача ДЗ
    WAITING_HW = "WAITING_HW"      # Ожидание ответа на ДЗ
    PROCESSING = "PROCESSING"      # Обработка ответа (LLM проверяет)
    
    # Поддержка
    WAITING_QUESTION = "WAITING_QUESTION"  # Ожидание вопроса куратору
