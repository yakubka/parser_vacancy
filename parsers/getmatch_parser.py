import httpx
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from parsers.telegram_parser import RawVacancy


async def parse_getmatch_rss() -> list:
    vacancies = []
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get("https://getmatch.ru/rss/vacancies")
            root = ET.fromstring(resp.text)
            for item in root.findall(".//item"):
                title = item.findtext("title", "")
                desc  = item.findtext("description", "")
                link  = item.findtext("link", "")
                vacancies.append(RawVacancy(
                    source="getmatch", source_id=link,
                    full_text=f"{title}\n{desc}", url=link,
                    contacts=[], posted_at=datetime.now(timezone.utc),
                ))
        except Exception as e:
            print(f"[GetMatch] Ошибка: {e}")
    print(f"[GetMatch] Найдено: {len(vacancies)}")
    return vacancies
