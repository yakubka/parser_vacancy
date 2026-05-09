"""
Генерация сопроводительных писем через Groq API (llama-3.3-70b-versatile).
Фоллбэк — готовый шаблон на основе примеров Yokub'а.
"""

import httpx
import config

# ─── Few-shot примеры в промпте ───────────────────────────────────────────────

EXAMPLES = """
ПРИМЕР 1 (Full-stack вакансия):
Здравствуйте, увидел вакансию Full-stack Developer, задачи по разработке мне знакомы.
У меня более двух лет коммерческой разработки на Python и фронтенде. Стек: FastAPI, Vue 3, PostgreSQL, Docker, Telegram Bot API (aiogram), CI/CD, асинхронное программирование. Делал полноценного Telegram-бота с платежами и админкой, интегрировал LLM (OpenRouter, Gemini), настраивал деплой на VPS с Nginx. Имею опыт с Redis и Celery. Работаю с Claude, но всегда понимаю генерируемый код и могу отладить без AI.
Буду рад обсудить детали.

ПРИМЕР 2 (AI Engineer Fintech):
Здравствуйте, увидел вакансию AI Engineer Fintech. Задачи по разработке RAG-систем, интеграции LLM в продакшен и работе с real‑time архитектурой мне знакомы.
У меня более двух лет коммерческой разработки на Python. Стек: FastAPI, asyncio, PostgreSQL, интеграции с LLM (OpenRouter, Gemini, локально Ollama), построение RAG на основе эмбеддингов и векторного поиска, микросервисная архитектура, Docker, CI/CD. Понимаю пайплайны голосовых и чат‑агентов: от STT до TTS, на практике собирал текстовых агентов с tool use. Опыт работы с RabbitMQ и WebRTC пока небольшой, но я строил событийно‑ориентированные асинхронные очереди (webhook + idempotency) и готов быстро освоить брокеры.
Буду рад обсудить детали.

ПРИМЕР 3 (AI/Python Intern):
Здравствуйте. Увидел вакансию AI/Python Intern. Задачи по написанию скриптов на Python, работе с AI и автоматизации процессов мне знакомы.
У меня более двух лет коммерческой разработки на Python. Стек: FastAPI, асинхронное программирование, интеграции с внешними API. Работал с AI — использовал OpenRouter и Gemini API в реальных проектах, в том числе с LLM-генерацией и агентоподобными сценариями. Также писал сервисы автоматизации, например браузерного сбора данных на Playwright. Готов выполнять качественные задачи, учиться новому и приносить пользу продукту.
Буду рад обсудить детали.
"""

PROMPT_TEMPLATE = """Ты помогаешь Python-разработчику Yokub'у (2+ года коммерческого опыта) писать сопроводительные письма.

Вот три примера его писем — строго придерживайся этого стиля, структуры и тона:
{examples}

---

Профиль Yokub'а:
{profile}

Совпавшие технологии из вакансии: {matched_stack}

Вакансия:
{vacancy_text}

---

Напиши сопроводительное письмо по этой вакансии. Правила:
- Структура как в примерах: приветствие → название вакансии → "задачи мне знакомы" → опыт/стек → конкретные совпадения с вакансией → "Буду рад обсудить детали."
- Упомяни 2-3 технологии из "Совпавших технологий"
- Адаптируй стек под конкретную вакансию — не копируй один пример целиком
- Если вакансия на фриланс/проект — тон чуть короче и конкретнее
- Только русский язык, живой тон, без воды
- Только текст письма, без пояснений

Сопроводительное:"""


# ─── Groq API ─────────────────────────────────────────────────────────────────

async def generate_cover_letter(vacancy_text: str, profile: dict, score_details: dict = None) -> str:
    profile_text  = profile.get("profile_text", "")
    matched       = score_details.get("matched_stack", []) if score_details else []
    matched_str   = ", ".join(matched) if matched else "не определены"

    prompt = PROMPT_TEMPLATE.format(
        examples=EXAMPLES,
        profile=profile_text[:600],
        matched_stack=matched_str,
        vacancy_text=vacancy_text[:1200],
    )

    try:
        letter = await _groq_generate(prompt)
        return letter.strip()
    except Exception as e:
        print(f"[LLM] Groq недоступен ({e}), использую шаблон")
        return _fallback_letter(profile, score_details)


async def _groq_generate(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       config.GROQ_MODEL,
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": 0.65,
        "max_tokens":  350,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# ─── Фоллбэк-шаблон ───────────────────────────────────────────────────────────

def _fallback_letter(profile: dict, score_details: dict = None) -> str:
    matched = score_details.get("matched_stack", [])[:4] if score_details else []
    techs   = f"Стек: {', '.join(matched)}." if matched else "Стек: FastAPI, PostgreSQL, Docker."
    return (
        f"Здравствуйте, увидел вакансию и задачи мне знакомы.\n"
        f"У меня более двух лет коммерческой разработки на Python. "
        f"{techs} Работал с Telegram Bot API, интегрировал LLM, "
        f"настраивал деплой на VPS.\n"
        f"Буду рад обсудить детали."
    )
