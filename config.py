import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram клиент (для чтения каналов) ─────────────────────────────────────
TG_API_ID       = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH     = os.getenv("TG_API_HASH", "")
TG_PHONE        = os.getenv("TG_PHONE", "")

# ─── Telegram бот (для отправки результатов) ──────────────────────────────────
TG_BOT_TOKEN    = os.getenv("TG_BOT_TOKEN", "")
TG_YOUR_CHAT_ID = int(os.getenv("TG_YOUR_CHAT_ID", "0"))

# ─── Supabase ─────────────────────────────────────────────────────────────────
SUPABASE_URL    = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY", "")

# ─── Ollama ───────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "gemma2:2b")

# ─── Модель эмбеддингов ────────────────────────────────────────────────────────
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ─── Дедупликация ─────────────────────────────────────────────────────────────
CONTACT_DEDUP_TITLE_THRESHOLD = 0.70
TEXT_SIMILARITY_THRESHOLD     = 0.85
DEDUP_DAYS_LOOKBACK           = 30

# ─── Скоринг ──────────────────────────────────────────────────────────────────
SCORE_SEMANTIC  = 0.60
SCORE_STACK     = 0.25
SCORE_FORMAT    = 0.10
SCORE_FRESHNESS = 0.05

MIN_SCORE_TO_SEND = 0.58   # порог для "подходящих" вакансий
TOP_N_PER_RUN     = 7
PREFERRED_FORMAT  = "remote"

# ─── Remote-фильтр ────────────────────────────────────────────────────────────
# Если ни одно из слов не найдено — вакансия идёт в unsorted (сам смотришь)
REMOTE_SIGNALS = [
    "remote", "удалённо", "удаленно", "дистанционно",
    "full remote", "fully remote", "полностью удалённо",
    "работа из дома", "из любой точки", "anywhere",
    "remote-first", "remote first",
]

# ─── Твой стек (Yokub) ────────────────────────────────────────────────────────
USER_TECH_STACK = [
    "python", "fastapi", "postgresql", "redis", "docker",
    "nginx", "asyncio", "pydantic", "sqlalchemy", "playwright",
    "celery", "websocket", "sse", "mongodb", "jwt",
    "rbac", "rest api", "gitlab", "ubuntu", "flask",
    "node.js", "nodejs", "typescript", "vue",
]

# ─── Стоп-слова (явно нерелевантные вакансии — скипаем сразу) ─────────────────
STOP_WORDS = [
    "java ", " c++ ", " c# ", "golang ", " go ",
    "ruby ", " php ", "1c ", "битрикс",
    "ios developer", "android developer",
    "data scientist", "machine learning engineer",
    "devops engineer", "sre engineer",
    "qa engineer", "tester", "qa automation",
    "продажи", "менеджер по продажам", "sales",
    "дизайнер", "верстальщик",
]
