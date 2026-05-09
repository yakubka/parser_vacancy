from datetime import datetime, timezone
from processing.embeddings import cosine_similarity
import config


def score_vacancy(vacancy_embedding, profile_embedding, vacancy_text, posted_at=None):
    semantic  = _semantic_score(vacancy_embedding, profile_embedding)
    stack     = _stack_score(vacancy_text)
    fmt       = _format_score(vacancy_text)
    freshness = _freshness_score(posted_at)
    total = (
        config.SCORE_SEMANTIC  * semantic  +
        config.SCORE_STACK     * stack     +
        config.SCORE_FORMAT    * fmt       +
        config.SCORE_FRESHNESS * freshness
    )
    return round(min(total, 1.0), 4)


def explain_score(vacancy_embedding, profile_embedding, vacancy_text, posted_at=None):
    semantic  = _semantic_score(vacancy_embedding, profile_embedding)
    stack     = _stack_score(vacancy_text)
    fmt       = _format_score(vacancy_text)
    freshness = _freshness_score(posted_at)
    total = (
        config.SCORE_SEMANTIC  * semantic  +
        config.SCORE_STACK     * stack     +
        config.SCORE_FORMAT    * fmt       +
        config.SCORE_FRESHNESS * freshness
    )
    text_lower = vacancy_text.lower()
    matched_stack = [t for t in config.USER_TECH_STACK if t in text_lower]
    return {
        "total":         round(min(total, 1.0), 3),
        "semantic":      round(semantic, 3),
        "stack":         round(stack, 3),
        "format":        round(fmt, 3),
        "freshness":     round(freshness, 3),
        "matched_stack": matched_stack,
    }


def _semantic_score(vacancy_emb, profile_emb):
    sim = cosine_similarity(vacancy_emb, profile_emb)
    return min(max(0.0, (sim - 0.2) / 0.7), 1.0)


def _stack_score(text):
    text_lower = text.lower()
    matches = sum(1 for tech in config.USER_TECH_STACK if tech in text_lower)
    if not config.USER_TECH_STACK:
        return 0.5
    return min(matches / len(config.USER_TECH_STACK) * 3, 1.0)


def _format_score(text):
    text_lower = text.lower()
    remote_signals = ["remote", "удалённо", "удаленно", "дистанционно", "full remote"]
    hybrid_signals = ["hybrid", "гибрид", "частично удалённо"]
    office_signals = ["офис", "office only", "в офисе"]
    has_remote = any(s in text_lower for s in remote_signals)
    has_hybrid = any(s in text_lower for s in hybrid_signals)
    has_office = any(s in text_lower for s in office_signals)
    if config.PREFERRED_FORMAT == "remote":
        if has_remote:  return 1.0
        if has_hybrid:  return 0.5
        if has_office:  return 0.1
        return 0.6
    return 0.6


def _freshness_score(posted_at):
    if posted_at is None:
        return 0.5
    now = datetime.now(timezone.utc)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    age_days = (now - posted_at).days
    if age_days <= 1:   return 1.0
    if age_days <= 3:   return 0.9
    if age_days <= 7:   return 0.7
    if age_days <= 14:  return 0.4
    return 0.0
