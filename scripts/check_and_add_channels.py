"""
Проверяет список новых каналов через Telethon и добавляет живые в tg_channels.
Запуск: python scripts/check_and_add_channels.py

Канал считается живым если последний пост был не позже 30 дней назад.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    ChannelPrivateError, UsernameNotOccupiedError,
    UsernameInvalidError, FloodWaitError
)
import config
from database import get_db

DEAD_THRESHOLD_DAYS = 30

NEW_CHANNELS = [
    "getitjob", "workinai", "remote_inflow", "junior_jobs",
    "well_paid_job", "freelance_gigs", "geekjob_ru", "python_geekjob",
    "it_jobs_world", "digital_hr", "vacancy_it", "startupjobs_ru",
    "pythondevjobs", "aiml_jobs", "fastapi_jobs", "tgram_jobs",
    "it_remote_work", "rabota_it", "dev_jobs_ru", "python_freelance",
    "backend_freelance", "it_freelance_ru", "hired_it", "jobs_for_devs",
    "coderabbit_jobs", "techjobs_ru", "remotejobs_cis", "devhunt_jobs",
    "freelance_tribe", "remotework", "itfreelance", "prog_jobs",
    "hitech_jobs", "developer_jobs", "remote_developers", "coders_jobs",
    "programmer_remote", "remote_tech_jobs", "employers_and_freelancers",
    "it_jobs", "freelancehunt_jobs", "freelance_today", "job4you",
    "digital_jobs", "remotepros", "remote_it_jobs", "startup_russia",
    "vacancy_python", "aiogram_jobs", "fastapi_dev", "python_community_jobs",
    "django_jobs_ru", "ml_jobs_ru", "data_jobs_ru", "devops_jobs_ru",
    "vue_jobs", "nuxt_jobs", "FreeLance", "Django_jobs", "ethereum_jobs",
    "web_freelance", "get_job", "theyseeku", "tgram_it_jobs",
    "agile_jobs", "devaller", "rabota_it_remote", "seti_it_jobs",
    "junior_staj_it", "python_ru_jobs", "asyncio_jobs",
    "scrapy_jobs", "selenium_jobs", "Jobs_IT", "remowork_ru",
    "remoteit", "fordev", "devops_jobs", "fordevops",
    "getitrussia", "moikrug", "tproger_official", "Data_Science_Jobs",
    "django_jobs", "JavaScript_Jobs", "DevOps_Jobs_chat", "products_jobs",
    "mobile_dev_jobs", "remocate_devs", "newhr_vacancy", "ClubcomJob",
    "js_jobs", "angular_jobs", "html_css_js_jobs", "freelancers_remote",
    "it_job_board", "python_analytics_jobs", "python_beginners_jobs",
    "data_engineers_jobs", "ai_jobs_ru", "nlp_jobs_ru", "qa_jobs_ru",
    "startup_jobs_ru", "fintech_jobs_ru", "crypto_dev_jobs",
    "web3_dev_jobs", "backend_dev_chat", "fullstack_chat_jobs",
    "it_freelance_board", "jobs_and_projects", "remote_cis_jobs",
    "it_jobs_world_ru", "vacancy_aggregator", "dev_freelance_chat",
    "python_vacancy", "fastapi_jobs_ru", "docker_jobs", "kubernetes_jobs",
    "naуdalyonke",
]


async def check_channel(client, username: str) -> Tuple[bool, str, Optional[datetime]]:
    """
    Возвращает (is_alive, title, last_post_at)
    """
    try:
        entity = await client.get_entity(username)
        title  = getattr(entity, 'title', username)

        async for msg in client.iter_messages(username, limit=1):
            if msg.date:
                last_post = msg.date.replace(tzinfo=timezone.utc)
                age_days  = (datetime.now(timezone.utc) - last_post).days
                alive     = age_days <= DEAD_THRESHOLD_DAYS
                return alive, title, last_post

        return False, title, None
    except (ChannelPrivateError, UsernameNotOccupiedError, UsernameInvalidError):
        return False, username, None
    except FloodWaitError as e:
        print(f"  ⏳ FloodWait {e.seconds}s — ждём...")
        await asyncio.sleep(e.seconds + 2)
        return False, username, None
    except Exception as e:
        return False, username, None


async def main():
    if config.TG_SESSION_STRING:
        session = StringSession(config.TG_SESSION_STRING)
    else:
        session = "tg_session"

    client = TelegramClient(session, config.TG_API_ID, config.TG_API_HASH)

    if config.TG_SESSION_STRING:
        await client.connect()
    else:
        await client.start(phone=config.TG_PHONE)

    db = get_db()

    # Получаем уже существующие каналы
    existing = db.table("tg_channels").select("username").execute()
    existing_set = {r["username"].lower() for r in existing.data}

    results = {"alive": [], "dead": [], "skip": []}

    print(f"Проверяем {len(NEW_CHANNELS)} каналов...\n")

    for i, username in enumerate(NEW_CHANNELS, 1):
        clean = username.lstrip("@").strip()

        if clean.lower() in existing_set:
            results["skip"].append(clean)
            print(f"[{i:3}/{len(NEW_CHANNELS)}] ⏭  @{clean} — уже в БД")
            continue

        is_alive, title, last_post = await check_channel(client, clean)

        age_str = ""
        if last_post:
            age_days = (datetime.now(timezone.utc) - last_post).days
            age_str  = f" ({age_days}д назад)"

        if is_alive:
            # Добавляем в БД
            try:
                db.table("tg_channels").insert({
                    "username":     clean,
                    "title":        title,
                    "active":       True,
                    "is_alive":     True,
                    "last_post_at": last_post.isoformat() if last_post else None,
                    "last_checked_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
                results["alive"].append(clean)
                print(f"[{i:3}/{len(NEW_CHANNELS)}] ✅ @{clean}{age_str} — добавлен")
            except Exception as e:
                print(f"[{i:3}/{len(NEW_CHANNELS)}] ⚠️  @{clean} — ошибка вставки: {e}")
        else:
            results["dead"].append(clean)
            print(f"[{i:3}/{len(NEW_CHANNELS)}] ❌ @{clean}{age_str} — мёртвый/недоступен")

        await asyncio.sleep(0.8)  # антифлуд

    await client.disconnect()

    print("\n" + "="*50)
    print(f"✅ Добавлено живых:      {len(results['alive'])}")
    print(f"❌ Мёртвых/недоступных: {len(results['dead'])}")
    print(f"⏭  Уже были в БД:       {len(results['skip'])}")
    print("="*50)

    if results["alive"]:
        print("\nДобавленные каналы:")
        for ch in results["alive"]:
            print(f"  @{ch}")


if __name__ == "__main__":
    asyncio.run(main())
