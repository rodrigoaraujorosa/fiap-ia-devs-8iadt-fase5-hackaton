"""Agenda de corretores: escolha do responsável, horários livres, reserva e reposição de horários."""

import random
import unicodedata
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Appointment, Broker, Lead, Property, Slot
from app.models.enums import AppointmentKind, AppointmentStatus, BrokerRole, LeadStatus

SLOT_HOURS = range(9, 18)
MIN_NOTICE = timedelta(hours=2)
WEEKDAYS_SHORT = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
ACTIVE = (AppointmentStatus.AGENDADO, AppointmentStatus.CONFIRMADO)


class SchedulingError(Exception):
    """Erro de negócio com mensagem pronta para devolver ao agente."""


def tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def format_slot(start: datetime) -> str:
    local = start.astimezone(tz())
    return f"{WEEKDAYS_SHORT[local.weekday()]}, {local:%d/%m} às {local:%H}h"


def _norm(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def lead_zones(db: Session, lead: Lead, property_id: str | None = None) -> set[str]:
    """Zonas de interesse: a do imóvel escolhido ou as regiões do lead (bairros viram a zona correspondente)."""
    if property_id and (prop := db.get(Property, property_id)):
        return {prop.zone}
    zones = set()
    known_zones = {"zona sul", "zona oeste", "zona norte", "zona leste", "centro"}
    for region in lead.regions or []:
        if _norm(region) in known_zones:
            zones.add(_norm(region))
            continue
        zone = db.scalar(
            select(Property.zone).where(func.lower(Property.neighborhood) == region.lower().strip()).limit(1)
        )
        if zone:
            zones.add(zone)
    return zones


def pick_brokers(db: Session, lead: Lead, kind: str, property_id: str | None = None) -> list[Broker]:
    brokers = db.scalars(select(Broker).where(Broker.active.is_(True))).all()
    if kind == AppointmentKind.REUNIAO and lead.intent == "investimento":
        return [b for b in brokers if b.role == BrokerRole.ESPECIALISTA_INVESTIMENTO]
    corretores = [b for b in brokers if b.role == BrokerRole.CORRETOR]
    zones = lead_zones(db, lead, property_id)
    matching = [b for b in corretores if zones & set(b.zones)]
    return matching or corretores


def free_slots(
    db: Session, brokers: list[Broker], day: date | None = None, period: str | None = None, limit: int = 6
) -> list[Slot]:
    stmt = (
        select(Slot)
        .where(
            Slot.broker_id.in_([b.id for b in brokers]),
            Slot.is_booked.is_(False),
            Slot.start_at >= datetime.now(UTC) + MIN_NOTICE,
        )
        .order_by(Slot.start_at, Slot.broker_id)
    )
    slots = db.scalars(stmt.limit(200)).all()
    if day:
        slots = [s for s in slots if s.start_at.astimezone(tz()).date() == day]
    if period == "manha":
        slots = [s for s in slots if s.start_at.astimezone(tz()).hour < 12]
    elif period == "tarde":
        slots = [s for s in slots if s.start_at.astimezone(tz()).hour >= 12]
    # um horário por início (evita repetir 10h de dois corretores), espalhando pelos dias
    seen, picked = set(), []
    for s in slots:
        if s.start_at not in seen:
            seen.add(s.start_at)
            picked.append(s)
        if len(picked) == limit:
            break
    return picked


def upcoming_appointment(db: Session, lead_id) -> Appointment | None:
    return db.scalar(
        select(Appointment)
        .join(Slot)
        .where(Appointment.lead_id == lead_id, Appointment.status.in_(ACTIVE), Slot.start_at >= datetime.now(UTC))
        .order_by(Slot.start_at)
        .limit(1)
    )


def book(
    db: Session, lead: Lead, slot_id: int, kind: str, property_id: str | None = None, notes: str | None = None
) -> Appointment:
    slot = db.scalar(select(Slot).where(Slot.id == slot_id).with_for_update())  # trava contra agendamento duplo
    if slot is None:
        raise SchedulingError("Horário não encontrado. Liste os horários de novo.")
    if slot.is_booked or slot.start_at < datetime.now(UTC) + MIN_NOTICE:
        raise SchedulingError("Esse horário acabou de ficar indisponível. Ofereça outras opções ao cliente.")
    if property_id and not db.get(Property, property_id):
        property_id = None

    previous = upcoming_appointment(db, lead.id)
    if previous:  # remarcação: libera o horário anterior
        previous.status = AppointmentStatus.CANCELADO
        previous.slot.is_booked = False

    slot.is_booked = True
    appointment = Appointment(
        lead_id=lead.id, broker_id=slot.broker_id, slot_id=slot.id, property_id=property_id, kind=kind, notes=notes
    )
    db.add(appointment)
    lead.status = LeadStatus.AGENDADO
    lead.assigned_broker_id = slot.broker_id
    lead.next_followup_at = None
    db.commit()
    db.refresh(appointment)
    return appointment


def _business_days(start: date, count: int) -> list[date]:
    days, d = [], start
    while len(days) < count:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days.append(d)
    return days


def ensure_future_slots(db: Session, prebooked_ratio: float = 0.0, seed: int | None = None) -> int:
    """Garante horários para os próximos N dias úteis de cada corretor (idempotente)."""
    rng = random.Random(seed)
    brokers = db.scalars(select(Broker).where(Broker.active.is_(True))).all()
    existing = {(broker_id, start) for broker_id, start in db.execute(select(Slot.broker_id, Slot.start_at))}
    created = 0
    for broker in brokers:
        for day in _business_days(datetime.now(tz()).date(), get_settings().slot_days_ahead):
            for hour in SLOT_HOURS:
                start = datetime.combine(day, time(hour), tzinfo=tz())
                if (broker.id, start) in existing:
                    continue
                db.add(
                    Slot(
                        broker_id=broker.id,
                        start_at=start,
                        end_at=start + timedelta(hours=1),
                        is_booked=rng.random() < prebooked_ratio,
                    )
                )
                created += 1
    db.commit()
    return created
