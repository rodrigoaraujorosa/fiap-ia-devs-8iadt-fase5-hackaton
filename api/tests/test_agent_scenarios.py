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
    third = _talk(lead.id, "Me chamo Ricardo, precisamos mudar em 3 semanas, vamos financiar")
    # quartos não são deduzidos de "2 filhos": o cliente informa quando a Laris pergunta
    events = _talk(lead.id, "Precisamos de 3 quartos")

    tools = [e for e in first + second + third + events if e["type"] == "tool" and e["status"] == "start"]
    assert any(t["name"] == "buscar_imoveis" for t in tools), "deveria buscar imóveis ao longo da conversa"

    final = events[-1]["lead"]
    assert final["name"] == "Ricardo"
    assert final["intent"] == "compra"
    assert "zona sul" in [r.lower() for r in final["regions"]]
    assert final["budget_max"] == 1_200_000
    assert final["bedrooms"] == 3
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


def test_agendamento_de_visita(db):
    lead = _new_lead(db)
    _talk(lead.id, "Quero alugar um studio mobiliado no centro, até 3 mil. Sou a Paula, preciso mudar em 2 semanas")
    events = _talk(lead.id, "Quero visitar o primeiro que você mostrou. Pode ser no próximo dia útil, de tarde?")
    assert any(e["type"] == "agent" and e["agent"] == "agendamento" for e in events)
    if not any(e["type"] == "appointment" for e in events):  # o agente pode primeiro oferecer opções
        events = _talk(lead.id, "Pode ser o primeiro horário que você falou")
    appointment = next(e for e in events if e["type"] == "appointment")
    assert appointment["tipo"] == "visita" and appointment["com"]
    assert events[-1]["lead"]["status"] == "agendado"


def test_exemplo_3_follow_up_com_contexto(db):
    from app.jobs.followup import send_followup

    lead = _new_lead(db)
    _talk(lead.id, "Oi, sou o Bruno e quero alugar um apê de 2 quartos na zona oeste até 5 mil")
    db.refresh(lead)
    text = send_followup(lead.id, 0, lead.last_lead_message_at)
    assert text and "bruno" in text.lower()
    events = _talk(lead.id, "Oi, voltei! O que você tinha me perguntado mesmo?")
    assert events[-1]["reply"]


def test_conversa_rodrigo_regressao(db):
    """Conversa real que expôs problemas: finalidade presumida, telefone nunca pedido e cards a mais."""
    lead = _new_lead(db)

    def searched(events):
        return [e for e in events if e["type"] == "tool" and e["name"] == "buscar_imoveis" and e["status"] == "done"]

    first = _talk(lead.id, "Oi, boa tarde, procuro um apartamento próximo ao metro, sou solteiro. "
                           "Não tenho preferência pela região.")  # fmt: skip
    second = _talk(lead.id, "Meu nome é Rodrigo, e a faixa de preço é até 2 mil reais")
    # sem dizer se é compra ou aluguel: não pode presumir pelo valor, precisa perguntar
    assert second[-1]["lead"]["intent"] == "indefinido"
    assert not searched(first + second), "não deveria buscar antes de saber a finalidade"
    assert any(w in second[-1]["reply"].lower() for w in ("compr", "alug")), second[-1]["reply"]

    third = _talk(lead.id, "É para alugar")
    final = third[-1]
    assert searched(third)
    assert final["property_ids"], "studios cabem em R$ 2 mil e devem aparecer como apartamento"
    assert all(code in final["reply"].upper() for code in final["property_ids"])  # cards = imóveis citados
    assert len(final["property_ids"]) <= 3
    profile = final["lead"]
    assert profile["intent"] == "aluguel" and profile["budget_max"] == 2000
    assert not profile["budget_min"], "'até 2 mil' não tem mínimo"
    assert [r.lower() for r in profile["regions"]] in ([], ["sem preferência"]), profile["regions"]

    events = _talk(lead.id, "Gostei da primeira opção, quero visitar na próxima terça à tarde")
    replies = events[-1]["reply"].lower()
    if not any(e["type"] == "appointment" for e in events):
        events = _talk(lead.id, "Pode ser o primeiro horário. Meu WhatsApp é 11 98888-7777")
        replies += " " + events[-1]["reply"].lower()
    else:
        events = _talk(lead.id, "Meu WhatsApp é 11 98888-7777")
    assert any(w in replies for w in ("whatsapp", "telefone", "contato")), "deveria pedir o telefone ao agendar"
    assert events[-1]["lead"]["phone"] == "+55 11 98888-7777"
