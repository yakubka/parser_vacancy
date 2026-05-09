"""
Парсер geekjob.ru — IT job board.
Используем открытый поиск, авторизация не нужна.
"""

import httpx
import re
from datetime import datetime, timezone
from parsers.telegram_parser import RawVacancy

BASE = "https://geekjob.ru"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


async def parse_geekjob(keywords: list[str] = None) -> list[RawVacancy]:
    if keywords is None:
        keywords = ["python", "fastapi", "backend"]

    vacancies = []
    seen_ids = set()

    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for kw in keywords[:3]:
            try:
                resp = await client.get(f"{BASE}/vacancies", params={"q": kw})
                found = _parse_html(resp.text)
                for v in found:
                    if v.source_id not in seen_ids:
                        seen_ids.add(v.source_id)
                        vacancies.append(v)
            except Exception as e:
                print(f"[GeekJob] Ошибка '{kw}': {e}")

    print(f"[GeekJob] Найдено: {len(vacancies)}")
    return vacancies


def _parse_html(html: str) -> list[RawVacancy]:
    vacancies = []

    # Ищем блоки вакансий
    blocks = re.findall(
        r'<article[^>]*class="[^"]*vacancy[^"]*"[^>]*>(.*?)</article>',
        html, re.DOTALL | re.IGNORECASE
    )

    for block in blocks:
        try:
            # Заголовок
            title_m = re.search(r'<h\d[^>]*>(.*?)</h\d>', block, re.DOTALL)
            title = _clean(title_m.group(1)) if title_m else ""

            # Ссылка
            link_m = re.search(r'href="(/vacancy/[^"]+)"', block)
            url = BASE + link_m.group(1) if link_m else ""
            vacancy_id = link_m.group(1).split("/")[-1] if link_m else ""

            # Описание
            desc_m = re.search(r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
            desc = _clean(desc_m.group(1)) if desc_m else ""

            # Зарплата
            salary_m = re.search(r'<span[^>]*class="[^"]*salary[^"]*"[^>]*>(.*?)</span>', block, re.DOTALL)
            salary = _clean(salary_m.group(1)) if salary_m else ""

            full_text = "\n".join(filter(None, [title, salary, desc]))
            if not full_text.strip():
                continue

            vacancies.append(RawVacancy(
                source="geekjob",
                source_id=vacancy_id,
                full_text=full_text,
                url=url,
                contacts=[],
                posted_at=datetime.now(timezone.utc),
            ))
        except Exception:
            continue

    return vacancies


def _clean(html: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', text).strip()
