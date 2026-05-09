-- Выполни этот файл в Supabase → SQL Editor

create extension if not exists vector;

-- ─── Каналы Telegram ──────────────────────────────────────────────────────────
create table if not exists tg_channels (
    id          serial primary key,
    username    text unique not null,
    title       text,
    last_msg_id bigint default 0,
    active      boolean default true,
    added_at    timestamp default now()
);

-- ─── Вакансии ─────────────────────────────────────────────────────────────────
create table if not exists vacancies (
    id              serial primary key,
    source          text not null,            -- 'telegram', 'getmatch', 'hh', 'geekjob', 'huntee'
    source_id       text,
    channel         text,

    title           text,
    full_text       text not null,
    url             text,

    contacts        text[],
    contact_hash    text,

    text_hash       text unique,
    embedding       vector(384),

    similarity_score float default 0,

    -- 'matched'  = remote упомянут + хороший скор → с сопроводительным
    -- 'unsorted' = remote не упомянут → сам смотришь
    category        text default 'matched',
    is_remote       boolean default false,

    cover_letter    text,

    is_duplicate    boolean default false,
    sent_to_user    boolean default false,
    created_at      timestamp default now()
);

-- ─── Профиль ──────────────────────────────────────────────────────────────────
create table if not exists user_profile (
    id           serial primary key,
    profile_text text not null,
    embedding    vector(384),
    updated_at   timestamp default now()
);

-- ─── Индексы ──────────────────────────────────────────────────────────────────
create index if not exists idx_vacancies_text_hash    on vacancies(text_hash);
create index if not exists idx_vacancies_contact_hash on vacancies(contact_hash);
create index if not exists idx_vacancies_category     on vacancies(category);
create index if not exists idx_vacancies_created      on vacancies(created_at);
create index if not exists idx_vacancies_embedding    on vacancies
    using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- ─── find_similar_vacancies ───────────────────────────────────────────────────
create or replace function find_similar_vacancies(
    query_embedding vector(384),
    similarity_threshold float default 0.85,
    days_back int default 30
)
returns table(id int, similarity float)
language sql as $$
    select v.id, 1 - (v.embedding <=> query_embedding) as similarity
    from vacancies v
    where
        v.created_at > now() - (days_back || ' days')::interval
        and v.is_duplicate = false
        and 1 - (v.embedding <=> query_embedding) > similarity_threshold
    order by similarity desc
    limit 5;
$$;

-- ─── Telegram каналы ──────────────────────────────────────────────────────────
insert into tg_channels (username, title) values
    -- Python / Backend / IT вакансии
    ('python_jobs',              'Python Jobs'),
    ('job_python',               'Job Python'),
    ('python_djangojobs',        'Python Django Jobs'),
    ('pydevjob',                 'PyDev Job'),
    ('python_jobs_top',          'Python Jobs Top'),
    ('ru_pythonjobs',            'RU Python Jobs'),
    ('Pythonist_Jobs',           'Pythonist Jobs'),
    ('DailySWJobs',              'Daily SW Jobs'),
    ('backend_vacancy',          'Backend Vacancy'),
    ('backend_job_geeklink',     'Backend Job Geeklink'),
    ('devs_it',                  'Devs IT'),
    ('middle_job_it',            'Middle Job IT'),
    ('ayti_jobs',                'AYTI Jobs'),

    -- Remote / IT общие
    ('remote_job_it_geeklink',   'Remote Job IT Geeklink'),
    ('workitkz',                 'Work IT KZ'),
    ('itcloz',                   'IT Cloz'),
    ('rabota_razrabotchikc',     'Работа Разработчикам'),
    ('ai_rabota',                'AI Работа'),

    -- Крипто / Web3
    ('cryptoheadhunter',         'Crypto Head Hunter'),
    ('job_web3',                 'Job Web3'),
    ('workingincrypto',          'Working in Crypto'),

    -- Узбекистан / СНГ
    ('uzdev_jobs',               'UzDev Jobs'),

    -- Фриланс
    ('freelance_rabota_chat',    'Freelance Работа Chat'),
    ('Koteyka_Freelancer',       'Котейка Фрилансер'),
    ('GetClient',                'GetClient'),
    ('workk_on',                 'Work On'),
    ('freelancce',               'Freelance'),
    ('udafrii',                  'Удафри'),
    ('frilanser_vacansii',       'Фрилансер Вакансии'),

    -- Медиа / другое
    ('rabotavmediawe',           'Работа в Медиа'),

    -- ── GeekLink: Разработка ──────────────────────────────────────────────────
    ('developers_job_geeklink',  'GL: Разработчики (общее)'),
    ('backend_job_geeklink',     'GL: Backend'),           -- уже был, on conflict пропустит
    ('fullstack_job_geeklink',   'GL: Fullstack'),
    ('python_django_job',        'GL: Python/Django'),
    ('js_node_typescript_vue_job','GL: JS/Node/Vue/TS'),
    ('blockchain_solidity_job',  'GL: Blockchain/Solidity'),
    ('pentest_appsec_devsecops_job','GL: DevSecOps/Pentest'),
    ('devops_job_geeklink',      'GL: DevOps'),
    ('database_administrator_job','GL: DB Admin'),

    -- ── GeekLink: По уровням ──────────────────────────────────────────────────
    ('junior_intern_job',        'GL: Junior/Intern'),
    ('middle_job_it',            'GL: Middle'),
    ('senior_job_it',            'GL: Senior'),
    ('teamlead_job_it',          'GL: Teamlead'),

    -- ── GeekLink: Remote / Релокация ──────────────────────────────────────────
    ('remote_job_it_geeklink',   'GL: Удалёнка'),          -- уже был
    ('relocate_job_geeklink',    'GL: Релокация')

on conflict (username) do nothing;
