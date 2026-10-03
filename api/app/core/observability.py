"""Observabilidade: traces no Langfuse (detalhe de cada chamada) e uso da IA no banco do app (painel).

Sem LANGFUSE_PUBLIC_KEY/SECRET_KEY o Langfuse vira no-op, então o app funciona igual sem conta lá. O registro no
banco (chamadas ao Claude, ferramentas, fluxos e suspeitas de injection) acontece sempre: o painel de
observabilidade lê dele, sem depender da cota da API do Langfuse.
"""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.core.pii import mask_pii

log = logging.getLogger(__name__)


class _NoopObservation:
    def update(self, **_: Any) -> "_NoopObservation":
        return self


_NOOP = _NoopObservation()
RECORDED = {"generation": "llm", "tool": "tool"}  # tipo da observação -> kind em usage_events
_session: ContextVar[str | None] = ContextVar("observability_session", default=None)  # conversa (lead) do fluxo atual


class _Recorded:
    """Observação que também guarda o uso de tokens informado em update(), para o registro no banco."""

    def __init__(self, inner: Any):
        self.inner = inner
        self.usage: dict[str, int] | None = None

    def update(self, **kwargs: Any) -> "_Recorded":
        if kwargs.get("usage_details"):
            self.usage = kwargs["usage_details"]
        self.inner.update(**kwargs)
        return self


def _record(kind: str, name: str, started: float | None = None, **kwargs: Any) -> None:
    from app.services import usage  # import tardio: services depende de core

    latency = round((time.perf_counter() - started) * 1000) if started else 0
    usage.record(kind, name, latency_ms=latency, session_id=_session.get(), **kwargs)


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
        mask=mask_pii,  # telefone, e-mail, CPF e CNPJ não saem da aplicação
    )


def enabled() -> bool:
    return _client() is not None


@contextmanager
def trace(name: str, *, session_id: str, input: Any = None, tags: list[str] | None = None) -> Iterator[Any]:
    """Observação raiz de um fluxo (turno de conversa, follow-up...), agrupada por conversa (session_id)."""
    client = _client()
    token = _session.set(session_id)
    started = time.perf_counter()
    try:
        if client is None:
            yield _NOOP
            return
        from langfuse import propagate_attributes

        with propagate_attributes(session_id=session_id, user_id=session_id, trace_name=name, tags=tags or []):
            with client.start_as_current_observation(name=name, as_type="agent", input=input) as obs:
                yield obs
    finally:
        _record("trace", name, started)
        try:
            _session.reset(token)
        except ValueError:  # gerador retomado em outro contexto: só limpa
            _session.set(None)


@contextmanager
def observation(name: str, as_type: str = "span", **kwargs: Any) -> Iterator[Any]:
    """Observação filha (nó do grafo, chamada de LLM com as_type='generation', ferramenta...).

    Chamadas ao Claude e ferramentas também vão para o banco do app: a chamada só é registrada se terminou
    (update(usage_details=...)), a ferramenta sempre.
    """
    client = _client()
    span = client.start_as_current_observation(name=name, as_type=as_type, **kwargs) if client else nullcontext(_NOOP)
    with span as obs:
        kind = RECORDED.get(as_type)
        if not kind:
            yield obs
            return
        recorded = _Recorded(obs)
        started = time.perf_counter()
        try:
            yield recorded
        finally:
            if kind == "tool":
                _record(kind, name, started)
            elif recorded.usage is not None:
                _record(kind, name, started, model=kwargs.get("model"), usage=recorded.usage)


def flag_trace(name: str, comment: str) -> None:
    """Marca o trace atual (ex.: suspeita de prompt injection) com tag, observação do tipo guardrail e score.

    A tag é aplicada no meio do turno: propagate_attributes grava no span raiz, que ainda está aberto.
    """
    _record("guardrail", name)
    client = _client()
    if client is None:
        return
    from langfuse import propagate_attributes

    with propagate_attributes(tags=[name]):
        with client.start_as_current_observation(name=name, as_type="guardrail", level="WARNING",
                                                 output={"detectado_por": comment}):  # fmt: skip
            pass
    client.score_current_trace(name=name, value=1, data_type="BOOLEAN", comment=comment)


def flush() -> None:
    client = _client()
    if client is not None:
        client.flush()
