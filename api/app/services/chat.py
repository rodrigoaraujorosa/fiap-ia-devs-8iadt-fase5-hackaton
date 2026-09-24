"""Orquestra um turno de conversa: persiste mensagens, roda o grafo e emite eventos SSE."""

import json
import logging
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from app.agents.runtime import get_graph
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Lead, Message
from app.models.enums import MessageRole
from app.schemas.lead import LeadOut

log = logging.getLogger(__name__)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def run_turn(lead_id: uuid.UUID, text: str) -> Iterator[dict]:
    """Executa um turno e gera eventos {"type": ...}. Base do SSE e dos testes."""
    now = datetime.now(UTC)
    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        db.add(Message(lead_id=lead_id, role=MessageRole.USER, content=text))
        lead.last_message_at = lead.last_lead_message_at = now
        lead.followup_count = 0
        lead.next_followup_at = None
        db.commit()

    reply, agent, property_ids = "", None, []
    graph_input = {"lead_id": str(lead_id), "messages": [{"role": "user", "content": text}]}
    config = {"configurable": {"thread_id": str(lead_id)}}
    try:
        for event in get_graph().stream(graph_input, config, stream_mode="custom"):
            if event["type"] == "reply":
                reply, property_ids = event["text"], event["property_ids"]
                continue
            if event["type"] == "agent":
                agent = event["agent"]
            yield event
    except Exception:
        log.exception("Erro ao processar turno do lead %s", lead_id)
        yield {"type": "error", "message": "Não consegui responder agora. Tente novamente em instantes."}

    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        if reply:
            db.add(
                Message(
                    lead_id=lead_id,
                    role=MessageRole.ASSISTANT,
                    content=reply,
                    agent=agent,
                    meta={"property_ids": list(dict.fromkeys(property_ids))},
                )
            )
            lead.last_message_at = datetime.now(UTC)
            lead.next_followup_at = lead.last_message_at + timedelta(minutes=get_settings().followup_minutes)
        db.commit()
        db.refresh(lead)
        yield {"type": "done", "reply": reply, "agent": agent, "lead": LeadOut.model_validate(lead).model_dump()}


def stream_turn_sse(lead_id: uuid.UUID, text: str) -> Iterator[str]:
    for event in run_turn(lead_id, text):
        yield sse(event["type"], event)
