from functools import lru_cache

from fastembed import TextEmbedding

from app.core.config import get_settings


@lru_cache
def _model() -> TextEmbedding:
    settings = get_settings()
    return TextEmbedding(settings.embedding_model, cache_dir=settings.embedding_cache_dir)


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [vec.tolist() for vec in _model().embed(texts)]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
