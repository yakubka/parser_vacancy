import re
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional, Tuple
from telethon import TelegramClient
from telethon.sessions import StringSession
import config
from database import get_active_channels, update_channel_last_msg, update_channel_health

_client = None


async def get_client():
    global _client
    if _client is None:
        # На Railway используем StringSession из переменной окружения,
        # локально — файл tg_session.session
        if config.TG_SESSION_STRING:
            session = StringSession(config.TG_SESSION_STRING)
        else:
            session = "tg_session"
        _client = TelegramClient(session, config.TG_API_ID, config.TG_API_HASH)
    if not _client.is_connected():
        if config.TG_SESSION_STRING:
            await _client.connect()  # не просит код — сессия уже авторизована
        else:
            await _client.start(phone=config.TG_PHONE)
    return _client


@dataclass
class RawVacancy:
    source: str = "telegram"
    channel: str = ""
    source_id: str = ""
    full_text: str = ""
    url: str = ""
    contacts: list = field(default_factory=list)
    posted_at: datetime = None


def extract_contacts(text: str, msg) -> list:
    contacts = set()
    for m in re.finditer(r'@([A-Za-z0-9_]{5,32})', text):
        contacts.add("@" + m.group(1).lower())
    for m in re.finditer(r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', text):
        phone = re.sub(r'[\s\-()]', '', m.group())
        if phone.startswith('8'):
            phone = '+7' + phone[1:]
        contacts.add(phone)
    for m in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text):
        contacts.add(m.group().lower())
    return list(contacts)


def extract_title(text: str) -> str:
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in lines[:5]:
        if len(line) > 10 and not line.startswith('http'):
            return line[:200]
    return lines[0][:200] if lines else "Вакансия"


CV_SIGNALS = [
    '#cv', '#резюме', '#resume', '#opentowork', '#ищуработу',
    '#open_to_work', 'ищу работу', 'ищу проект', 'рассмотрю предложения',
    'открыт к предложениям', 'в поиске работы', 'looking for job',
    'available for work', '#нанимайте', 'портфолио:', 'github:', 'hh.ru/resume',
]

def is_vacancy_post(text: str) -> bool:
    text_lower = text.lower()

    # Фильтруем резюме и CV-посты
    if any(s in text_lower for s in CV_SIGNALS):
        return False

    signals = ['вакансия', 'ищем', 'нужен', 'требуется', 'hiring', 'vacancy',
               'job', 'developer', 'разработчик', 'engineer', 'специалист',
               'зарплата', 'зп', 'salary', 'опыт от', 'experience']
    if not any(s in text_lower for s in signals):
        return False
    if any(sw in text_lower for sw in config.STOP_WORDS):
        return False
    return True


ALIVE_THRESHOLD_DAYS  = 30   # канал мёртв если молчит дольше
SLEEP_THRESHOLD_DAYS  = 7    # канал "спит" если молчит дольше


# ─── Health-check каналов ─────────────────────────────────────────────────────

async def check_channel_alive(username: str, days_threshold: int = ALIVE_THRESHOLD_DAYS) -> Tuple[bool, Optional[datetime]]:
    """
    Проверяет последнее сообщение в канале.
    Возвращает (is_alive, last_post_at).
    """
    client = await get_client()
    try:
        async for message in client.iter_messages(username, limit=1):
            if message.date:
                last_post = message.date.replace(tzinfo=timezone.utc)
                age_days  = (datetime.now(timezone.utc) - last_post).days
                return age_days <= days_threshold, last_post
    except Exception:
        pass
    return False, None


async def check_channels_health() -> dict:
    """
    Проходит по всем active=True каналам, проверяет живость,
    обновляет is_alive / last_post_at / last_checked_at в Supabase.
    Возвращает словарь {'alive': [...], 'sleeping': [...], 'dead': [...]}.
    """
    channels = get_active_channels()
    now      = datetime.now(timezone.utc)

    report = {"alive": [], "sleeping": [], "dead": []}

    for ch in channels:
        username  = ch["username"]
        is_alive, last_post = await check_channel_alive(username)

        age_days = None
        if last_post:
            age_days = (now - last_post).days

        # Определяем категорию для отчёта
        if not is_alive or last_post is None:
            report["dead"].append((username, None))
        elif age_days is not None and age_days > SLEEP_THRESHOLD_DAYS:
            report["sleeping"].append((username, age_days))
        else:
            report["alive"].append((username, age_days or 0))

        # Обновляем Supabase
        update_channel_health(
            username=username,
            is_alive=is_alive,
            last_post_at=last_post,
            last_checked_at=now,
            # Мёртвые → active=False, чтобы не парсить каждый раз
            set_inactive=not is_alive,
        )

    total = len(channels)
    print(
        f"[Health] ✅ {len(report['alive'])}  "
        f"⚠️ {len(report['sleeping'])}  "
        f"❌ {len(report['dead'])}  "
        f"/ {total} каналов"
    )
    return report


def format_health_report(report: dict) -> str:
    """Формирует Telegram-сообщение с health-отчётом."""
    lines = ["📡 <b>Отчёт по каналам</b>", ""]

    if report["alive"]:
        lines.append("✅ <b>Живые</b>")
        for username, days in sorted(report["alive"], key=lambda x: x[1]):
            lines.append(f"  @{username} — {days}д назад")

    if report["sleeping"]:
        lines.append("")
        lines.append("⚠️ <b>Спящие (7–30 дней)</b>")
        for username, days in sorted(report["sleeping"], key=lambda x: x[1]):
            lines.append(f"  @{username} — {days}д назад")

    if report["dead"]:
        lines.append("")
        lines.append("❌ <b>Мёртвые / недоступные (→ отключены)</b>")
        for username, _ in report["dead"]:
            lines.append(f"  @{username}")

    lines.append("")
    lines.append(f"<i>Проверено: {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC</i>")
    return "\n".join(lines)


def should_run_health_check() -> bool:
    """
    Возвращает True если health-check не запускался сегодня.
    Проверяем через самый свежий last_checked_at из Supabase.
    """
    from database import get_last_health_check
    last = get_last_health_check()
    if last is None:
        return True
    now = datetime.now(timezone.utc)
    # Нормализуем last к timezone-aware если нужно
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last) >= timedelta(hours=23)


# ─── Парсинг вакансий ─────────────────────────────────────────────────────────

async def parse_channels() -> list:
    client = await get_client()
    channels = get_active_channels()
    all_vacancies = []

    for channel in channels:
        username = channel["username"]
        last_id = channel.get("last_msg_id", 0)
        new_last_id = last_id
        print(f"[TG] Парсим @{username}")
        try:
            entity = await client.get_entity(username)
            messages = await client.get_messages(entity, min_id=last_id, limit=100)
            for msg in messages:
                if not msg.text or len(msg.text) < 50:
                    continue
                if not is_vacancy_post(msg.text):
                    continue
                contacts = extract_contacts(msg.text, msg)
                all_vacancies.append(RawVacancy(
                    channel=username,
                    source_id=str(msg.id),
                    full_text=msg.text,
                    url=f"https://t.me/{username}/{msg.id}",
                    contacts=contacts,
                    posted_at=msg.date.replace(tzinfo=timezone.utc) if msg.date else datetime.now(timezone.utc),
                ))
                if msg.id > new_last_id:
                    new_last_id = msg.id
        except Exception as e:
            print(f"[TG] Ошибка @{username}: {e}")

        if new_last_id > last_id:
            update_channel_last_msg(username, new_last_id)

    return all_vacancies


async def disconnect():
    global _client
    if _client and _client.is_connected():
        await _client.disconnect()
