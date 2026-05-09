"""
Парсер huntee.ru — IT вакансии с фокусом на удалёнку.
"""

import httpx
import re
from datetime import datetime, timezone
from parsers.telegram_parser import RawVacancy

BASE = "https://huntee.ru"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/html",
}


async def parse_huntee() -> list:
    vacancies = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        try:
            # Пробуем JSON API
            resp = await client.get(
                f"{BASE}/api/vacancies",
                params={"specialization": "backend", "remote": "true", "per_page": 50}
            )
            if resp.headers.get("content-type", "").startswith("application/json"):
                data = resp.json()
                vacancies = _parse_json(data)
            else:
                # Фолбэк на HTML
                resp2 = await client.get(f"{BASE}/vacancies", params={"remote": 1})
                vacancies = _parse_html(resp2.text)
        except Exception as e:
            print(f"[Huntee] Ошибка: {e}")

    print(f"[Huntee] Найдено: {len(vacancies)}")
    return vacancies


def _parse_json(data) -> list:
    items = data if isinstance(data, list) else data.get("data", data.get("vacancies", []))
    vacancies = []

    for item in items:
        title    = item.get("title", item.get("name", ""))
        company  = item.get("company", {}).get("name", "") if isinstance(item.get("company"), dict) else item.get("company", "")
        desc     = item.get("description", item.get("body", ""))
        salary   = item.get("salary", "")
        url      = item.get("url", item.get("link", ""))
        vac_id   = str(item.get("id", url))

        full_text = "\n".join(filter(None, [title, company, str(salary), _strip_html(desc)]))
        if not full_text.strip():
            continue

        vacancies.append(RawVacancy(
            source="huntee",
            source_id=vac_id,
            full_text=full_text[:3000],
            url=url,
            contacts=[],
            posted_at=datetime.now(timezone.utc),
        ))

    return vacancies


def _parse_html(html: str) -> list:
    vacancies = []
    blocks = re.findall(r'<div[^>]*class="[^"]*vacancy[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)

    for block in blocks:
        title_m = re.search(r'<h\d[^>]*>(.*?)</h\d>', block, re.DOTALL)
        link_m  = re.search(r'href="(/vacancies?/[^"]+)"', block)

        if not title_m:
            continue

        title = _strip_html(title_m.group(1))
        url   = BASE + link_m.group(1) if link_m else ""

        vacancies.append(RawVacancy(
            source="huntee",
            source_id=url,
            full_text=title,
            url=url,
            contacts=[],
            posted_at=datetime.now(timezone.utc),
        ))

    return vacancies


def _strip_html(text: str) -> str:
    clean = re.sub(r'<[^>]+>', ' ', text or "")
    return re.sub(r'\s+', ' ', clean).strip()
