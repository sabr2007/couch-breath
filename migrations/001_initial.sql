-- ============================================
-- Telegram Bot "Дыхание Тренера" — Initial Schema
-- ============================================

-- Пользователи
CREATE TABLE IF NOT EXISTS users (
    tg_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    full_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    state VARCHAR(50) DEFAULT 'NO_AUTH',
    last_activity TIMESTAMP DEFAULT NOW()
);

-- Уроки
CREATE TABLE IF NOT EXISTS lessons (
    id SERIAL PRIMARY KEY,
    order_num INT UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    content_text TEXT,
    video_url VARCHAR(500),
    has_homework BOOLEAN DEFAULT TRUE,
    homework_type VARCHAR(20) DEFAULT 'text'
);

-- Зачисления
CREATE TABLE IF NOT EXISTS enrollments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
    start_date TIMESTAMP DEFAULT NOW(),
    current_lesson_id INT REFERENCES lessons(id) DEFAULT 1,
    UNIQUE(user_id)
);

-- Прогресс по урокам
CREATE TABLE IF NOT EXISTS user_progress (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
    lesson_id INT REFERENCES lessons(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'LOCKED',
    completed_at TIMESTAMP,
    UNIQUE(user_id, lesson_id)
);

-- Сданные работы
CREATE TABLE IF NOT EXISTS submissions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
    lesson_id INT REFERENCES lessons(id) ON DELETE CASCADE,
    content_text TEXT,
    content_type VARCHAR(20),
    ai_verdict VARCHAR(20),
    ai_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Коды доступа
CREATE TABLE IF NOT EXISTS access_codes (
    code VARCHAR(50) PRIMARY KEY,
    is_used BOOLEAN DEFAULT FALSE,
    used_by BIGINT REFERENCES users(tg_id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Лог напоминаний
CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
    reminder_type VARCHAR(10),
    sent_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- Индексы
-- ============================================

CREATE INDEX IF NOT EXISTS idx_progress_user ON user_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_submissions_user_lesson ON submissions(user_id, lesson_id);
CREATE INDEX IF NOT EXISTS idx_submissions_created ON submissions(created_at);
CREATE INDEX IF NOT EXISTS idx_codes_unused ON access_codes(is_used) WHERE is_used = FALSE;
CREATE INDEX IF NOT EXISTS idx_users_last_activity ON users(last_activity);

-- ============================================
-- Данные уроков
-- ============================================

INSERT INTO lessons (order_num, title, has_homework, homework_type, video_url) VALUES
(1,  'Что есть тренинг?', TRUE, 'text', 'https://youtu.be/wERSPxhPqXg'),
(2,  'Способы передачи знаний', TRUE, 'text', 'https://youtu.be/h5maY1xalH4'),
(3,  'Особенности обучения взрослых', TRUE, 'text', 'https://youtu.be/j4DsZ-2WT6U'),
(4,  'Цикл Колба на практике', TRUE, 'video_link', 'https://youtu.be/qXtR2rbLP_E'),
(5,  'Методы работы с группой', TRUE, 'text', 'https://youtu.be/okHIGqNYWZQ'),
(6,  'Сезонность: Весна', TRUE, 'text', 'https://youtu.be/otgThzHjWBY'),
(7,  'Сезонность: Лето', TRUE, 'text', 'https://youtu.be/3crwHSV8ar8'),
(8,  'Сезонность: Осень', FALSE, NULL, 'https://youtu.be/cbaWx59WTTQ'),
(9,  'Сезонность: Зима', TRUE, 'video_link', 'https://youtu.be/UfSAL5mTWJ4'),
(10, 'Групповая динамика', TRUE, 'text', 'https://youtu.be/P0mf-Gqsyuc'),
(11, 'Цикл Колба: формирование навыка', TRUE, 'file', 'https://youtu.be/YNuqggee1hI'),
(12, 'Петлеобразное развитие', TRUE, 'text', 'https://youtu.be/aFyub7ji1v8'),
(13, 'Пирамида обучения', TRUE, 'text', 'https://youtu.be/jfQx05gSqI8'),
(14, 'Матрица осознанности', TRUE, 'text', 'https://youtu.be/80dx8YJf6Ms'),
(15, 'Зоны развития по Выготскому', TRUE, 'text', 'https://youtu.be/-crlu_B44d8'),
(16, 'Цветовой профиль тренера', TRUE, 'text', 'https://youtu.be/iIxARBNwpsk'),
(17, 'Уникальный стиль через ценности', TRUE, 'text', 'https://youtu.be/k2aFgspqDnM'),
(18, 'Бонус: Синдром самозванца', FALSE, NULL, 'https://youtu.be/GpUNjX_7e4Y')
ON CONFLICT (order_num) DO NOTHING;
