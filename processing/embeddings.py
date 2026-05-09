from functools import lru_cache
import numpy as np
from sentence_transformers import SentenceTransformer
import config


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    print(f"[Embeddings] Загружаем модель {config.EMBEDDING_MODEL}...")
    model = SentenceTransformer(config.EMBEDDING_MODEL)
    print("[Embeddings] Модель загружена ✓")
    return model


def embed_text(text: str) -> list[float]:
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return embeddings.tolist()


def parse_embedding(emb) -> list:
    """Конвертируем эмбеддинг из любого формата в list[float]."""
    if emb is None:
        return []
    if isinstance(emb, list):
        return [float(x) for x in emb]
    if isinstance(emb, str):
        import json
        s = emb.strip()
        if s.startswith('['):
            return [float(x) for x in json.loads(s)]
        s = s.strip('()')
        return [float(x) for x in s.split(',') if x.strip()]
    return [float(x) for x in emb]


def cosine_similarity(a, b) -> float:
    a_arr = np.array(parse_embedding(a), dtype=float)
    b_arr = np.array(parse_embedding(b), dtype=float)
    if a_arr.size == 0 or b_arr.size == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr))


def prepare_vacancy_text(full_text: str, max_chars: int = 1000) -> str:
    import re
    text = re.sub(r'https?://\S+', '', full_text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_chars]
