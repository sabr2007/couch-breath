"""
Модели данных (dataclasses)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """Пользователь бота"""
    tg_id: int
    username: Optional[str]
    full_name: Optional[str]
    created_at: datetime
    state: str
    last_activity: datetime


@dataclass
class Lesson:
    """Урок курса"""
    id: int
    order_num: int
    title: str
    content_text: Optional[str]
    video_url: Optional[str]
    has_homework: bool
    homework_type: Optional[str]  # text, video_link, file


@dataclass
class Enrollment:
    """Зачисление на курс"""
    id: int
    user_id: int
    start_date: datetime
    current_lesson_id: int


@dataclass
class UserProgress:
    """Прогресс пользователя по уроку"""
    id: int
    user_id: int
    lesson_id: int
    status: str  # LOCKED, OPEN, COMPLETED
    completed_at: Optional[datetime]


@dataclass
class Submission:
    """Сданное ДЗ"""
    id: int
    user_id: int
    lesson_id: int
    content_text: Optional[str]
    content_type: str  # text, file, video_link
    ai_verdict: Optional[str]
    ai_message: Optional[str]
    created_at: datetime


@dataclass
class AccessCode:
    """Код доступа"""
    code: str
    is_used: bool
    used_by: Optional[int]
    created_at: datetime
