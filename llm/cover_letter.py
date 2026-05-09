import httpx
import config

PROMPT_TEMPLATE = """Ты — помощник по поиску работы. Пиши кратко и по делу.

Профиль разработчика:
{profile}

Вакансия:
{vacancy_text}

Напиши короткое сопроводительное сообщение для HR (3-4 предложения максимум).
Требования:
- Только на русском языке
- Упомяни 2-3 конкретных совпадения между профилем и вакансией
- Живой разговорный тон, не шаблонный
- Заканчивай предложением обсудить детали
- НЕ пиши "Здравствуйте" и "С уважением"
- Только текст письма, без лишних слов

Сопроводительное:"""


async def generate_cover_letter(vacancy_text: str, profile: dict, score_details: dict = None) -> str:
    profile_text = profile.get("profile_text", "")
    matched = score_details.get("matched_stack", []) if score_details else []
    if matched:
        profile_text += f"\nСовпавшие технологии: {', '.join(matched)}"

    prompt = PROMPT_TEMPLATE.format(
        profile=profile_text[:800],
        vacancy_text=vacancy_text[:1500],
    )

    try:
        letter = await _ollama_generate(prompt)
        return letter.strip()
    except Exception as e:
        print(f"[LLM] Ollama недоступна ({e}), использую шаблон")
        return _fallback_letter(profile, score_details)


async def _ollama_generate(prompt: str) -> str:
    payload = {
        "model": config.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 200},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{config.OLLAMA_BASE_URL}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")


def _fallback_letter(profile: dict, score_details: dict = None) -> str:
    name = profile.get("name", "")
    about = profile.get("about_short", profile.get("profile_text", "")[:200])
    portfolio = profile.get("portfolio_url", "")
    matched = score_details.get("matched_stack", [])[:4] if score_details else []
    techs = f" Работал с {', '.join(matched)} в продакшн-проектах." if matched else ""
    letter = f"Привет! Меня зовут {name}, Python backend разработчик.{techs} {about}"
    if portfolio:
        letter += f" Портфолио: {portfolio}"
    letter += " Готов обсудить детали!"
    return letter
