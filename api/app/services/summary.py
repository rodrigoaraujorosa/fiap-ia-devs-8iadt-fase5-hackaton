"""Resumo inteligente do lead para o corretor (gerado ao agendar/encaminhar ou sob demanda)."""

import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

import anthropic
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm import claude, usage_details
from app.core import observability
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Lead, Message, Summary
from app.services.mailer import send_summary_email
from app.services.scheduling import format_slot, upcoming_appointment

log = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="summary")

SUMMARY_PROMPT = """\
Você prepara o briefing de um lead para o corretor de uma imobiliária em São Paulo, a partir da conversa do lead \
com a SDR virtual e dos dados do CRM. O corretor vai ler em 30 segundos antes de ligar ou encontrar o cliente.

Seja objetivo e concreto; use apenas fatos da conversa e do CRM (não invente). Escreva tudo em português do Brasil, \
sem palavras em inglês.
"""


class BrokerSummary(BaseModel):
    resumo: str = Field(description="2 a 4 frases: quem é o cliente, o que busca, momento e urgência")
    perfil: str = Field(description="Perfil em uma linha (ex.: 'Família com 2 filhos, 1º imóvel, financiamento')")
    necessidades: list[str] = Field(description="Critérios do imóvel: região, faixa de preço, quartos, extras")
    imoveis_de_interesse: list[str] = Field(description="Códigos dos imóveis que o cliente viu ou gostou (IMV-...)")
    objecoes_e_duvidas: list[str] = Field(description="Objeções, dúvidas ou receios que apareceram; [] se nenhum")
    proximos_passos: list[str] = Field(description="Ações recomendadas para o corretor, em ordem")
    abordagem_sugerida: str = Field(description="Dica de como conduzir a conversa com este cliente")


def _render(summary: BrokerSummary, lead: Lead) -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {i}" for i in items) if items else "- —"

    return (
        f"**{lead.name or 'Lead sem nome'}** · {lead.intent} · {lead.temperature} ({lead.score}/100)\n\n"
        f"{summary.resumo}\n\n**Perfil:** {summary.perfil}\n\n"
        f"**Necessidades**\n{bullets(summary.necessidades)}\n\n"
        f"**Imóveis de interesse:** {', '.join(summary.imoveis_de_interesse) or '—'}\n\n"
        f"**Objeções e dúvidas**\n{bullets(summary.objecoes_e_duvidas)}\n\n"
        f"**Próximos passos**\n{bullets(summary.proximos_passos)}\n\n"
        f"**Abordagem sugerida:** {summary.abordagem_sugerida}"
    )


def _crm_snapshot(db: Session, lead: Lead) -> dict:
    fields = ["name", "phone", "intent", "property_type", "budget_min", "budget_max", "bedrooms", "regions",
              "urgency", "timeline", "financing", "investor_profile", "ticket", "expected_return", "score",
              "temperature", "status"]  # fmt: skip
    data = {f: getattr(lead, f) for f in fields if getattr(lead, f) not in (None, [], "")}
    data.update(lead.extra or {})
    if appt := upcoming_appointment(db, lead.id):
        data["agendamento"] = f"{appt.kind} com {appt.broker.name} em {format_slot(appt.slot.start_at)}"
        if appt.property_id:
            data["agendamento"] += f" (imóvel {appt.property_id})"
    return data


def generate_summary(db: Session, lead_id: uuid.UUID) -> Summary:
    settings = get_settings()
    lead = db.get(Lead, lead_id)
    messages = db.scalars(select(Message).where(Message.lead_id == lead_id).order_by(Message.id)).all()
    conversation = "\n".join(
        f"{'Cliente' if m.role == 'user' else 'SDR'}: {m.content}" for m in messages[-40:] if m.role != "system"
    )
    crm = json.dumps(_crm_snapshot(db, lead), ensure_ascii=False, default=str)
    prompt = f"<crm>\n{crm}\n</crm>\n\n<conversa>\n{conversation}\n</conversa>"

    with observation_for(lead_id, prompt) as gen:
        response = claude().messages.parse(
            model=settings.llm_main_model,
            max_tokens=16000,
            system=SUMMARY_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},
            output_format=BrokerSummary,
        )
        gen.update(output=response.parsed_output, usage_details=usage_details(response))

    summary = response.parsed_output
    if summary is None:
        raise RuntimeError(f"Resumo não gerado (stop_reason={response.stop_reason})")
    row = Summary(lead_id=lead_id, content=summary.model_dump(), text=_render(summary, lead))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def observation_for(lead_id: uuid.UUID, prompt: str):
    return observability.observation(
        "resumo_corretor", as_type="generation", model=get_settings().llm_main_model, input=prompt
    )


def _generate_in_background(lead_id: uuid.UUID, trigger: str) -> None:
    try:
        with observability.trace("resumo_corretor", session_id=str(lead_id)), SessionLocal() as db:
            summary = generate_summary(db, lead_id)
            send_summary_email(db, lead_id, trigger, summary)
    except (anthropic.APIError, RuntimeError):
        log.exception("Falha ao gerar resumo do lead %s", lead_id)


def submit_summary(lead_id: uuid.UUID, trigger: str) -> None:
    """Gera o resumo e o envia ao corretor por e-mail, sem bloquear a resposta ao lead."""
    _executor.submit(_generate_in_background, lead_id, trigger)
