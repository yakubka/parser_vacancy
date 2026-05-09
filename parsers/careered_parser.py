"""
Парсер careered.io через JSON API.

API: GET https://careered.io/api/jobs?page=N
Возвращает 20 вакансий на страницу, поле total — общее количество.
Фильтруем по релевантным тегам для Python/backend разработчика.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from parsers.telegram_parser import RawVacancy

RELEVANT_TAGS = {
    "Python",
    "JavaScript / TypeScript",
    "DS / ML",
    "Data Engineer",
}

BASE_URL   = "https://careered.io"
API_URL    = f"{BASE_URL}/api/jobs"
MAX_PAGES  = 10   # не более 200 вакансий за раз

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _get_feature(features: list, key: str) -> str:
    for f in features:
        if f.get("key") == key:
            return str(f.get("value", ""))
    return ""


def _build_full_text(features: list, tag_name: str) -> str:
    name        = _get_feature(features, "name")
    summary     = _get_feature(features, "summary")
    location    = _get_feature(features, "location")
    term        = _get_feature(features, "term")
    salary_from = _get_feature(features, "salary_from")
    salary_to   = _get_feature(features, "salary_to")
    currency    = _get_feature(features, "salary_currency")

    parts = [name, ""]
    if summary:
        parts.append(summary)

    meta = []
    if location and location not in ("", "null"):
        meta.append(f"Локация: {location}")
    if term:
        term_ru = {"fulltime": "полная занятость", "parttime": "частичная"}.get(term, term)
        meta.append(f"Формат: {term_ru}")
    if salary_from and salary_from != "0":
        sal = f"Зарплата: от {salary_from}"
        if salary_to and salary_to != "0":
            sal += f" до {salary_to}"
        sal += f" {currency}/мес"
        meta.append(sal)
    if tag_name:
        meta.append(f"Категория: {tag_name}")

    if meta:
        parts.append("\n".join(meta))

    return "\n".join(parts).strip()


async def parse_careered() -> list[RawVacancy]:
    vacancies: list[RawVacancy] = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=20) as client:
        for page in range(1, MAX_PAGES + 1):
            try:
                resp = await client.get(API_URL, params={"page": page})
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"[careered] Ошибка на странице {page}: {e}")
                break

            entries = data.get("entries", [])
            if not entries:
                break

            for entry in entries:
                tag_name = entry.get("tag", {}).get("name", "")

                # Фильтр по релевантным категориям
                if tag_name not in RELEVANT_TAGS:
                    continue

                entry_id  = entry.get("id", "")
                features  = entry.get("features", [])
                full_text = _build_full_text(features, tag_name)
                title     = _get_feature(features, "name")
                url       = f"{BASE_URL}/job/{entry_id}"

                if not full_text:
                    continue

                vacancies.append(RawVacancy(
                    source="careered",
                    channel="careered.io",
                    source_id=entry_id,
                    full_text=full_text,
                    url=url,
                    contacts=[],
                    posted_at=datetime.now(timezone.utc),
                ))

            # Проверяем нужно ли листать дальше
            total  = data.get("total", 0)
            limit  = data.get("limit", 20)
            offset = data.get("offset", 0)
            if offset + limit >= total:
                break

            await asyncio.sleep(0.5)  # не спамим API

    print(f"[careered] Найдено релевантных: {len(vacancies)}")
    return vacancies
