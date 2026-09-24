import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Lead, Message
from app.models.enums import Channel
from app.schemas.lead import LeadCreate, LeadOut, MessageIn, MessageOut
from app.services.chat import stream_turn_sse

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_lead(db: Session, lead_id: uuid.UUID) -> Lead:
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Conversa não encontrada")
    return lead


@router.post("/sessions", response_model=LeadOut, status_code=201)
def create_session(payload: LeadCreate | None = None, db: Session = Depends(get_db)):
    """Inicia uma conversa: cria o lead (canal web)."""
    lead = Lead(channel=Channel.WEB, regions=[], extra={}, **(payload.model_dump() if payload else {}))
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@router.get("/{lead_id}/messages", response_model=list[MessageOut])
def list_messages(lead_id: uuid.UUID, db: Session = Depends(get_db)):
    _get_lead(db, lead_id)
    return db.scalars(select(Message).where(Message.lead_id == lead_id).order_by(Message.created_at, Message.id)).all()


@router.post("/{lead_id}/messages")
def send_message(lead_id: uuid.UUID, payload: MessageIn, db: Session = Depends(get_db)):
    """Envia uma mensagem do lead e devolve a resposta do agente via Server-Sent Events.

    Eventos: analysis, agent, token, tool, properties, error, done.
    """
    _get_lead(db, lead_id)
    return StreamingResponse(
        stream_turn_sse(lead_id, payload.content.strip()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
