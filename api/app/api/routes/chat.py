import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.qualification import normalize_phone
from app.db.session import get_db
from app.models import Lead, Message
from app.models.enums import Channel
from app.schemas.lead import ContactIn, LeadCreate, LeadOut, MessageIn, MessageOut
from app.services.app_config import get_widget_config
from app.services.chat import save_contact, stream_turn_sse
from app.services.rate_limit import ai_available, check_message, check_new_session, client_ip

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_lead(db: Session, lead_id: uuid.UUID) -> Lead:
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Conversa não encontrada")
    return lead


@router.get("/status")
def chat_status():
    """Se a Laris está atendendo com IA; pausada, o chat mostra o formulário de contato (nome e telefone)."""
    return {"ai_enabled": ai_available()}


@router.post("/sessions", response_model=LeadOut, status_code=201)
def create_session(request: Request, payload: LeadCreate | None = None, db: Session = Depends(get_db)):
    """Inicia uma conversa: cria o lead. Com `source` (widget no site de uma imobiliária), o canal é "site"."""
    if blocked := check_new_session(db, client_ip(request)):
        raise HTTPException(429, blocked)
    data = payload.model_dump(exclude={"source"}) if payload else {}
    source = payload.source.model_dump(exclude_none=True) if payload and payload.source else None
    if source and not get_widget_config(db).allows(urlparse(source.get("page_url") or "").netloc):
        raise HTTPException(403, "Widget não autorizado neste site")  # o bloqueio de verdade é o frame-ancestors
    extra = {"source": source} if source else {}
    if source and source.get("property_id"):
        extra["viewing"] = source["property_id"]
    lead = Lead(channel=Channel.SITE if source else Channel.WEB, regions=[], extra=extra, **data)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@router.get("/{lead_id}/messages", response_model=list[MessageOut])
def list_messages(lead_id: uuid.UUID, db: Session = Depends(get_db)):
    _get_lead(db, lead_id)
    return db.scalars(select(Message).where(Message.lead_id == lead_id).order_by(Message.id)).all()


@router.post("/{lead_id}/contact", response_model=LeadOut)
def send_contact(lead_id: uuid.UUID, payload: ContactIn, request: Request, db: Session = Depends(get_db)):
    """Recebe o formulário de contato do chat (nome + telefone) e responde com o recado de agradecimento."""
    _get_lead(db, lead_id)
    if blocked := check_message(db, lead_id, client_ip(request)):
        raise HTTPException(429, blocked)
    phone = normalize_phone(payload.phone)
    if phone is None:
        raise HTTPException(422, "Telefone inválido: informe o DDD e o número")
    return save_contact(lead_id, payload.name.strip(), phone)


@router.post("/{lead_id}/messages")
def send_message(lead_id: uuid.UUID, payload: MessageIn, request: Request, db: Session = Depends(get_db)):
    """Envia uma mensagem do lead e devolve a resposta do agente via Server-Sent Events.

    Eventos: analysis, agent, token, tool, properties, error, done. 429 se passar do limite de mensagens.
    """
    _get_lead(db, lead_id)
    if blocked := check_message(db, lead_id, client_ip(request)):
        raise HTTPException(429, blocked)
    return StreamingResponse(
        stream_turn_sse(lead_id, payload.content.strip(), payload.context),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
