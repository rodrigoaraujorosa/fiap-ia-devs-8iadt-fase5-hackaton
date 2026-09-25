"""Dados de demonstração: limpa leads, conversas e agenda e recria um cenário realista (data/demo_leads.json).

Imóveis, embeddings e corretores são mantidos (caros de recalcular). A memória dos agentes (checkpointer) é
recriada com as mesmas conversas, então follow-ups e novas mensagens continuam com contexto.
"""

import json
import logging
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.agents.qualification import compute_score, temperature_for
from app.agents.runtime import get_graph
from app.core.config import get_settings
from app.models import Appointment, Broker, Lead, Message, Slot, Summary
from app.models.enums import Channel, MessageRole
from app.services.scheduling import _business_days, book, ensure_future_slots, format_slot, tz
from app.services.summary import BrokerSummary, _render

log = logging.getLogger(__name__)

PREBOOKED_RATIO = 0.25  # parte da agenda já ocupada, mais realista
SLOT_SEED = 7
CHECKPOINT_TABLES = ("checkpoints", "checkpoint_blobs", "checkpoint_writes")
HANDOFF_NOTICE_DEADLINE = "em até 1 hora útil"


def load_demo_leads() -> list[dict]:
    return json.loads((get_settings().data_dir / "demo_leads.json").read_text(encoding="utf-8"))


def _clear(db: Session) -> int:
    db.execute(text("TRUNCATE appointments, summaries, messages, leads RESTART IDENTITY CASCADE"))
    existing = set(db.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")))
    if checkpoints := [t for t in CHECKPOINT_TABLES if t in existing]:
        db.execute(text(f"TRUNCATE {', '.join(checkpoints)}"))
    db.execute(delete(Slot))
    db.commit()
    return ensure_future_slots(db, prebooked_ratio=PREBOOKED_RATIO, seed=SLOT_SEED)


def _book(db: Session, lead: Lead, spec: dict, brokers: dict[str, Broker]) -> Appointment:
    day = _business_days(datetime.now(tz()).date(), spec["business_days_ahead"])[-1]
    target = datetime.combine(day, time(spec["hour"]), tzinfo=tz())
    slot = db.scalar(
        select(Slot)
        .where(Slot.broker_id == brokers[spec["broker"]].id, Slot.is_booked.is_(False), Slot.start_at >= target)
        .order_by(Slot.start_at)
    )
    return book(db, lead, slot.id, spec["kind"], spec.get("property_id"), spec.get("notes"))


def _message_meta(m: dict, lead: Lead, appointment: Appointment | None) -> dict:
    if m["role"] == MessageRole.FOLLOWUP:
        return {"attempt": m["attempt"]}
    if m["role"] == MessageRole.USER:
        return {}
    meta: dict = {"property_ids": m.get("property_ids", [])}
    if m.get("appointment") and appointment:
        meta["appointment"] = {
            "tipo": appointment.kind,
            "quando": format_slot(appointment.slot.start_at),
            "com": appointment.broker.name,
            "imovel": appointment.property_id,
        }
    if m.get("handoff") and lead.assigned_broker:
        meta["handoff"] = {"corretor": lead.assigned_broker.name, "prazo_retorno": HANDOFF_NOTICE_DEADLINE}
    return meta


def _create_lead(db: Session, spec: dict, brokers: dict[str, Broker], now: datetime) -> Lead:
    msgs = spec["messages"]

    def at(m: dict) -> datetime:
        return now - timedelta(minutes=m["minutes_ago"])

    lead = Lead(channel=Channel.WEB, name=spec.get("name"), phone=spec["phone"],
                **{"regions": [], "extra": {}, **spec["profile"]})  # fmt: skip
    lead.created_at = at(msgs[0])
    lead.last_message_at = at(msgs[-1])
    lead.last_lead_message_at = max(at(m) for m in msgs if m["role"] == MessageRole.USER)
    lead.score = compute_score(lead)
    lead.temperature = temperature_for(lead.score)
    lead.status = spec["status"]
    if broker := spec.get("broker"):
        lead.assigned_broker_id = brokers[broker].id
    followup = spec.get("followup") or {}
    lead.followup_count = followup.get("count", 0)
    if "due_in_minutes" in followup:  # o job de follow-up vai disparar ao vivo durante a demo
        lead.next_followup_at = now + timedelta(minutes=followup["due_in_minutes"])
    db.add(lead)
    db.flush()

    appointment = _book(db, lead, spec["appointment"], brokers) if spec.get("appointment") else None
    db.refresh(lead)
    for m in msgs:
        agent = m.get("agent") or ("follow_up" if m["role"] == MessageRole.FOLLOWUP else None)
        db.add(Message(lead_id=lead.id, role=m["role"], content=m["content"], agent=agent,
                       meta=_message_meta(m, lead, appointment), created_at=at(m)))  # fmt: skip
    if spec.get("summary"):
        summary = BrokerSummary.model_validate(spec["summary"])
        db.add(Summary(lead_id=lead.id, content=summary.model_dump(), text=_render(summary, lead),
                       created_at=lead.last_message_at + timedelta(minutes=1)))  # fmt: skip
    db.commit()
    return lead


def _write_memory(lead: Lead, spec: dict) -> None:
    """Grava a conversa na memória do agente (mesmo thread_id que o chat usa)."""
    history = [
        {"role": "user" if m["role"] == MessageRole.USER else "assistant", "content": m["content"]}
        for m in spec["messages"]
    ]
    config = {"configurable": {"thread_id": str(lead.id)}}
    get_graph().update_state(config, {"lead_id": str(lead.id), "messages": history}, as_node=spec["route"])


def reset_demo(db: Session) -> dict:
    slots = _clear(db)
    brokers = {b.email: b for b in db.scalars(select(Broker))}
    now = datetime.now(UTC)
    leads = []
    for spec in load_demo_leads():
        lead = _create_lead(db, spec, brokers, now)
        _write_memory(lead, spec)
        leads.append(lead)
    appointments = db.scalar(select(func.count()).select_from(Appointment))
    log.info("Demo recriada: %s leads, %s horários", len(leads), slots)
    return {"leads": len(leads), "appointments": appointments, "slots": slots}
