"""Registro do uso da IA no banco do app (tabela usage_events), fonte do painel de observabilidade."""

import logging
import uuid

from app.core import pricing
from app.db.session import SessionLocal
from app.models import UsageEvent

log = logging.getLogger(__name__)


def record(kind: str, name: str, *, model: str | None = None, usage: dict[str, int] | None = None,
           latency_ms: int = 0, session_id: str | None = None) -> None:  # fmt: skip
    """Grava um evento. Nunca derruba o atendimento: uma falha aqui só vai para o log."""
    usage = usage or {}
    try:
        lead_id = uuid.UUID(session_id) if session_id else None
    except ValueError:
        lead_id = None
    try:
        with SessionLocal() as db:
            db.add(
                UsageEvent(
                    kind=kind,
                    name=name[:60],
                    model=model,
                    lead_id=lead_id,
                    input_tokens=usage.get("input", 0),
                    output_tokens=usage.get("output", 0),
                    cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                    cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
                    cost_usd=pricing.cost(model, usage),
                    latency_ms=latency_ms,
                )
            )
            db.commit()
    except Exception:
        log.exception("Não consegui registrar o uso da IA (%s %s)", kind, name)
