import httpx
import re
from datetime import datetime, timezone
from parsers.telegram_parser import RawVacancy

HH_API = "https://api.hh.ru/vacancies"
HEADERS = {"User-Agent": "JobAggregator/1.0 (personal)"}


async def parse_hh(text="python backend fastapi", area=113, only_remote=True, per_page=30) -> list:
    params = {"text": text, "area": area, "per_page": per_page, "order_by": "publication_time"}
    if only_remote:
        params["schedule"] = "remote"
    vacancies = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        try:
            resp = await client.get(HH_API, params=params)
            items = resp.json().get("items", [])
            print(f"[HH] Найдено {len(items)}")
            for item in items[:20]:
                vac_id = item.get("id")
                try:
                    detail = (await client.get(f"{HH_API}/{vac_id}")).json()
                except Exception:
                    detail = item
                full_text = _build_text(detail)
                contacts = _get_contacts(detail)
                url = detail.get("alternate_url", f"https://hh.ru/vacancy/{vac_id}")
                try:
                    posted_at = datetime.fromisoformat(detail.get("published_at", "").replace("Z", "+00:00"))
                except Exception:
                    posted_at = datetime.now(timezone.utc)
                vacancies.append(RawVacancy(source="hh", source_id=str(vac_id),
                                            full_text=full_text, url=url,
                                            contacts=contacts, posted_at=posted_at))
        except Exception as e:
            print(f"[HH] Ошибка: {e}")
    return vacancies


def _build_text(d):
    parts = [d.get("name", "")]
    emp = d.get("employer", {}).get("name", "")
    if emp: parts.append(f"Компания: {emp}")
    sal = d.get("salary")
    if sal: parts.append(f"Зарплата: {sal.get('from','?')}-{sal.get('to','?')} {sal.get('currency','RUR')}")
    desc = d.get("description", "")
    if desc: parts.append(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', desc))[:2000])
    skills = d.get("key_skills", [])
    if skills: parts.append("Навыки: " + ", ".join(s["name"] for s in skills))
    sched = d.get("schedule", {}).get("name", "")
    if sched: parts.append(f"График: {sched}")
    return "\n".join(filter(None, parts))


def _get_contacts(d):
    contacts = []
    c = d.get("contacts")
    if not c: return contacts
    for p in c.get("phones", []):
        if p.get("number"): contacts.append(p["number"])
    if c.get("email"): contacts.append(c["email"].lower())
    return contacts
