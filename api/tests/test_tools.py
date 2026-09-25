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
    blocked = run_tool(ctx, "buscar_imoveis", {"purpose": "aluguel", "max_price": 2000})
    assert blocked.is_error and "comprar, alugar ou investir" in blocked.content
    assert not blocked.properties

    lead.intent = "aluguel"
    db.commit()
    allowed = run_tool(ctx, "buscar_imoveis", {"purpose": "aluguel", "max_price": 2000})
    assert not allowed.is_error and allowed.properties
