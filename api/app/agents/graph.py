"""Grafo multiagente do SDR (LangGraph) com chamadas ao Claude pelo SDK oficial da Anthropic.

    START → supervisor (Haiku: extrai perfil, atualiza CRM/score, escolhe o agente)
          → compra_aluguel | investimento | agendamento (Sonnet: conversa + tools, com streaming)
          → END

A memória da conversa é o estado do grafo, persistido no Postgres pelo checkpointer (thread_id = id do lead).
Eventos para a interface (tokens, tools, imóveis, agendamentos) saem pelo stream "custom" do LangGraph.
"""

import logging
import operator
import re
import uuid
from datetime import datetime
from typing import Annotated, Any, TypedDict
from zoneinfo import ZoneInfo

import anthropic
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.agents.llm import claude, transcript, usage_details
from app.agents.prompts import lead_context, system_prompt
from app.agents.qualification import LeadAnalysis, apply_analysis, refresh_funnel
from app.agents.tools import TOOLSETS, ToolContext, run_tool
from app.core import observability
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Lead, Property
from app.models.enums import Intent
from app.services.scheduling import format_slot, upcoming_appointment

log = logging.getLogger(__name__)

AGENTS = ("compra_aluguel", "investimento", "agendamento")
MAX_TOOL_ROUNDS = 6
PROPERTY_CODE = re.compile(r"IMV-\d+", re.IGNORECASE)
FALLBACK_REPLY = "Desculpe, tive uma instabilidade aqui. Pode repetir sua última mensagem, por favor?"
REFUSAL_REPLY = "Esse assunto eu não consigo tratar por aqui, mas posso te ajudar a encontrar o imóvel ideal. 🙂"

ANALYST_PROMPT = """\
Você é o supervisor de um time de SDRs de uma imobiliária em São Paulo. Leia a conversa entre o cliente e a SDR \
e extraia o perfil do cliente para o CRM.

Regras:
- Registre apenas o que o cliente disse (ou confirmou). Não invente nem deduza valores que ele não deu.
- Considere a conversa inteira; se o cliente mudou de ideia, use a informação mais recente.
- Valores em reais como inteiros: "900 mil" → 900000; "1,2 milhão" → 1200000; "até 4 mil de aluguel" → budget_max 4000.
- "Até 2 mil" é budget_max 2000 e budget_min 0. Nunca use o preço de um imóvel mostrado pela SDR como orçamento.
- Regiões: só as zonas ou bairros que o próprio cliente escreveu. Bairros de imóveis que a SDR mostrou NÃO entram, \
mesmo que o cliente goste do imóvel (registre o imóvel preferido em notes). Se o cliente disse que não tem \
preferência de região, use ["sem preferência"]. Nunca remova a região pedida originalmente, a menos que o \
cliente desista dela. Normalize zonas como "zona sul", "zona oeste", "zona norte", "zona leste", "centro"; \
mantenha bairros com o nome próprio (ex.: "Moema").
- intent: só com base no que o cliente declarou. "investimento" quando o objetivo é renda ou valorização (mesmo \
que vá comprar); "compra" para morar; "aluguel" para alugar para si. Se ele ainda não disse se quer comprar, \
alugar ou investir, use "indefinido" — nunca deduza pela faixa de valor ("até 2 mil" não significa aluguel) \
nem por ele ter gostado de imóveis que a SDR buscou.
- intent_evidence: copie letra por letra o trecho do cliente que declara a finalidade; sem ele, o intent \
é descartado.
- phone: telefone ou WhatsApp que o cliente digitou. declined_phone "sim" só se a SDR pediu e ele recusou.
- urgency: calcule pelo prazo em relação à data de hoje (até 1 mês = alta; 1 a 6 meses = media; mais que isso \
ou sem prazo = baixa). "desconhecida" se o cliente ainda não falou de prazo.
- route (quem responde a última mensagem do cliente):
  - "agendamento" se na última mensagem o cliente pede ou aceita marcar visita/reunião, indica dia ou horário, \
escolhe uma das opções de horário oferecidas, ou quer remarcar;
  - senão "investimento" se o intent for investimento;
  - senão "compra_aluguel".
  Se já existe agendamento e o cliente só faz outras perguntas, não use "agendamento".
"""


class AgentState(TypedDict):
    lead_id: str
    messages: Annotated[list[dict[str, Any]], operator.add]  # histórico no formato da Messages API
    route: str
    missing: list[str]


def _appointment_text(db, lead_id) -> str | None:
    appt = upcoming_appointment(db, lead_id)
    if not appt:
        return None
    text = f"{appt.kind} com {appt.broker.name} em {format_slot(appt.slot.start_at)}"
    return f"{text} (imóvel {appt.property_id})" if appt.property_id else text


def _viewing(db, lead: Lead) -> Property | None:
    """Imóvel da página em que o visitante está (widget no site da imobiliária)."""
    code = (lead.extra or {}).get("viewing")
    return db.get(Property, code) if code else None


# ---------------------------------------------------------------- supervisor


def _client_text(messages: list[dict]) -> str:
    """Só o que o cliente escreveu (sem resultados de ferramentas), para conferir as citações do analisador."""
    parts = []
    for m in messages:
        if m["role"] != "user":
            continue
        content = m["content"]
        if isinstance(content, str):
            parts.append(content)
        else:
            parts.extend(b["text"] for b in content if b.get("type") == "text")
    return "\n".join(parts)


def supervisor(state: AgentState) -> dict:
    settings = get_settings()
    writer = get_stream_writer()
    with SessionLocal() as db, observability.observation("supervisor", as_type="chain") as span:
        lead = db.get(Lead, uuid.UUID(state["lead_id"]))
        route = "investimento" if lead.intent == Intent.INVESTIMENTO else "compra_aluguel"
        today = datetime.now(ZoneInfo(settings.timezone))
        crm = f"Etapa atual do lead: {lead.status}. Agendamento: {_appointment_text(db, lead.id) or 'nenhum'}."
        prompt = f"{crm}\n\n<conversa>\n{transcript(state['messages'])}\n</conversa>"
        try:
            with observability.observation(
                "extrair_perfil", as_type="generation", model=settings.llm_fast_model, input=prompt
            ) as gen:
                response = claude().messages.parse(
                    model=settings.llm_fast_model,
                    max_tokens=1024,
                    system=f"{ANALYST_PROMPT}\nData de hoje: {today:%d/%m/%Y}.",
                    messages=[{"role": "user", "content": prompt}],
                    output_format=LeadAnalysis,
                )
                gen.update(output=response.parsed_output, usage_details=usage_details(response))
            analysis = response.parsed_output
            if analysis:
                apply_analysis(lead, analysis, _client_text(state["messages"]))
                if analysis.route == "agendamento":
                    route = "agendamento"
                elif lead.intent == Intent.INVESTIMENTO:
                    route = "investimento"
                else:
                    route = "compra_aluguel"
        except anthropic.APIError:
            log.exception("Supervisor falhou; mantendo perfil anterior")
        missing = refresh_funnel(lead)
        db.commit()
        analysis_event = {
            "type": "analysis",
            "route": route,
            "intent": lead.intent,
            "score": lead.score,
            "temperature": lead.temperature,
            "status": lead.status,
            "missing": missing,
        }
        span.update(output=analysis_event)
        writer(analysis_event)
    return {"route": route, "missing": missing}


# ---------------------------------------------------------------- agentes


def _assistant_turn(content: list[Any]) -> dict[str, Any]:
    return {"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in content]}


def _call_claude(route: str, system: list[dict], messages: list[dict], writer, new_bubble: bool):
    """Uma chamada ao modelo principal, com streaming dos tokens para a interface.

    new_bubble: já houve texto antes (numa rodada com ferramenta); o novo texto vira outro balão.
    """
    settings = get_settings()
    started_text = False
    with observability.observation(
        f"{route}.llm", as_type="generation", model=settings.llm_main_model, input=messages[-1]["content"]
    ) as gen:
        with claude().messages.stream(
            model=settings.llm_main_model,
            max_tokens=settings.llm_agent_max_tokens,
            system=system,
            tools=TOOLSETS[route],
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": settings.llm_agent_effort},
        ) as stream:
            for event in stream:
                if event.type == "text":
                    if not started_text and new_bubble:
                        writer({"type": "bubble"})
                    started_text = True
                    writer({"type": "token", "text": event.text})
            response = stream.get_final_message()
        gen.update(
            output=[b.model_dump(exclude_none=True) for b in response.content if b.type != "thinking"],
            usage_details=usage_details(response),
            metadata={"stop_reason": response.stop_reason},
        )
    return response


def make_agent(route: str):
    def agent(state: AgentState) -> dict:
        writer = get_stream_writer()
        writer({"type": "agent", "agent": route})

        with SessionLocal() as db, observability.observation(route, as_type="agent") as span:
            lead_id = uuid.UUID(state["lead_id"])
            lead = db.get(Lead, lead_id)
            ctx = ToolContext(db=db, lead_id=lead_id)
            system = [
                {"type": "text", "text": system_prompt(route), "cache_control": {"type": "ephemeral"}},
                {
                    "type": "text",
                    "text": lead_context(lead, state["missing"], _appointment_text(db, lead_id), _viewing(db, lead)),
                },  # fmt: skip
            ]
            history = list(state["messages"])
            new_messages: list[dict[str, Any]] = []
            reply_parts: list[str] = []
            property_ids: list[str] = []

            for _ in range(MAX_TOOL_ROUNDS):
                try:
                    response = _call_claude(route, system, history + new_messages, writer, bool(reply_parts))
                except (anthropic.APIError, ValueError):
                    log.exception("Falha na chamada do agente %s", route)
                    if reply_parts:
                        writer({"type": "bubble"})
                    reply_parts.append(FALLBACK_REPLY)
                    writer({"type": "token", "text": FALLBACK_REPLY})
                    new_messages.append({"role": "assistant", "content": FALLBACK_REPLY})
                    break

                text = "".join(b.text for b in response.content if b.type == "text").strip()
                if text:
                    reply_parts.append(text)

                if response.stop_reason == "refusal":
                    if reply_parts:
                        writer({"type": "bubble"})
                    reply_parts.append(REFUSAL_REPLY)
                    writer({"type": "token", "text": REFUSAL_REPLY})
                    new_messages.append({"role": "assistant", "content": REFUSAL_REPLY})
                    break

                tool_uses = [b for b in response.content if b.type == "tool_use"]
                if response.stop_reason != "tool_use" or not tool_uses:
                    # fim do turno; nunca deixar tool_use sem tool_result no histórico
                    kept = [b for b in response.content if b.type != "tool_use"]
                    if kept:
                        new_messages.append(_assistant_turn(kept))
                    break

                new_messages.append(_assistant_turn(response.content))
                results = []
                for block in tool_uses:
                    writer({"type": "tool", "name": block.name, "input": block.input, "status": "start"})
                    with observability.observation(block.name, as_type="tool", input=block.input) as tool_obs:
                        outcome = run_tool(ctx, block.name, block.input)
                        tool_obs.update(output=outcome.content, level="ERROR" if outcome.is_error else "DEFAULT")
                    writer({"type": "tool", "name": block.name, "status": "error" if outcome.is_error else "done"})
                    if outcome.properties:
                        property_ids.extend(p["id"] for p in outcome.properties)
                        writer({"type": "properties", "items": outcome.properties})
                    if outcome.event:
                        writer(outcome.event)
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": outcome.content,
                            "is_error": outcome.is_error,
                        }
                    )
                new_messages.append({"role": "user", "content": results})

            reply = "\n\n".join(reply_parts)
            # cards só dos imóveis que a Laris citou no texto (a busca pode ter trazido mais), na ordem citada
            cited = dict.fromkeys(code.upper() for code in PROPERTY_CODE.findall(reply))
            shown = [code for code in cited if code in property_ids]
            span.update(output=reply)
            writer({"type": "reply", "text": reply, "bubbles": reply_parts, "property_ids": shown})
        return {"messages": new_messages}

    agent.__name__ = route
    return agent


# ---------------------------------------------------------------- grafo


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    builder = StateGraph(AgentState)
    builder.add_node("supervisor", supervisor)
    for route in AGENTS:
        builder.add_node(route, make_agent(route))
        builder.add_edge(route, END)
    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", lambda s: s["route"], list(AGENTS))
    return builder.compile(checkpointer=checkpointer)
