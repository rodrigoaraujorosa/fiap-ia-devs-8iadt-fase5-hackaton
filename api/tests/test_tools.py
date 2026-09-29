"""Ferramentas do agente: travas determinísticas que não dependem do LLM."""

import pytest

from app.agents.tools import ToolContext, run_tool
from app.models import Lead


@pytest.fixture
def lead(db):
    lead = Lead(channel="web", regions=[], extra={}, intent="indefinido")
    db.add(lead)
    db.commit()
    yield lead
    db.delete(lead)
    db.commit()


def test_search_blocked_until_client_states_purpose(db, lead):
    ctx = ToolContext(db=db, lead_id=lead.id)
    blocked = run_tool(ctx, "buscar_imoveis", {"purpose": "aluguel", "max_price": 20000})
    assert blocked.is_error and "comprar, alugar ou investir" in blocked.content
    assert not blocked.properties

    lead.intent = "aluguel"
    db.commit()
    allowed = run_tool(ctx, "buscar_imoveis", {"purpose": "aluguel", "max_price": 20000})
    assert not allowed.is_error and allowed.properties


def test_booking_requires_phone_unless_declined(db, lead, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.agents import tools
    from app.models import Appointment, Slot

    monkeypatch.setattr(tools, "submit_summary", lambda *a: None)  # sem resumo (LLM) nem e-mail
    ctx = ToolContext(db=db, lead_id=lead.id)
    future = datetime.now(UTC) + timedelta(hours=2)  # o banco de testes é reaproveitado: horários antigos já passaram
    slot = db.scalars(select(Slot).where(Slot.is_booked.is_(False), Slot.start_at > future).limit(1)).first()
    blocked = run_tool(ctx, "agendar", {"slot_id": slot.id, "tipo": "visita"})
    assert blocked.is_error and "telefone" in blocked.content and not blocked.event
    assert not db.get(Slot, slot.id).is_booked

    lead.extra = {"phone_declined": True}  # o cliente se recusou: agenda sem telefone
    db.commit()
    booked = run_tool(ctx, "agendar", {"slot_id": slot.id, "tipo": "visita"})
    assert not booked.is_error and booked.event["type"] == "appointment"
    for appt in db.scalars(select(Appointment).where(Appointment.lead_id == lead.id)):
        appt.slot.is_booked = False
        db.delete(appt)
    db.commit()
