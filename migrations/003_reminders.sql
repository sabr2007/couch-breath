-- Таблица для отслеживания отправленных напоминаний
-- Предотвращает спам: напоминания отправляются единоразово на 3 и 7 день

CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(tg_id) ON DELETE CASCADE,
    reminder_type VARCHAR(20) NOT NULL,  -- 'soft' (3 дня) или 'strong' (7 дней)
    sent_at TIMESTAMP DEFAULT NOW(),

    -- Уникальность: один тип напоминания на пользователя
    UNIQUE(user_id, reminder_type)
);

CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
