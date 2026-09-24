"""Grafo multiagente do SDR (LangGraph) com chamadas ao Claude pelo SDK oficial da Anthropic.

    START → supervisor (Haiku: extrai perfil, atualiza CRM/score, escolhe especialista)
          → compra_aluguel | investimento (Sonnet: conversa + tools, com streaming)
          → END

A memória da conversa é o estado do grafo, persistido no Postgres pelo checkpointer (thread_id = id do lead).
Eventos para a interface (tokens, tools, imóveis) saem pelo stream "custom" do LangGraph.
"""

import logging
import operator
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any, TypedDict
from zoneinfo import ZoneInfo

import anthropic
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.agents.prompts import lead_context, system_prompt
from app.agents.qualification import LeadAnalysis, apply_analysis, refresh_funnel
from app.agents.tools import TOOLS, run_tool
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Lead
from app.models.enums import Intent

log = logging.getLogger(__name__)

SPECIALISTS = ("compra_aluguel", "investimento")
MAX_TOOL_ROUNDS = 6
FALLBACK_REPLY = "Desculpe, tive uma instabilidade aqui. Pode repetir sua última mensagem, por favor?"
REFUSAL_REPLY = "Esse assunto eu não consigo tratar por aqui, mas posso te ajudar a encontrar o imóvel ideal. 🙂"

ANALYST_PROMPT = """\
Você é o supervisor de um time de SDRs de uma imobiliária em São Paulo. Leia a conversa entre o cliente e a SDR \
e extraia o perfil do cliente para o CRM.

Regras:
- Registre apenas o que o cliente disse (ou confirmou). Não invente nem deduza valores que ele não deu.
- Considere a conversa inteira; se o cliente mudou de ideia, use a informação mais recente.
- Valores em reais como inteiros: "900 mil" → 900000; "1,2 milhão" → 1200000; "até 4 mil de aluguel" → budget_max 4000.
- Regiões: só as que o cliente pediu ou aceitou (não os bairros dos imóveis que a SDR apenas mostrou). \
Normalize zonas como "zona sul", "zona oeste", "zona norte", "zona leste", "centro"; mantenha bairros \
com o nome próprio (ex.: "Moema").
- intent: "investimento" quando o objetivo é renda ou valorização (mesmo que vá comprar); "compra" para morar; \
"aluguel" para alugar para si; "indefinido" se ainda não ficou claro.
- urgency: calcule pelo prazo em relação à data de hoje (até 1 mês = alta; 1 a 6 meses = media; mais que isso \
ou sem prazo = baixa). "desconhecida" se o cliente ainda não falou de prazo.
- route: "investimento" se intent for investimento; caso contrário "compra_aluguel".
"""


class AgentState(TypedDict):
    lead_id: str
    messages: Annotated[list[dict[str, Any]], operator.add]  # histórico no formato da Messages API
    route: str
    missing: list[str]


@lru_cache
def claude() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


def _text_of(message: dict[str, Any]) -> str:
    content = message["content"]
    if isinstance(content, str):
        return content
    return " ".join(b["text"] for b in content if b.get("type") == "text")


def _transcript(messages: list[dict[str, Any]], limit: int = 14) -> str:
    lines = []
    for m in messages[-limit:]:
        text = _text_of(m).strip()
        if text:
            lines.append(f"{'Cliente' if m['role'] == 'user' else 'SDR'}: {text}")
    return "\n".join(lines)


def _default_route(lead: Lead) -> str:
    return "investimento" if lead.intent == Intent.INVESTIMENTO else "compra_aluguel"


# ---------------------------------------------------------------- nós


def supervisor(state: AgentState) -> dict:
    settings = get_settings()
    writer = get_stream_writer()
    with SessionLocal() as db:
        lead = db.get(Lead, uuid.UUID(state["lead_id"]))
        route = _default_route(lead)
        try:
            response = claude().messages.parse(
                model=settings.llm_fast_model,
                max_tokens=1024,
                system=f"{ANALYST_PROMPT}\nData de hoje: {datetime.now(ZoneInfo('America/Sao_Paulo')):%d/%m/%Y}.",
                messages=[{"role": "user", "content": f"<conversa>\n{_transcript(state['messages'])}\n</conversa>"}],
                output_format=LeadAnalysis,
            )
            analysis = response.parsed_output
            if analysis:
                apply_analysis(lead, analysis)
                route = "investimento" if lead.intent == Intent.INVESTIMENTO else analysis.route
        except anthropic.APIError:
            log.exception("Supervisor falhou; mantendo perfil anterior")
        missing = refresh_funnel(lead)
        db.commit()
        writer(
            {
                "type": "analysis",
                "route": route,
                "intent": lead.intent,
                "score": lead.score,
                "temperature": lead.temperature,
                "status": lead.status,
                "missing": missing,
            }
        )
    return {"route": route, "missing": missing}


def _assistant_turn(content: list[Any]) -> dict[str, Any]:
    return {"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in content]}


def make_specialist(route: str):
    def specialist(state: AgentState) -> dict:
        settings = get_settings()
        writer = get_stream_writer()
        writer({"type": "agent", "agent": route})

        with SessionLocal() as db:
            lead = db.get(Lead, uuid.UUID(state["lead_id"]))
            system = [
                {"type": "text", "text": system_prompt(route), "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": lead_context(lead, state["missing"])},
            ]
            history = list(state["messages"])
            new_messages: list[dict[str, Any]] = []
            reply_parts: list[str] = []
            property_ids: list[str] = []

            for _ in range(MAX_TOOL_ROUNDS):
                started_text = False
                try:
                    with claude().messages.stream(
                        model=settings.llm_main_model,
                        max_tokens=settings.llm_agent_max_tokens,
                        system=system,
                        tools=TOOLS,
                        messages=history + new_messages,
                        thinking={"type": "adaptive"},
                        output_config={"effort": settings.llm_agent_effort},
                    ) as stream:
                        for event in stream:
                            if event.type == "text":
                                if not started_text and reply_parts:
                                    writer({"type": "token", "text": "\n\n"})
                                started_text = True
                                writer({"type": "token", "text": event.text})
                        response = stream.get_final_message()
                except (anthropic.APIError, ValueError):
                    log.exception("Falha na chamada do especialista %s", route)
                    reply_parts.append(FALLBACK_REPLY)
                    writer({"type": "token", "text": FALLBACK_REPLY})
                    new_messages.append({"role": "assistant", "content": FALLBACK_REPLY})
                    break

                text = "".join(b.text for b in response.content if b.type == "text").strip()
                if text:
                    reply_parts.append(text)

                if response.stop_reason == "refusal":
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
                    outcome = run_tool(db, block.name, block.input)
                    writer({"type": "tool", "name": block.name, "status": "error" if outcome.is_error else "done"})
                    if outcome.properties:
                        property_ids.extend(p["id"] for p in outcome.properties)
                        writer({"type": "properties", "items": outcome.properties})
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": outcome.content,
                            "is_error": outcome.is_error,
                        }
                    )
                new_messages.append({"role": "user", "content": results})

            writer({"type": "reply", "text": "\n\n".join(reply_parts), "property_ids": property_ids})
        return {"messages": new_messages}

    specialist.__name__ = route
    return specialist


# ---------------------------------------------------------------- grafo


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    builder = StateGraph(AgentState)
    builder.add_node("supervisor", supervisor)
    for route in SPECIALISTS:
        builder.add_node(route, make_specialist(route))
        builder.add_edge(route, END)
    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", lambda s: s["route"], list(SPECIALISTS))
    return builder.compile(checkpointer=checkpointer)
