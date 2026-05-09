"""
Отправка вакансий через Telegram Bot API.

Две категории:
  matched  — remote + хороший скор → красивое сообщение с сопроводительным
  unsorted — remote не упомянут → компактная строчка, сам смотришь
"""

import httpx
import json

import config

TG_API = f"https://api.telegram.org/bot{config.TG_BOT_TOKEN}"


def _esc(text: str) -> str:
    """Экранируем HTML-спецсимволы чтобы Telegram не сломал форматирование."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ─── Matched вакансии ─────────────────────────────────────────────────────────

async def send_digest_header(count: int):
    text = (
        f"🎯 <b>Подборка: {count} подходящих вакансий</b>\n"
        f"Remote · Python/Backend · по твоему профилю\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    await _send(config.TG_YOUR_CHAT_ID, text)


async def send_vacancy(vacancy: dict, cover_letter: str, score_details: dict):
    """Полноформатная вакансия с сопроводительным."""
    text  = _format_matched(vacancy, cover_letter, score_details)
    kb    = _keyboard(vacancy)
    await _send(config.TG_YOUR_CHAT_ID, text, kb)


# ─── Unsorted вакансии ────────────────────────────────────────────────────────

async def send_unsorted_header(count: int):
    text = (
        f"📦 <b>Unsorted: {count} вакансий без упоминания remote</b>\n"
        f"Может офис, может не указали — сам смотришь\n"
        f"─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─"
    )
    await _send(config.TG_YOUR_CHAT_ID, text)


async def send_unsorted_vacancy(vacancy: dict):
    """Компактная строчка для unsorted — без лишнего."""
    source = f"@{vacancy['channel']}" if vacancy.get("channel") else vacancy.get("source", "?")
    title  = _esc(vacancy.get("title", "Вакансия")[:80])
    url    = vacancy.get("url", "")

    contacts = vacancy.get("contacts", [])
    contact_str = _esc("  ".join(contacts[:2]) if contacts else "—")

    text = f"📌 {title}\n<code>{contact_str}</code> · {_esc(source)}"

    kb = {}
    if url:
        kb = {"inline_keyboard": [[{"text": "Открыть", "url": url}]]}

    await _send(config.TG_YOUR_CHAT_ID, text, kb)


# ─── Прочее ───────────────────────────────────────────────────────────────────

async def send_no_vacancies():
    await _send(
        config.TG_YOUR_CHAT_ID,
        "😴 Новых подходящих remote вакансий сегодня нет."
    )


# ─── Форматирование ───────────────────────────────────────────────────────────

def _format_matched(vacancy: dict, cover_letter: str, score_details: dict) -> str:
    score_pct = int(score_details.get("total", 0) * 100)
    matched   = score_details.get("matched_stack", [])

    source      = _esc(f"@{vacancy['channel']}" if vacancy.get("channel") else vacancy.get("source", ""))
    contacts    = vacancy.get("contacts", [])
    contacts_str = _esc("  ".join(contacts[:3]) if contacts else "не указан")
    stack_str    = "  ".join(f"<code>{_esc(t)}</code>" for t in matched[:6]) if matched else "—"

    preview = _esc(_truncate(vacancy.get("full_text", ""), 500))
    cover   = _esc(cover_letter)

    return "\n".join([
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"🎯 <b>{score_pct}% совпадение</b>  ·  🌐 Remote  ·  {source}",
        f"",
        f"{preview}",
        f"",
        f"🛠 {stack_str}",
        f"📞 <code>{contacts_str}</code>",
        f"",
        f"✉️ <b>Сопроводительное</b> <i>(ctrl+c)</i>",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"<i>{cover}</i>",
    ])


def _keyboard(vacancy: dict) -> dict:
    url = vacancy.get("url", "")
    if not url:
        return {}
    return {"inline_keyboard": [[{"text": "🔗 Открыть вакансию", "url": url}]]}


def _truncate(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[:n].rsplit(' ', 1)[0] + "…"


# ─── HTTP ─────────────────────────────────────────────────────────────────────

async def _send(chat_id: int, text: str, reply_markup: dict = None):
    payload = {
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(f"{TG_API}/sendMessage", json=payload)
            if not resp.is_success:
                print(f"[Bot] Ошибка: {resp.text[:200]}")
        except Exception as e:
            print(f"[Bot] {e}")
