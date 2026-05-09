-- ─────────────────────────────────────────────────────────────────────────────
-- Migration 001: Новые каналы + health-check поля + web_sources
-- Выполни в Supabase → SQL Editor
-- ─────────────────────────────────────────────────────────────────────────────


-- ── 1. Добавляем health-check колонки в tg_channels ──────────────────────────

ALTER TABLE tg_channels ADD COLUMN IF NOT EXISTS last_post_at    timestamptz;
ALTER TABLE tg_channels ADD COLUMN IF NOT EXISTS is_alive        boolean DEFAULT true;
ALTER TABLE tg_channels ADD COLUMN IF NOT EXISTS last_checked_at timestamptz;


-- ── 2. Новые фриланс и IT каналы ─────────────────────────────────────────────

INSERT INTO tg_channels (username, title, active) VALUES

    -- Фриланс чаты (можно постить о себе)
    ('proffreelancee_chat',   'Профессиональный фриланс чат',  true),
    ('jobospherechat',        'Jobosphere чат',                true),
    ('teletoloka',            'Телетолока digital чат',        true),
    ('ipomogator',            'Помогатор биржа',               true),
    ('freelancealeksei',      'Фриланс вакансии',              true),

    -- IT фриланс каналы
    ('FreeVacanciesIT',       'IT Фриланс вакансии',           true),
    ('ITaward',               'IT Award фриланс',              true),
    ('distantsiya',           'Дистанция удалёнка',            true),
    ('workzavr',              'Воркзавр агрегатор',            true),
    ('Remote_IT',             'Remote IT',                     true),

    -- Общие IT с фрилансом
    ('over100',               'Вакансии от 100к',              true),
    ('airabota',              'AI работа',                     true),

    -- Node.js (есть опыт)
    ('nodejs_jobs',           'Node.js Jobs',                  true),
    ('js_jobs_ru',            'JS Jobs RU',                    true)

ON CONFLICT (username) DO NOTHING;


-- ── 3. Таблица web_sources (для Scrapling-парсера) ───────────────────────────

CREATE TABLE IF NOT EXISTS web_sources (
    id              serial PRIMARY KEY,
    url             text UNIQUE NOT NULL,
    title           text,
    active          boolean DEFAULT true,
    last_scraped_at timestamptz,
    added_at        timestamptz DEFAULT now()
);

INSERT INTO web_sources (url, title) VALUES
    ('https://freten.ru/projects/?category=development',          'Freten — Разработка'),
    ('https://workzilla.com/tasks/?category=programming',         'Workzilla — Программирование'),
    ('https://weblancer.net/projects/?category=python-backend',   'Weblancer — Python/Backend'),
    ('https://workspace.ru/tenders/works/?category=development',  'Workspace — Разработка')
ON CONFLICT (url) DO NOTHING;


-- ── 4. Индекс на is_alive для быстрой выборки активных каналов ───────────────

CREATE INDEX IF NOT EXISTS idx_tg_channels_alive
    ON tg_channels (active, is_alive);

CREATE INDEX IF NOT EXISTS idx_web_sources_active
    ON web_sources (active);
