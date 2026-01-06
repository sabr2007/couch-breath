-- Таблица для хранения маппинга вопросов куратору
-- Решает проблему потери данных при перезапуске бота

CREATE TABLE IF NOT EXISTS support_questions (
    id SERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,           -- ID сообщения в чате куратора
    student_id BIGINT NOT NULL,           -- tg_id студента
    lesson_id INTEGER,                    -- ID урока (опционально)
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индекс для быстрого поиска по message_id
CREATE INDEX IF NOT EXISTS idx_support_questions_message_id ON support_questions(message_id);

-- Автоочистка старых записей (старше 30 дней)
-- Можно настроить через pg_cron или периодическую задачу
