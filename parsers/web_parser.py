"""
Парсер сайтов фриланс-бирж через httpx + BeautifulSoup4.
(Scrapling заменён — конфликт pyobjc на macOS с новым Clang)

Источники:
  - freten.ru/projects       — категория разработка
  - workzilla.com/tasks      — категория программирование
  - weblancer.net/projects   — Python/backend
  - workspace.ru/tenders     — разработка

Возвращает list[RawVacancy] — совместимо с pipeline main.py.
"""

from __future__ import annotations

import re
import asyncio
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from parsers.telegram_parser import RawVacancy
from database import get_db

import logging
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


# ─── Хелперы ──────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _fetch(client: httpx.AsyncClient, url: str) -> BeautifulSoup | None:
    try:
        resp = await client.get(url, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        log.warning(f"[WebParser] Не удалось получить {url}: {e}")
        return None


# ─── Основной класс ───────────────────────────────────────────────────────────

class WebParser:

    SOURCE = "web"

    # ── freten.ru ─────────────────────────────────────────────────────────────

    async def parse_freten(self, client: httpx.AsyncClient) -> list[RawVacancy]:
        url  = "https://freten.ru/projects/?category=development"
        soup = await _fetch(client, url)
        if not soup:
            return []

        vacancies = []
        for card in soup.select(".project-item, .project-card, article.project, .project"):
            title_el  = card.select_one("h2, h3, .project-title, .title")
            desc_el   = card.select_one(".project-description, .description, p")
            link_el   = card.select_one("a[href]")
            budget_el = card.select_one(".budget, .price, .cost")

            title  = _clean(title_el.get_text()) if title_el  else ""
            desc   = _clean(desc_el.get_text())  if desc_el   else ""
            href   = link_el["href"]             if link_el   else ""
            budget = _clean(budget_el.get_text()) if budget_el else ""

            if not href.startswith("http"):
                href = "https://freten.ru" + href
            if not title and not desc:
                continue

            full_text = f"{title}\n\n{desc}"
            if budget:
                full_text += f"\n\nБюджет: {budget}"

            vacancies.append(RawVacancy(
                source=self.SOURCE, channel="freten.ru",
                source_id=href, full_text=full_text,
                url=href, contacts=[], posted_at=_now(),
            ))

        log.info(f"[freten.ru] {len(vacancies)} проектов")
        return vacancies

    # ── workzilla.com ─────────────────────────────────────────────────────────

    async def parse_workzilla(self, client: httpx.AsyncClient) -> list[RawVacancy]:
        url  = "https://workzilla.com/tasks/?category=programming"
        soup = await _fetch(client, url)
        if not soup:
            return []

        vacancies = []
        for card in soup.select(".task-item, .task-card, .task, li.task"):
            title_el = card.select_one("h2, h3, .task-title, .title, a.name")
            desc_el  = card.select_one(".task-description, .description, .text, p")
            link_el  = card.select_one("a[href*='/task/'], a[href*='/tasks/']")
            price_el = card.select_one(".price, .budget, .cost, .reward")

            title = _clean(title_el.get_text()) if title_el else ""
            desc  = _clean(desc_el.get_text())  if desc_el  else ""
            href  = link_el["href"]             if link_el  else ""
            price = _clean(price_el.get_text()) if price_el else ""

            if not href.startswith("http"):
                href = "https://workzilla.com" + href
            if not title and not desc:
                continue

            full_text = f"{title}\n\n{desc}"
            if price:
                full_text += f"\n\nБюджет: {price}"

            vacancies.append(RawVacancy(
                source=self.SOURCE, channel="workzilla.com",
                source_id=href, full_text=full_text,
                url=href, contacts=[], posted_at=_now(),
            ))

        log.info(f"[workzilla] {len(vacancies)} проектов")
        return vacancies

    # ── weblancer.net ─────────────────────────────────────────────────────────

    async def parse_weblancer(self, client: httpx.AsyncClient) -> list[RawVacancy]:
        url  = "https://weblancer.net/projects/?cat=5"
        soup = await _fetch(client, url)
        if not soup:
            return []

        vacancies = []
        for card in soup.select(".project, .item-list .item, article"):
            title_el = card.select_one("h2 a, h3 a, .title a, a.project-title")
            desc_el  = card.select_one(".description, .text, p.desc")
            price_el = card.select_one(".price, .budget")

            title = _clean(title_el.get_text()) if title_el else ""
            desc  = _clean(desc_el.get_text())  if desc_el  else ""
            href  = title_el["href"]            if title_el else ""
            price = _clean(price_el.get_text()) if price_el else ""

            if not href.startswith("http"):
                href = "https://weblancer.net" + href
            if not title and not desc:
                continue

            # Фильтр: только python/backend
            combined = (title + " " + desc).lower()
            if not any(kw in combined for kw in [
                "python", "fastapi", "django", "flask",
                "backend", "api", "бэкенд", "postgresql", "asyncio",
            ]):
                continue

            full_text = f"{title}\n\n{desc}"
            if price:
                full_text += f"\n\nБюджет: {price}"

            vacancies.append(RawVacancy(
                source=self.SOURCE, channel="weblancer.net",
                source_id=href, full_text=full_text,
                url=href, contacts=[], posted_at=_now(),
            ))

        log.info(f"[weblancer] {len(vacancies)} проектов")
        return vacancies

    # ── workspace.ru ──────────────────────────────────────────────────────────

    async def parse_workspace(self, client: httpx.AsyncClient) -> list[RawVacancy]:
        url  = "https://workspace.ru/tenders/works/?category=development"
        soup = await _fetch(client, url)
        if not soup:
            return []

        vacancies = []
        for card in soup.select(".tender-item, .tender-card, .tenders__item, article"):
            title_el  = card.select_one("h2, h3, .tender-title, .title, a.name")
            desc_el   = card.select_one(".description, .tender-description, .text, p")
            link_el   = card.select_one("a[href*='/tenders/'], a[href*='/tender/']")
            budget_el = card.select_one(".budget, .price, .cost")

            title  = _clean(title_el.get_text()) if title_el  else ""
            desc   = _clean(desc_el.get_text())  if desc_el   else ""
            href   = link_el["href"]             if link_el   else ""
            budget = _clean(budget_el.get_text()) if budget_el else ""

            if not href.startswith("http"):
                href = "https://workspace.ru" + href
            if not title and not desc:
                continue

            full_text = f"{title}\n\n{desc}"
            if budget:
                full_text += f"\n\nБюджет: {budget}"

            vacancies.append(RawVacancy(
                source=self.SOURCE, channel="workspace.ru",
                source_id=href, full_text=full_text,
                url=href, contacts=[], posted_at=_now(),
            ))

        log.info(f"[workspace.ru] {len(vacancies)} проектов")
        return vacancies

    # ── Все источники параллельно ─────────────────────────────────────────────

    async def parse_all(self) -> list[RawVacancy]:
        async with httpx.AsyncClient(headers=HEADERS) as client:
            results = await asyncio.gather(
                self.parse_freten(client),
                self.parse_workzilla(client),
                self.parse_weblancer(client),
                self.parse_workspace(client),
                return_exceptions=True,
            )

        all_vacancies: list[RawVacancy] = []
        for r in results:
            if isinstance(r, Exception):
                log.warning(f"[WebParser] Источник упал: {r}")
            else:
                all_vacancies.extend(r)

        # Обновляем last_scraped_at
        try:
            get_db().table("web_sources") \
                .update({"last_scraped_at": _now().isoformat()}) \
                .eq("active", True) \
                .execute()
        except Exception as e:
            log.warning(f"[WebParser] last_scraped_at не обновлён: {e}")

        return all_vacancies
