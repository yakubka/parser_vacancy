from parsers.telegram_parser import RawVacancy
from processing.embeddings import embed_text, cosine_similarity, prepare_vacancy_text
from database import (
    vacancy_exists_by_hash,
    find_duplicates_by_contact,
    find_similar_by_embedding,
    make_text_hash,
    make_contact_hash,
)
import config


def check_duplicate(vacancy: RawVacancy, embedding: list[float]) -> tuple[bool, str]:
    text_hash = make_text_hash(vacancy.full_text)

    if vacancy_exists_by_hash(text_hash):
        return True, "exact_hash"

    if vacancy.contacts:
        contact_hash = make_contact_hash(vacancy.contacts)
        if contact_hash:
            existing = find_duplicates_by_contact(contact_hash, embedding)
            if existing:
                new_title_emb = embed_text(vacancy.full_text[:200])
                for ex in existing:
                    ex_emb = ex.get("embedding")
                    if ex_emb is None:
                        continue
                    title_sim = cosine_similarity(new_title_emb, ex_emb)
                    if title_sim >= config.CONTACT_DEDUP_TITLE_THRESHOLD:
                        return True, f"same_contact+title_sim={title_sim:.2f}"
        return False, "unique_contact"

    similar = find_similar_by_embedding(embedding, config.TEXT_SIMILARITY_THRESHOLD)
    if similar:
        best = max(similar, key=lambda x: x.get("similarity", 0))
        return True, f"text_sim={best.get('similarity', 0):.2f}"

    return False, "unique"


def prepare_for_db(vacancy: RawVacancy, embedding: list[float], score: float) -> dict:
    from parsers.telegram_parser import extract_title
    text_hash = make_text_hash(vacancy.full_text)
    contact_hash = make_contact_hash(vacancy.contacts) if vacancy.contacts else None

    return {
        "source":           vacancy.source,
        "source_id":        vacancy.source_id,
        "channel":          vacancy.channel,
        "title":            extract_title(vacancy.full_text),
        "full_text":        vacancy.full_text[:5000],
        "url":              vacancy.url,
        "contacts":         vacancy.contacts,
        "contact_hash":     contact_hash,
        "text_hash":        text_hash,
        "embedding":        embedding,
        "similarity_score": round(score, 4),
        "is_duplicate":     False,
        "sent_to_user":     False,
    }
