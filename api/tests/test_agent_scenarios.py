"""Cenários do enunciado rodando o agente de verdade (Claude + banco).

Custam tokens, então só rodam com RUN_LLM_TESTS=1:
    RUN_LLM_TESTS=1 uv run pytest tests/test_agent_scenarios.py -v
"""

import os

import pytest

from app.models import Lead
from app.models.enums import Temperature
from app.services.chat import run_turn

pytestmark = pytest.mark.skipif(os.getenv("RUN_LLM_TESTS") != "1", reason="defina RUN_LLM_TESTS=1")


def _new_lead(db) -> Lead:
    lead = Lead(channel="web", regions=[], extra={})
    db.add(lead)
    db.commit()
    return lead


def _talk(lead_id, text) -> list[dict]:
    events = list(run_turn(lead_id, text))
    assert events[-1]["type"] == "done" and events[-1]["reply"], events
    return events


def test_exemplo_1_compra_zona_sul(db):
    lead = _new_lead(db)
    first = _talk(lead.id, "Estou procurando apartamento na zona sul.")
    assert first[0]["type"] == "analysis"

    second = _talk(lead.id, "É pra comprar. Somos um casal com 2 filhos e podemos pagar até 1,2 milhão")
    events = _talk(lead.id, "Me chamo Ricardo, precisamos mudar em 3 semanas, vamos financiar")

    tools = [e for e in first + second + events if e["type"] == "tool" and e["status"] == "start"]
    assert any(t["name"] == "buscar_imoveis" for t in tools), "deveria buscar imóveis ao longo da conversa"

    final = events[-1]["lead"]
    assert final["name"] == "Ricardo"
    assert final["intent"] == "compra"
    assert "zona sul" in [r.lower() for r in final["regions"]]
    assert final["budget_max"] == 1_200_000
    assert final["bedrooms"] and final["bedrooms"] >= 2
    assert final["urgency"] == "alta"
    assert final["temperature"] == Temperature.QUENTE


def test_exemplo_2_investidor(db):
    lead = _new_lead(db)
    events = _talk(lead.id, "Quero investir em imóveis para renda.")
    assert next(e for e in events if e["type"] == "agent")["agent"] == "investimento"

    _talk(lead.id, "Tenho 400 mil à vista, seria meu primeiro imóvel pra alugar. Sou a Fernanda")
    events = _talk(lead.id, "Espero uns 0,6% ao mês de retorno")

    final = events[-1]["lead"]
    assert final["intent"] == "investimento"
    assert final["ticket"] == 400_000
    assert final["expected_return"]
    assert final["investor_profile"]
    search = [e for e in events if e["type"] == "tool" and e["name"] == "buscar_imoveis" and e["status"] == "start"]
    if search:  # quando busca, deve considerar rentabilidade ou o ticket
        args = search[0]["input"]
        assert args.get("min_yield") or args.get("max_price")


def test_memoria_entre_turnos(db):
    lead = _new_lead(db)
    _talk(lead.id, "Oi, meu nome é Juliana e tenho um gato chamado Frajola")
    events = _talk(lead.id, "Qual é o nome do meu gato?")
    assert "frajola" in events[-1]["reply"].lower()
