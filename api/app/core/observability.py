"""Observabilidade com Langfuse (traces por conversa, custo e latência de cada chamada ao Claude).

Sem LANGFUSE_PUBLIC_KEY/SECRET_KEY tudo vira no-op, então o app funciona igual sem conta no Langfuse.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

log = logging.getLogger(__name__)


class _NoopObservation:
    def update(self, **_: Any) -> "_NoopObservation":
        return self


_NOOP = _NoopObservation()


@lru_cache
def _client():
    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return None
    from langfuse import Langfuse

    log.info("Langfuse habilitado (%s)", s.langfuse_base_url)
    return Langfuse(
        public_key=s.langfuse_public_key,
        secret_key=s.langfuse_secret_key,
        base_url=s.langfuse_base_url,
        environment=s.environment,
    )


def enabled() -> bool:
    return _client() is not None


@contextmanager
def trace(name: str, *, session_id: str, input: Any = None, tags: list[str] | None = None) -> Iterator[Any]:
    """Observação raiz de um fluxo (turno de conversa, follow-up...), agrupada por conversa (session_id)."""
    client = _client()
    if client is None:
        yield _NOOP
        return
    from langfuse import propagate_attributes

    with propagate_attributes(session_id=session_id, user_id=session_id, trace_name=name, tags=tags or []):
        with client.start_as_current_observation(name=name, as_type="agent", input=input) as obs:
            yield obs


@contextmanager
def observation(name: str, as_type: str = "span", **kwargs: Any) -> Iterator[Any]:
    """Observação filha (nó do grafo, chamada de LLM com as_type='generation', ferramenta...)."""
    client = _client()
    if client is None:
        yield _NOOP
        return
    with client.start_as_current_observation(name=name, as_type=as_type, **kwargs) as obs:
        yield obs


def flush() -> None:
    client = _client()
    if client is not None:
        client.flush()
