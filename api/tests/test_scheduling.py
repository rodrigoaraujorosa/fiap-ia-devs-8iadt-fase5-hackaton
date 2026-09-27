"""Agenda: escolha do corretor, horários livres, reserva, conflito e remarcação (banco real, sem LLM)."""

import pytest
from sqlalchemy import select

from app.models import Broker, Lead, Slot
from app.models.enums import AppointmentStatus, BrokerRole, LeadStatus
from app.services import scheduling
from app.services.property_search import OFFICE


@pytest.fixture
def lead(db):
    lead = Lead(channel="web", regions=["zona sul"], extra={}, intent="compra", status=LeadStatus.QUALIFICADO)
    db.add(lead)
    db.commit()
    yield lead
    for appt in scheduling_appointments(db, lead):
        appt.slot.is_booked = False
    db.delete(lead)
    db.commit()


def scheduling_appointments(db, lead):
    from app.models import Appointment

    return db.scalars(select(Appointment).where(Appointment.lead_id == lead.id)).all()


def test_pick_brokers_by_specialty_and_role(db, lead):
    """Comercial: o corretor é escolhido pela especialidade (tipo de imóvel); investidor vai para o especialista."""
    lead.property_type = "galpão"
    assert [b.name for b in scheduling.pick_brokers(db, lead, "visita")] == ["Paulo Nogueira"]

    home = scheduling.pick_brokers(db, lead, "visita", property_id="IMV-070")  # o imóvel escolhido manda
    assert [b.name for b in home] == ["Juliana Pereira"]  # apartamento: residencial de alto padrão

    lead.property_type = "escritório"  # sinônimo: conjunto, andar ou laje
    office = scheduling.pick_brokers(db, lead, "visita")
    assert office and all(b.role == BrokerRole.CORRETOR for b in office)
    assert all(set(OFFICE) & set(b.specialties) for b in office)

    lead.intent = "investimento"
    specialists = scheduling.pick_brokers(db, lead, "reuniao")
    assert [b.role for b in specialists] == [BrokerRole.ESPECIALISTA_INVESTIMENTO]
    db.rollback()


def test_free_slots_respect_period(db, lead):
    brokers = scheduling.pick_brokers(db, lead, "visita")
    afternoon = scheduling.free_slots(db, brokers, period="tarde")
    assert afternoon and all(s.start_at.astimezone(scheduling.tz()).hour >= 12 for s in afternoon)
    assert all(not s.is_booked for s in afternoon)
    assert len({s.start_at for s in afternoon}) == len(afternoon)  # sem horários repetidos


def test_book_conflict_and_reschedule(db, lead):
    brokers = scheduling.pick_brokers(db, lead, "visita")
    first, second = scheduling.free_slots(db, brokers, limit=2)

    appt = scheduling.book(db, lead, first.id, "visita", "IMV-001")
    assert lead.status == LeadStatus.AGENDADO
    assert lead.assigned_broker_id == first.broker_id
    assert db.get(Slot, first.id).is_booked

    with pytest.raises(scheduling.SchedulingError):  # mesmo horário não pode ser reservado duas vezes
        scheduling.book(db, lead, first.id, "visita")

    new_appt = scheduling.book(db, lead, second.id, "visita")  # remarcação libera o horário anterior
    db.refresh(appt)
    assert appt.status == AppointmentStatus.CANCELADO
    assert not db.get(Slot, first.id).is_booked
    assert scheduling.upcoming_appointment(db, lead.id).id == new_appt.id


def test_ensure_future_slots_is_idempotent(db):
    scheduling.ensure_future_slots(db)
    assert scheduling.ensure_future_slots(db) == 0
    active = db.scalars(select(Broker).where(Broker.active.is_(True))).all()
    assert active
