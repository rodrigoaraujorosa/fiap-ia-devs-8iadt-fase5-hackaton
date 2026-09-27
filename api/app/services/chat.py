"""Orquestra um turno de conversa: persiste mensagens, roda o grafo e emite eventos SSE."""

import json
import logging
import queue
import re
import threading
import uuid
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from app.agents.qualification import normalize_phone, proper_name
from app.agents.runtime import get_graph
from app.core import observability
from app.db.session import SessionLocal
from app.models import Lead, Message, Property
from app.models.enums import MessageRole
from app.schemas.lead import LeadOut, PageContext
from app.services.app_config import ai_enabled, get_followup_config

log = logging.getLogger(__name__)
_lead_locks: defaultdict[uuid.UUID, threading.Lock] = defaultdict(threading.Lock)
PHONE_REQUEST = re.compile(r"whats\s?app|telefone|celular", re.IGNORECASE)
PHONE_IN_TEXT = re.compile(r"\+?\d[\d\s().-]{7,}\d")

# IA desligada nas configurações: resposta fixa, sem chamar o Claude (o recado fica registrado para o corretor)
PAUSED_REPLY = (
    "Nosso atendimento automático está pausado no momento. Deixe seu nome e telefone que um corretor retorna 😊"
)
PAUSED_THANKS = "Obrigada! Seu contato ficou anotado e um corretor retorna em breve."

# sem IA, o nome sai por regra: "meu nome é X", "sou o X", "me chamo X" ou o texto curto que acompanha o telefone
_WORD = r"[A-Za-zÀ-ÿ]+"
NAME_INTRO = re.compile(rf"\b(?:meu nome é|me chamo|aqui é (?:o |a )?|sou (?:o |a )?)\s*({_WORD}(?:\s+{_WORD})?)", re.I)
NOT_NAME = {
    "oi", "olá", "ola", "bom", "boa", "dia", "tarde", "noite", "tudo", "bem", "meu", "minha", "nome", "é", "e", "o",
    "a", "telefone", "fone", "tel", "whatsapp", "zap", "celular", "contato", "número", "numero", "obrigado",
    "obrigada", "sim", "ok", "pode", "ligar", "me", "chamo", "sou", "aqui",
}  # fmt: skip


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def run_turn(lead_id: uuid.UUID, text: str, context: PageContext | None = None) -> Iterator[dict]:
    """Executa um turno e gera eventos {"type": ...}. Base do SSE e dos testes.

    context: página em que o visitante está (widget). O imóvel em foco vai para o contexto do agente.
    """
    now = datetime.now(UTC)
    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        if context and context.property_id and db.get(Property, context.property_id):
            lead.extra = {**(lead.extra or {}), "viewing": context.property_id}
        db.add(Message(lead_id=lead_id, role=MessageRole.USER, content=text))
        lead.last_message_at = lead.last_lead_message_at = now
        lead.followup_count = 0
        lead.next_followup_at = None
        db.commit()

    if not ai_enabled():
        yield _paused_turn(lead_id, text)
        return

    reply, bubbles, agent, property_ids, notices = "", [], None, [], {}
    graph_input = {"lead_id": str(lead_id), "messages": [{"role": "user", "content": text}]}
    config = {"configurable": {"thread_id": str(lead_id)}}
    with observability.trace("turno", session_id=str(lead_id), input=text) as root:
        try:
            for event in get_graph().stream(graph_input, config, stream_mode="custom"):
                if event["type"] == "reply":
                    reply, bubbles, property_ids = event["text"], event["bubbles"], event["property_ids"]
                    continue
                if event["type"] == "agent":
                    agent = event["agent"]
                elif event["type"] in ("appointment", "handoff"):
                    notices[event["type"]] = {k: v for k, v in event.items() if k != "type"}
                yield event
        except Exception:
            log.exception("Erro ao processar turno do lead %s", lead_id)
            yield {"type": "error", "message": "Não consegui responder agora. Tente novamente em instantes."}
        root.update(output=reply, metadata={"agent": agent})

    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        if reply:
            # um balão por mensagem (texto antes de uma ferramenta vira balão próprio); cards e avisos no último
            sent_at = datetime.now(UTC)
            bubbles = bubbles or [reply]
            for i, text in enumerate(bubbles):  # inseridos em ordem: o id sequencial ordena os balões
                last = i == len(bubbles) - 1
                db.add(
                    Message(
                        lead_id=lead_id,
                        role=MessageRole.ASSISTANT,
                        content=text,
                        agent=agent,
                        meta={"property_ids": property_ids, **notices} if last else {"property_ids": []},
                    )
                )
            lead.last_message_at = sent_at
            if not lead.phone and PHONE_REQUEST.search(reply):  # a Laris pediu o telefone: não pede de novo
                lead.extra = {**(lead.extra or {}), "phone_asked": True}
            if lead.status in ("novo", "em_qualificacao", "qualificado"):  # agendado/encaminhado não recebem follow-up
                lead.next_followup_at = lead.last_message_at + timedelta(minutes=get_followup_config(db).minutes)
        db.commit()
        db.refresh(lead)
        yield {
            "type": "done",
            "reply": reply,
            "bubbles": bubbles,
            "property_ids": property_ids,
            "agent": agent,
            "lead": LeadOut.model_validate(lead).model_dump(),
        }


def guess_name(text: str) -> str | None:
    """Nome do cliente numa mensagem, sem LLM (modo IA pausada). None se não der para ter certeza."""
    phone = PHONE_IN_TEXT.search(text)
    rest = PHONE_IN_TEXT.sub(" ", text)
    if match := NAME_INTRO.search(rest):
        words = [w for w in match.group(1).split() if w.lower() not in NOT_NAME]
    elif phone:  # "Juliano, 51 99999-1234": o que sobra ao lado do telefone é o nome
        words = [w for w in re.findall(_WORD, rest) if w.lower() not in NOT_NAME]
        if len(words) > 3:
            return None
    else:
        return None
    return proper_name(" ".join(words[:3])) if words else None


def _paused_turn(lead_id: uuid.UUID, text: str) -> dict:
    """Turno sem IA: guarda nome e telefone, se vieram na mensagem, e responde com o recado fixo."""
    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        if not lead.phone and (match := PHONE_IN_TEXT.search(text)):
            lead.phone = normalize_phone(match.group())
        if not lead.name and (name := guess_name(text)):
            lead.name = name
        reply = PAUSED_THANKS if lead.phone else PAUSED_REPLY
        db.add(Message(lead_id=lead_id, role=MessageRole.ASSISTANT, content=reply, agent="pausa",
                       meta={"property_ids": []}))  # fmt: skip
        lead.last_message_at = datetime.now(UTC)
        db.commit()
        db.refresh(lead)
        return {"type": "done", "reply": reply, "bubbles": [reply], "property_ids": [], "agent": None,
                "lead": LeadOut.model_validate(lead).model_dump(),
                "contact_form": not (lead.name and lead.phone)}  # fmt: skip


def save_contact(lead_id: uuid.UUID, name: str, phone: str) -> Lead:
    """Formulário de contato do chat (IA pausada): nome e telefone digitados em campos próprios, sem adivinhar."""
    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        now = datetime.now(UTC)
        lead.name, lead.phone = proper_name(name), phone
        db.add(Message(lead_id=lead_id, role=MessageRole.USER, content=f"Nome: {lead.name} · Telefone: {phone}",
                       meta={"contact_form": True}))  # fmt: skip
        db.add(Message(lead_id=lead_id, role=MessageRole.ASSISTANT, content=PAUSED_THANKS, agent="pausa",
                       meta={"property_ids": []}))  # fmt: skip
        lead.last_message_at = lead.last_lead_message_at = now
        db.commit()
        db.refresh(lead)
        db.expunge(lead)
        return lead


def stream_turn_sse(lead_id: uuid.UUID, text: str, context: PageContext | None = None) -> Iterator[str]:
    """Roda o turno numa thread própria (contexto de tracing estável) e repassa os eventos como SSE."""
    events: queue.Queue[dict | None] = queue.Queue()

    def produce() -> None:
        with _lead_locks[lead_id]:  # uma mensagem por vez por conversa
            try:
                for event in run_turn(lead_id, text, context):
                    events.put(event)
            finally:
                events.put(None)

    threading.Thread(target=produce, daemon=True, name=f"turn-{lead_id}").start()
    while (event := events.get()) is not None:
        yield sse(event["type"], event)
