import uuid
from datetime import UTC, datetime, timedelta

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import false, func, or_, select, true
from sqlalchemy.orm import Session

from app.agents.qualification import missing_fields
from app.core.auth import Principal, current_principal
from app.db.session import get_db
from app.models import Appointment, EmailLog, Lead, Message, Slot, Summary
from app.schemas.crm import AppointmentOut, EmailLogOut, LeadDetail, SummaryOut
from app.schemas.lead import LeadOut
from app.services.app_config import ai_enabled
from app.services.mailer import send_summary_email
from app.services.summary import generate_summary

router = APIRouter(tags=["crm"], dependencies=[Depends(current_principal)])  # CRM só com login


def visible_leads(principal: Principal):
    """Condição SQL dos leads que o usuário enxerga: todos, ou só os do corretor (atribuídos ou com visita)."""
    if principal.sees_all:
        return None
    if principal.broker_id is None:  # corretor sem vínculo na tela de usuários: nada a mostrar
        return false()
    own_visits = select(Appointment.lead_id).where(Appointment.broker_id == principal.broker_id)
    return or_(Lead.assigned_broker_id == principal.broker_id, Lead.id.in_(own_visits))


def lead_or_404(db: Session, lead_id: uuid.UUID, principal: Principal, write: bool = False) -> Lead:
    """O lead, se existir e o usuário puder vê-lo (ou alterá-lo, com write=True)."""
    if write and not principal.can_write:
        raise HTTPException(403, "Seu perfil é só de leitura")
    stmt = select(Lead).where(Lead.id == lead_id)
    if (scope := visible_leads(principal)) is not None:
        stmt = stmt.where(scope)
    lead = db.scalar(stmt)
    if not lead:
        raise HTTPException(404, "Lead não encontrado")
    return lead


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
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    stmt = select(Lead).where(Lead.last_message_at.is_not(None))  # só leads que conversaram
    if (scope := visible_leads(principal)) is not None:
        stmt = stmt.where(scope)
    if status:
        stmt = stmt.where(Lead.status == status)
    if temperature:
        stmt = stmt.where(Lead.temperature == temperature)
    if intent:
        stmt = stmt.where(Lead.intent == intent)
    # mais recentes no topo (último contato; leads sem mensagem pela criação), como uma caixa de entrada
    recent = func.coalesce(Lead.last_message_at, Lead.created_at)
    return db.scalars(stmt.order_by(recent.desc(), Lead.created_at.desc()).limit(limit)).all()


def lead_detail(db: Session, lead: Lead, internal: bool = True) -> LeadDetail:
    """Perfil, agendamentos e conversa de um lead. internal=False é a visão do próprio visitante no chat:
    sem o resumo escrito para o corretor e sem o histórico de e-mails internos."""
    lead_id = lead.id
    summary = emails = None
    if internal:
        summary = db.scalar(select(Summary).where(Summary.lead_id == lead_id).order_by(Summary.created_at.desc()))
        emails = db.scalars(
            select(EmailLog).where(EmailLog.lead_id == lead_id).order_by(EmailLog.created_at.desc())
        ).all()
    appts = db.scalars(
        select(Appointment).join(Slot).where(Appointment.lead_id == lead_id).order_by(Slot.start_at)
    ).all()
    messages = db.scalars(select(Message).where(Message.lead_id == lead_id).order_by(Message.id)).all()
    return LeadDetail.model_validate(
        {
            **LeadOut.model_validate(lead).model_dump(),
            "assigned_broker": lead.assigned_broker,
            "summary": summary,
            "appointments": [appointment_out(a, lead.name) for a in appts],
            "messages": messages,
            "missing": missing_fields(lead),
            "emails": emails or [],
        }
    )


@router.get("/leads/{lead_id}", response_model=LeadDetail)
def get_lead(lead_id: uuid.UUID, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    return lead_detail(db, lead_or_404(db, lead_id, principal))


@router.post("/leads/{lead_id}/summary", response_model=SummaryOut)
def create_summary(
    lead_id: uuid.UUID, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)
):
    """Gera (ou atualiza) o resumo inteligente do lead para o corretor."""
    lead_or_404(db, lead_id, principal, write=True)
    try:
        return generate_summary(db, lead_id)
    except (anthropic.APIError, RuntimeError) as exc:
        raise HTTPException(502, "Não foi possível gerar o resumo agora") from exc


@router.post("/leads/{lead_id}/summary/email", response_model=EmailLogOut)
def email_summary(lead_id: uuid.UUID, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    """Envia o resumo ao corretor por e-mail agora (gera o resumo antes, se ainda não existir)."""
    lead_or_404(db, lead_id, principal, write=True)
    summary = db.scalar(select(Summary).where(Summary.lead_id == lead_id).order_by(Summary.created_at.desc()))
    if summary is None:
        try:
            summary = generate_summary(db, lead_id)
        except (anthropic.APIError, RuntimeError) as exc:
            raise HTTPException(502, "Não foi possível gerar o resumo agora") from exc
    return send_summary_email(db, lead_id, "manual", summary)


@router.get("/appointments", response_model=list[AppointmentOut])
def list_appointments(
    upcoming: bool = True, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)
):
    stmt = select(Appointment, Lead.name).join(Slot).join(Lead, Lead.id == Appointment.lead_id)
    if not principal.sees_all:
        stmt = stmt.where(Appointment.broker_id == principal.broker_id)
    if upcoming:
        stmt = stmt.where(Slot.start_at >= datetime.now(UTC), Appointment.status.in_(("agendado", "confirmado")))
    return [appointment_out(appt, name) for appt, name in db.execute(stmt.order_by(Slot.start_at)).all()]


@router.get("/dashboard/metrics")
def dashboard_metrics(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    """KPIs do dashboard: funil, temperatura, intenção, agendamentos e follow-ups (do corretor, se for o caso)."""
    active = Lead.last_message_at.is_not(None)
    scope = visible_leads(principal)
    if scope is not None:
        active = active & scope
    mine = scope if scope is not None else true()  # filtro extra das contagens que não usam "active"
    own_visits = true() if principal.sees_all else Appointment.broker_id == principal.broker_id

    def count_by(column) -> dict[str, int]:
        return dict(db.execute(select(column, func.count()).where(active).group_by(column)).all())

    by_status = count_by(Lead.status)
    # canal de entrada + transição: quem começou no site ou no chat e continuou no Telegram vira "<canal>_telegram"
    by_channel: dict[str, int] = {}
    has_telegram = Lead.extra.has_key("telegram")
    for channel, telegram, n in db.execute(
        select(Lead.channel, has_telegram, func.count()).where(active).group_by(Lead.channel, has_telegram)
    ).all():
        key = f"{channel}_telegram" if telegram and channel != "telegram" else str(channel)
        by_channel[key] = by_channel.get(key, 0) + n
    total = sum(by_status.values())
    advanced = sum(by_status.get(s, 0) for s in ("qualificado", "agendado", "encaminhado"))
    since = datetime.now(UTC) - timedelta(hours=24)
    return {
        "total_leads": total,
        "leads_24h": db.scalar(select(func.count()).select_from(Lead).where(active, Lead.created_at >= since)),
        "by_status": by_status,
        "by_temperature": count_by(Lead.temperature),
        "by_intent": count_by(Lead.intent),
        "by_channel": by_channel,
        "avg_score": round(db.scalar(select(func.avg(Lead.score)).where(active)) or 0),
        "qualification_rate": round(advanced / total, 3) if total else 0,
        "upcoming_appointments": db.scalar(
            select(func.count())
            .select_from(Appointment)
            .join(Slot)
            .where(Slot.start_at >= datetime.now(UTC), Appointment.status.in_(("agendado", "confirmado")), own_visits)
        ),
        "followups_sent": db.scalar(
            select(func.count())
            .select_from(Message)
            .join(Lead, Lead.id == Message.lead_id)
            .where(Message.role == "followup", mine)
        ),
        "ai_enabled": ai_enabled(),
        "awaiting_followup": db.scalar(
            select(func.count()).select_from(Lead).where(Lead.next_followup_at.is_not(None), mine)
        ),
    }
