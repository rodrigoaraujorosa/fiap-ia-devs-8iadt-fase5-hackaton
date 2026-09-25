import uuid
from datetime import UTC, datetime

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.jobs.followup import run_followups
from app.models import Appointment, Lead, Message, Slot, Summary
from app.schemas.crm import AppointmentOut, LeadDetail, SummaryOut
from app.schemas.lead import LeadOut
from app.services.summary import generate_summary

router = APIRouter(tags=["crm"])


def appointment_out(appt: Appointment, lead_name: str | None = None) -> AppointmentOut:
    return AppointmentOut.model_validate(
        {**appt.__dict__, "start_at": appt.slot.start_at, "broker": appt.broker, "lead_name": lead_name}
    )


@router.get("/leads", response_model=list[LeadOut])
def list_leads(
    status: str | None = None,
    temperature: str | None = None,
    intent: str | None = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Lead).where(Lead.last_message_at.is_not(None))  # só leads que conversaram
    if status:
        stmt = stmt.where(Lead.status == status)
    if temperature:
        stmt = stmt.where(Lead.temperature == temperature)
    if intent:
        stmt = stmt.where(Lead.intent == intent)
    return db.scalars(stmt.order_by(Lead.score.desc(), Lead.last_message_at.desc()).limit(limit)).all()


@router.get("/leads/{lead_id}", response_model=LeadDetail)
def get_lead(lead_id: uuid.UUID, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead não encontrado")
    summary = db.scalar(select(Summary).where(Summary.lead_id == lead_id).order_by(Summary.created_at.desc()))
    appts = db.scalars(
        select(Appointment).join(Slot).where(Appointment.lead_id == lead_id).order_by(Slot.start_at)
    ).all()
    messages = db.scalars(select(Message).where(Message.lead_id == lead_id).order_by(Message.created_at)).all()
    return LeadDetail.model_validate(
        {
            **LeadOut.model_validate(lead).model_dump(),
            "assigned_broker": lead.assigned_broker,
            "summary": summary,
            "appointments": [appointment_out(a, lead.name) for a in appts],
            "messages": messages,
        }
    )


@router.post("/leads/{lead_id}/summary", response_model=SummaryOut)
def create_summary(lead_id: uuid.UUID, db: Session = Depends(get_db)):
    """Gera (ou atualiza) o resumo inteligente do lead para o corretor."""
    if not db.get(Lead, lead_id):
        raise HTTPException(404, "Lead não encontrado")
    try:
        return generate_summary(db, lead_id)
    except (anthropic.APIError, RuntimeError) as exc:
        raise HTTPException(502, "Não foi possível gerar o resumo agora") from exc


@router.get("/appointments", response_model=list[AppointmentOut])
def list_appointments(upcoming: bool = True, db: Session = Depends(get_db)):
    stmt = select(Appointment, Lead.name).join(Slot).join(Lead, Lead.id == Appointment.lead_id)
    if upcoming:
        stmt = stmt.where(Slot.start_at >= datetime.now(UTC), Appointment.status.in_(("agendado", "confirmado")))
    return [appointment_out(appt, name) for appt, name in db.execute(stmt.order_by(Slot.start_at)).all()]


@router.post("/followups/run")
def trigger_followups():
    """Dispara o ciclo de follow-up agora (o job também roda sozinho periodicamente)."""
    return {"enviados": run_followups()}
