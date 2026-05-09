from __future__ import annotations
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY
import hashlib

_client = None


def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ─── Вакансии ─────────────────────────────────────────────────────────────────

def vacancy_exists_by_hash(text_hash: str) -> bool:
    result = get_db().table("vacancies") \
        .select("id").eq("text_hash", text_hash).limit(1).execute()
    return len(result.data) > 0


def find_duplicates_by_contact(contact_hash: str, title_embedding: list[float]) -> list[dict]:
    result = get_db().table("vacancies") \
        .select("id, title, embedding") \
        .eq("contact_hash", contact_hash) \
        .eq("is_duplicate", False) \
        .execute()
    return result.data


def find_similar_by_embedding(embedding: list[float], threshold: float = 0.85) -> list[dict]:
    result = get_db().rpc("find_similar_vacancies", {
        "query_embedding": embedding,
        "similarity_threshold": threshold,
        "days_back": 30,
    }).execute()
    return result.data


def insert_vacancy(data: dict):
    try:
        result = get_db().table("vacancies").insert(data).execute()
        return result.data[0]["id"] if result.data else None
    except Exception as e:
        print(f"[DB] Ошибка вставки: {e}")
        return None


def mark_sent(vacancy_id: int):
    get_db().table("vacancies") \
        .update({"sent_to_user": True}) \
        .eq("id", vacancy_id).execute()


def get_top_unsent(limit: int = 7) -> list[dict]:
    """Топ matched вакансий — сначала свежие, потом по скору."""
    result = get_db().table("vacancies") \
        .select("*") \
        .eq("sent_to_user", False) \
        .eq("is_duplicate", False) \
        .eq("category", "matched") \
        .order("created_at", desc=True) \
        .order("similarity_score", desc=True) \
        .limit(limit) \
        .execute()
    return result.data


def get_unsorted_unsent(limit: int = 10) -> list[dict]:
    """Вакансии без remote — сначала самые свежие."""
    result = get_db().table("vacancies") \
        .select("id, title, full_text, url, source, channel, contacts, created_at") \
        .eq("sent_to_user", False) \
        .eq("is_duplicate", False) \
        .eq("category", "unsorted") \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()
    return result.data


# ─── Каналы ───────────────────────────────────────────────────────────────────

def get_active_channels() -> list[dict]:
    result = get_db().table("tg_channels") \
        .select("*").eq("active", True).execute()
    return result.data


def update_channel_last_msg(channel_username: str, last_msg_id: int):
    get_db().table("tg_channels") \
        .update({"last_msg_id": last_msg_id}) \
        .eq("username", channel_username).execute()


def update_channel_health(
    username: str,
    is_alive: bool,
    last_post_at,
    last_checked_at,
    set_inactive: bool = False,
):
    """Обновляет health-поля канала. Мёртвые каналы ставит active=False."""
    data = {
        "is_alive":        is_alive,
        "last_checked_at": last_checked_at.isoformat() if last_checked_at else None,
    }
    if last_post_at:
        data["last_post_at"] = last_post_at.isoformat()
    if set_inactive:
        data["active"] = False

    try:
        get_db().table("tg_channels") \
            .update(data) \
            .eq("username", username) \
            .execute()
    except Exception as e:
        print(f"[DB] update_channel_health ошибка @{username}: {e}")


def get_last_health_check():
    """Возвращает datetime последней проверки здоровья каналов (или None)."""
    try:
        result = get_db().table("tg_channels") \
            .select("last_checked_at") \
            .order("last_checked_at", desc=True) \
            .limit(1) \
            .execute()
        if result.data and result.data[0].get("last_checked_at"):
            from datetime import datetime, timezone
            raw = result.data[0]["last_checked_at"]
            # Supabase возвращает строку ISO
            if isinstance(raw, str):
                raw = raw.replace("Z", "+00:00")
                return datetime.fromisoformat(raw)
            return raw
    except Exception:
        pass
    return None


# ─── Профиль ──────────────────────────────────────────────────────────────────

def get_user_profile():
    result = get_db().table("user_profile") \
        .select("*").order("updated_at", desc=True).limit(1).execute()
    return result.data[0] if result.data else None


def upsert_user_profile(profile_text: str, embedding: list[float]):
    db = get_db()
    existing = get_user_profile()
    data = {"profile_text": profile_text, "embedding": embedding}
    if existing:
        db.table("user_profile").update(data).eq("id", existing["id"]).execute()
    else:
        db.table("user_profile").insert(data).execute()


# ─── Хелперы ──────────────────────────────────────────────────────────────────

def make_text_hash(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.md5(normalized.encode()).hexdigest()


def make_contact_hash(contacts):
    if not contacts:
        return None
    sorted_contacts = sorted(c.lower().strip() for c in contacts)
    return hashlib.md5("|".join(sorted_contacts).encode()).hexdigest()
