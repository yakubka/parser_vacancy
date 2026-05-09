"""
Главный скрипт агрегатора вакансий.

Запуск:
  python main.py           — разовый запуск
  python main.py --setup   — сохранить профиль в БД
  python main.py --test    — тест без отправки в TG
"""

import asyncio
import argparse
import json
from pathlib import Path

from processing.embeddings import embed_text, embed_batch, prepare_vacancy_text
from processing.deduplication import check_duplicate, prepare_for_db
from processing.scorer import score_vacancy, explain_score
from llm.cover_letter import generate_cover_letter
from bot.notifier import (
    send_vacancy, send_unsorted_vacancy,
    send_digest_header, send_unsorted_header, send_no_vacancies
)
from database import (
    get_user_profile, upsert_user_profile,
    insert_vacancy, get_top_unsent, get_unsorted_unsent, mark_sent
)
import config


def load_local_profile() -> dict:
    profile_path = Path(__file__).parent / "user_profile.json"
    with open(profile_path, encoding="utf-8") as f:
        return json.load(f)


def is_remote_vacancy(text: str) -> bool:
    """Проверяем упоминание удалённой работы в тексте вакансии."""
    text_lower = text.lower()
    return any(signal in text_lower for signal in config.REMOTE_SIGNALS)


async def setup_profile():
    profile = load_local_profile()
    print("[Setup] Генерируем эмбеддинг профиля...")
    embedding = embed_text(profile["profile_text"])
    upsert_user_profile(profile["profile_text"], embedding)
    print("[Setup] Профиль сохранён в БД ✓")


async def run(test_mode: bool = False):
    print("=" * 50)
    print("🚀 Job Aggregator — Yokub Nurullaev")
    print("=" * 50)

    profile_db = get_user_profile()
    if not profile_db:
        print("[!] Профиль не найден. Запусти: python main.py --setup")
        return

    profile_local   = load_local_profile()
    from processing.embeddings import parse_embedding
    profile_embedding = parse_embedding(profile_db["embedding"])

    # ── 1. Парсинг ────────────────────────────────────────────────────────────
    all_raw = []

    # ── Health-check каналов (раз в сутки) ───────────────────────────────────
    from parsers.telegram_parser import (
        parse_channels, disconnect,
        check_channels_health, format_health_report, should_run_health_check,
    )
    if should_run_health_check():
        print("\n🔍 Проверяем здоровье каналов...")
        health_report = await check_channels_health()
        report_text   = format_health_report(health_report)
        if not test_mode:
            from bot.notifier import _send
            await _send(config.TG_YOUR_CHAT_ID, report_text)
        else:
            print(report_text)

    print("\n📡 Парсим Telegram каналы...")
    tg = await parse_channels()
    all_raw.extend(tg)
    print(f"   {len(tg)} постов")

    print("📡 Парсим GetMatch...")
    from parsers.getmatch_parser import parse_getmatch_rss
    gm = await parse_getmatch_rss()
    all_raw.extend(gm)
    print(f"   {len(gm)} вакансий")

    print("📡 Парсим HH.ru...")
    from parsers.hh_parser import parse_hh
    hh = await parse_hh(text="python backend fastapi", only_remote=True)
    all_raw.extend(hh)
    print(f"   {len(hh)} вакансий")

    print("📡 Парсим GeekJob...")
    from parsers.geekjob_parser import parse_geekjob
    gj = await parse_geekjob(["python", "fastapi", "backend"])
    all_raw.extend(gj)
    print(f"   {len(gj)} вакансий")

    print("📡 Парсим Huntee...")
    from parsers.huntee_parser import parse_huntee
    ht = await parse_huntee()
    all_raw.extend(ht)
    print(f"   {len(ht)} вакансий")

    print("📡 Парсим фриланс-сайты (Scrapling)...")
    from parsers.web_parser import WebParser
    web = await WebParser().parse_all()
    all_raw.extend(web)
    print(f"   {len(web)} проектов")

    print(f"\n📊 Всего сырых: {len(all_raw)}")

    # ── 2. Обработка ──────────────────────────────────────────────────────────
    saved_matched  = 0   # remote + хороший скор
    saved_unsorted = 0   # remote не указан — сам смотришь
    skipped_dups   = 0
    skipped_score  = 0
    skipped_stop   = 0

    texts      = [prepare_vacancy_text(v.full_text) for v in all_raw]
    embeddings = embed_batch(texts) if texts else []

    print("\n🔄 Обработка вакансий...")

    for vacancy, embedding in zip(all_raw, embeddings):
        # Стоп-слова — быстрый скип
        text_lower = vacancy.full_text.lower()
        if any(sw in text_lower for sw in config.STOP_WORDS):
            skipped_stop += 1
            continue

        # Дедупликация
        is_dup, reason = check_duplicate(vacancy, embedding)
        if is_dup:
            skipped_dups += 1
            continue

        # ── Remote-детект ─────────────────────────────────────────────────────
        remote = is_remote_vacancy(vacancy.full_text)

        if not remote:
            # Не упомянут remote → кидаем в unsorted без скоринга
            db_data = prepare_for_db(vacancy, embedding, score=0.0)
            db_data["category"]  = "unsorted"
            db_data["is_remote"] = False
            insert_vacancy(db_data)
            saved_unsorted += 1
            continue

        # ── Remote есть → полный скоринг ──────────────────────────────────────
        score_details = explain_score(
            vacancy_embedding=embedding,
            profile_embedding=profile_embedding,
            vacancy_text=vacancy.full_text,
            posted_at=vacancy.posted_at,
        )

        if score_details["total"] < config.MIN_SCORE_TO_SEND:
            skipped_score += 1
            continue

        db_data = prepare_for_db(vacancy, embedding, score_details["total"])
        db_data["category"]  = "matched"
        db_data["is_remote"] = True
        insert_vacancy(db_data)
        saved_matched += 1

    print(f"   ✅ Remote + подходящие:  {saved_matched}")
    print(f"   📦 Unsorted (без remote): {saved_unsorted}")
    print(f"   ✗  Дубли:                {skipped_dups}")
    print(f"   ✗  Низкий скор:          {skipped_score}")
    print(f"   ✗  Стоп-слова:           {skipped_stop}")

    # ── 3. Отправка matched вакансий ──────────────────────────────────────────
    top_matched = get_top_unsent(config.TOP_N_PER_RUN)

    if top_matched:
        print(f"\n📤 Отправляем {len(top_matched)} подходящих вакансий...")
        if not test_mode:
            await send_digest_header(len(top_matched))

        for vac in top_matched:
            score_details = _build_score_details(vac)
            cover = await generate_cover_letter(
                vacancy_text=vac["full_text"],
                profile=profile_local,
                score_details=score_details,
            )
            # Кэшируем сопроводительное в БД (для Mini App)
            from database import get_db
            get_db().table("vacancies").update({"cover_letter": cover}).eq("id", vac["id"]).execute()

            if test_mode:
                _print_vacancy(vac, cover, score_details)
            else:
                await send_vacancy(vac, cover, score_details)
                mark_sent(vac["id"])

            await asyncio.sleep(1)
    else:
        print("\n📭 Нет новых matched вакансий")
        if not test_mode:
            await send_no_vacancies()

    # ── 4. Отправка unsorted пачкой ───────────────────────────────────────────
    unsorted = get_unsorted_unsent(limit=10)

    if unsorted:
        print(f"\n📦 Отправляем {len(unsorted)} unsorted вакансий...")
        if not test_mode:
            await send_unsorted_header(len(unsorted))

        for vac in unsorted:
            if test_mode:
                print(f"\n[UNSORTED] {vac.get('title','?')} | {vac.get('url','')}")
            else:
                await send_unsorted_vacancy(vac)
                mark_sent(vac["id"])
            await asyncio.sleep(0.5)

    await disconnect()
    print("\n✅ Готово!")


# ─── Хелперы ──────────────────────────────────────────────────────────────────

def _parse_embedding(embedding):
    """Конвертируем эмбеддинг из любого формата в list[float]."""
    if isinstance(embedding, list):
        return [float(x) for x in embedding]
    if isinstance(embedding, str):
        import json
        cleaned = embedding.strip()
        if cleaned.startswith('['):
            return [float(x) for x in json.loads(cleaned)]
        # Postgres vector format: (0.1,0.2,...) или 0.1,0.2,...
        cleaned = cleaned.strip('()')
        return [float(x) for x in cleaned.split(',')]
    return list(embedding)


def _build_score_details(vac: dict) -> dict:
    text_lower = vac.get("full_text", "").lower()
    return {
        "total": vac.get("similarity_score", 0),
        "matched_stack": [t for t in config.USER_TECH_STACK if t in text_lower],
    }


def _print_vacancy(vac: dict, cover: str, score_details: dict):
    print("\n" + "─" * 50)
    print(f"Скор:    {int(score_details['total']*100)}%")
    print(f"Стек:    {', '.join(score_details['matched_stack'])}")
    print(f"Контакт: {vac.get('contacts', [])}")
    print(f"URL:     {vac.get('url', '')}")
    print(f"\nСопроводительное:\n{cover}")


# ─── Entrypoint ───────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--test",  action="store_true")
    args = parser.parse_args()

    if args.setup:
        await setup_profile()
    else:
        await run(test_mode=args.test)


if __name__ == "__main__":
    asyncio.run(main())
