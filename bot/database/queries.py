"""
SQL-запросы к базе данных
"""

from datetime import datetime, timedelta
from typing import Optional, List

from bot.database.connection import get_pool
from bot.database.models import User, Lesson, Enrollment, UserProgress, Submission, AccessCode


# ============================================
# Users
# ============================================

async def get_user(tg_id: int) -> Optional[User]:
    """Получить пользователя по Telegram ID"""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM users WHERE tg_id = $1",
        tg_id
    )
    if row:
        return User(**dict(row))
    return None


async def create_user(tg_id: int, username: str, full_name: str) -> User:
    """Создать нового пользователя"""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO users (tg_id, username, full_name)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        tg_id, username, full_name
    )
    return User(**dict(row))


async def update_user_state(tg_id: int, state: str):
    """Обновить состояние пользователя"""
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET state = $1, last_activity = NOW() WHERE tg_id = $2",
        state, tg_id
    )


async def update_last_activity(tg_id: int):
    """Обновить время последней активности и сбросить напоминания"""
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET last_activity = NOW() WHERE tg_id = $1",
        tg_id
    )
    # Сбрасываем напоминания — пользователь вернулся
    await pool.execute(
        "DELETE FROM reminders WHERE user_id = $1",
        tg_id
    )


# ============================================
# Lessons
# ============================================

async def get_lesson(lesson_id: int) -> Optional[Lesson]:
    """Получить урок по ID"""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM lessons WHERE id = $1",
        lesson_id
    )
    if row:
        return Lesson(**dict(row))
    return None


async def get_lesson_by_order(order_num: int) -> Optional[Lesson]:
    """Получить урок по порядковому номеру"""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM lessons WHERE order_num = $1",
        order_num
    )
    if row:
        return Lesson(**dict(row))
    return None


async def get_all_lessons() -> List[Lesson]:
    """Получить все уроки"""
    pool = await get_pool()
    rows = await pool.fetch("SELECT * FROM lessons ORDER BY order_num")
    return [Lesson(**dict(row)) for row in rows]


async def check_lesson_access(user_id: int, lesson_id: int) -> bool:
    """Проверить, имеет ли пользователь доступ к уроку (OPEN или COMPLETED)"""
    pool = await get_pool()
    has_access = await pool.fetchval(
        """
        SELECT EXISTS(
            SELECT 1 FROM user_progress
            WHERE user_id = $1 AND lesson_id = $2
        ) OR EXISTS(
            SELECT 1 FROM enrollments
            WHERE user_id = $1 AND current_lesson_id = $2
        )
        """,
        user_id, lesson_id
    )
    return has_access


async def get_lessons_with_status(user_id: int) -> List[dict]:
    """
    Получить все уроки со статусами для пользователя.
    Возвращает: order_num, title, status (LOCKED/OPEN/COMPLETED)
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT
            l.id,
            l.order_num,
            l.title,
            CASE
                WHEN up.status = 'COMPLETED' THEN 'COMPLETED'
                WHEN up.status IS NOT NULL THEN 'OPEN'
                WHEN e.current_lesson_id = l.id THEN 'OPEN'
                ELSE 'LOCKED'
            END as status
        FROM lessons l
        LEFT JOIN user_progress up ON up.lesson_id = l.id AND up.user_id = $1
        LEFT JOIN enrollments e ON e.user_id = $1
        ORDER BY l.order_num
        """,
        user_id
    )
    return [dict(row) for row in rows]


# ============================================
# Enrollments
# ============================================

async def get_enrollment(user_id: int) -> Optional[Enrollment]:
    """Получить зачисление пользователя"""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM enrollments WHERE user_id = $1",
        user_id
    )
    if row:
        return Enrollment(**dict(row))
    return None


async def create_enrollment(user_id: int) -> Enrollment:
    """Создать зачисление (после активации кода)"""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO enrollments (user_id, current_lesson_id)
        VALUES ($1, 1)
        RETURNING *
        """,
        user_id
    )
    return Enrollment(**dict(row))


# ============================================
# User Progress
# ============================================

async def get_user_progress(user_id: int, lesson_id: int) -> Optional[UserProgress]:
    """Получить прогресс по уроку"""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM user_progress WHERE user_id = $1 AND lesson_id = $2",
        user_id, lesson_id
    )
    if row:
        return UserProgress(**dict(row))
    return None


async def set_lesson_status(user_id: int, lesson_id: int, status: str):
    """Установить статус урока"""
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO user_progress (user_id, lesson_id, status)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, lesson_id) 
        DO UPDATE SET status = $3
        """,
        user_id, lesson_id, status
    )


async def complete_lesson(user_id: int, lesson_id: int):
    """Завершить урок"""
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO user_progress (user_id, lesson_id, status, completed_at)
        VALUES ($1, $2, 'COMPLETED', NOW())
        ON CONFLICT (user_id, lesson_id) 
        DO UPDATE SET status = 'COMPLETED', completed_at = NOW()
        """,
        user_id, lesson_id
    )


# ============================================
# Submissions
# ============================================

async def create_submission(
    user_id: int,
    lesson_id: int,
    content_text: str,
    content_type: str,
    ai_verdict: str,
    ai_message: str
) -> Submission:
    """Сохранить сданное ДЗ"""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO submissions 
        (user_id, lesson_id, content_text, content_type, ai_verdict, ai_message)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        user_id, lesson_id, content_text, content_type, ai_verdict, ai_message
    )
    return Submission(**dict(row))


async def count_recent_submissions(user_id: int, lesson_id: int, hours: int = 1) -> int:
    """Количество попыток за последние N часов (для rate limiting)"""
    pool = await get_pool()
    count = await pool.fetchval(
        """
        SELECT COUNT(*) FROM submissions
        WHERE user_id = $1 AND lesson_id = $2
        AND created_at > NOW() - INTERVAL '1 hour' * $3
        """,
        user_id, lesson_id, hours
    )
    return count or 0


async def has_accepted_submission(user_id: int, lesson_id: int) -> bool:
    """Проверить, есть ли принятое ДЗ для урока"""
    pool = await get_pool()
    result = await pool.fetchval(
        """
        SELECT EXISTS(
            SELECT 1 FROM submissions
            WHERE user_id = $1 AND lesson_id = $2 AND ai_verdict = 'ACCEPT'
        )
        """,
        user_id, lesson_id
    )
    return result or False


# ============================================
# Access Codes
# ============================================

async def get_access_code(code: str) -> Optional[AccessCode]:
    """Получить код доступа"""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM access_codes WHERE code = $1",
        code
    )
    if row:
        return AccessCode(**dict(row))
    return None


async def use_access_code(code: str, user_id: int):
    """Пометить код как использованный"""
    pool = await get_pool()
    await pool.execute(
        "UPDATE access_codes SET is_used = TRUE, used_by = $2 WHERE code = $1",
        code, user_id
    )


async def create_access_code(code: str):
    """Создать новый код доступа"""
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO access_codes (code) VALUES ($1)",
        code
    )


# ============================================
# Admin / Stats
# ============================================

async def get_all_enrolled_users() -> List[User]:
    """Все зачисленные пользователи (для broadcast)"""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT u.* FROM users u
        INNER JOIN enrollments e ON u.tg_id = e.user_id
        """
    )
    return [User(**dict(row)) for row in rows]


async def get_inactive_users(days: int = 3) -> List[User]:
    """Пользователи без активности N дней"""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT u.* FROM users u
        INNER JOIN enrollments e ON u.tg_id = e.user_id
        WHERE u.last_activity < NOW() - INTERVAL '1 day' * $1
        """,
        days
    )
    return [User(**dict(row)) for row in rows]


async def get_users_ready_for_next_lesson() -> List[dict]:
    """
    Получить пользователей, которым пора открыть следующий урок.
    Условие: прошло >= 1 день с момента завершения текущего урока.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT
            e.user_id,
            e.current_lesson_id,
            l.order_num as current_order,
            up.completed_at
        FROM enrollments e
        INNER JOIN lessons l ON l.id = e.current_lesson_id
        INNER JOIN user_progress up ON up.user_id = e.user_id AND up.lesson_id = e.current_lesson_id
        WHERE
            up.status = 'COMPLETED'
            AND up.completed_at <= NOW() - INTERVAL '1 day'
            AND l.order_num < 18
            -- Проверяем, что следующий урок ещё НЕ открыт
            AND NOT EXISTS (
                SELECT 1 FROM user_progress up2
                INNER JOIN lessons l2 ON l2.id = up2.lesson_id
                WHERE up2.user_id = e.user_id
                AND l2.order_num = l.order_num + 1
            )
        """
    )
    return [dict(row) for row in rows]


async def unlock_next_lesson(user_id: int, current_order: int):
    """Открыть следующий урок пользователю"""
    pool = await get_pool()

    # Получаем следующий урок
    next_lesson = await pool.fetchrow(
        "SELECT id FROM lessons WHERE order_num = $1",
        current_order + 1
    )

    if not next_lesson:
        return None

    next_lesson_id = next_lesson["id"]

    # Обновляем current_lesson_id
    await pool.execute(
        "UPDATE enrollments SET current_lesson_id = $1 WHERE user_id = $2",
        next_lesson_id, user_id
    )

    # Открываем урок
    await pool.execute(
        """
        INSERT INTO user_progress (user_id, lesson_id, status)
        VALUES ($1, $2, 'OPEN')
        ON CONFLICT (user_id, lesson_id)
        DO UPDATE SET status = 'OPEN'
        """,
        user_id, next_lesson_id
    )

    return next_lesson_id


# ============================================
# Reminders (напоминания без спама)
# ============================================

async def get_users_for_reminder(days: int, reminder_type: str) -> List[User]:
    """
    Получить пользователей для напоминания.
    Возвращает только тех, кому ЕЩЁ НЕ отправляли данный тип напоминания.

    days: количество дней неактивности (3 или 7)
    reminder_type: 'soft' (3 дня) или 'strong' (7 дней)
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT u.* FROM users u
        INNER JOIN enrollments e ON u.tg_id = e.user_id
        LEFT JOIN reminders r ON r.user_id = u.tg_id AND r.reminder_type = $2
        WHERE u.last_activity < NOW() - INTERVAL '1 day' * $1
          AND u.last_activity >= NOW() - INTERVAL '14 days'  -- Не спамим после 14 дней
          AND r.id IS NULL  -- Напоминание этого типа ещё не отправлялось
        """,
        days, reminder_type
    )
    return [User(**dict(row)) for row in rows]


async def log_reminder(user_id: int, reminder_type: str):
    """Записать отправленное напоминание"""
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO reminders (user_id, reminder_type)
        VALUES ($1, $2)
        ON CONFLICT (user_id, reminder_type) DO NOTHING
        """,
        user_id, reminder_type
    )


async def clear_reminders_on_activity(user_id: int):
    """
    Очистить напоминания при возвращении пользователя.
    Вызывается при обновлении last_activity.
    """
    pool = await get_pool()
    await pool.execute(
        "DELETE FROM reminders WHERE user_id = $1",
        user_id
    )
