"""Regras de qualificação do lead: esquema extraído pelo LLM, campos faltantes e scoring.

Tudo aqui é determinístico (sem LLM), para ser explicável no pitch e testável.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.models import Lead
from app.models.enums import Intent, LeadStatus, Temperature

Route = Literal["compra_aluguel", "investimento", "agendamento"]


class LeadAnalysis(BaseModel):
    """Saída estruturada do Supervisor (Haiku).

    Todos os campos são obrigatórios e sem null (esquemas com muitos campos anuláveis são rejeitados como
    "too complex"). Convenção: "" ou 0 = não informado; "desconhecida"/"nao_informado" nos enums.
    """

    name: str = Field(description="Primeiro nome do cliente, ou '' se não informou")
    intent: Literal["compra", "aluguel", "investimento", "indefinido"] = Field(
        description="Objetivo principal do cliente considerando toda a conversa"
    )
    property_type: str = Field(description="apartamento, casa, studio, cobertura, sala comercial, ou ''")
    budget_min: int = Field(description="Valor mínimo em reais (compra: total; aluguel: mensal), ou 0")
    budget_max: int = Field(description="Valor máximo em reais (compra: total; aluguel: mensal), ou 0")
    bedrooms: int = Field(description="Quantidade mínima de quartos desejada, ou 0")
    regions: list[str] = Field(description="Zonas ou bairros de interesse, ex.: ['zona sul', 'Moema']; [] se nenhum")
    urgency: Literal["alta", "media", "baixa", "desconhecida"] = Field(
        description="alta: até 1 mês ou urgente; media: 1 a 6 meses; baixa: sem pressa ou só pesquisando"
    )
    timeline: str = Field(description="Prazo nas palavras do cliente, ex.: 'mudar até o fim do ano', ou ''")
    financing: str = Field(description="Forma de pagamento: financiamento, à vista, FGTS, consórcio..., ou ''")
    investor_profile: str = Field(
        description="Para investidores: objetivo (renda com aluguel ou valorização), prazo e experiência; ou ''"
    )
    ticket: int = Field(description="Para investidores: valor disponível para investir, em reais, ou 0")
    expected_return: str = Field(description="Para investidores: retorno esperado, ex.: '0,6% ao mês', ou ''")
    wants_meeting: Literal["sim", "nao", "nao_informado"] = Field(
        description="'sim' se o cliente pediu ou aceitou visita/reunião; 'nao' se recusou"
    )
    notes: str = Field(
        description="Resumo consolidado, em uma frase, de TODAS as outras preferências e contexto do cliente na "
        "conversa (família, pet, vaga, metrô, imóvel que gostou...), ou ''"
    )
    route: Route = Field(
        description="'agendamento' se o cliente quer marcar/remarcar visita ou reunião ou está escolhendo horário; "
        "senão 'investimento' para investidores; senão 'compra_aluguel'"
    )


# Campos que o SDR precisa coletar, por intenção, em ordem de prioridade
REQUIRED_FIELDS: dict[str, list[str]] = {
    Intent.COMPRA: ["regions", "budget_max", "bedrooms", "property_type", "name", "urgency", "financing"],
    Intent.ALUGUEL: ["regions", "budget_max", "bedrooms", "name", "urgency"],
    Intent.INVESTIMENTO: ["investor_profile", "ticket", "expected_return", "name", "urgency"],
    Intent.INDEFINIDO: ["intent", "name"],
}

FIELD_LABELS = {
    "intent": "objetivo (comprar, alugar ou investir)",
    "name": "nome do cliente",
    "regions": "região/bairros de interesse",
    "budget_max": "faixa de preço",
    "bedrooms": "quantidade de quartos",
    "property_type": "tipo de imóvel",
    "urgency": "urgência/prazo",
    "financing": "forma de pagamento",
    "investor_profile": "perfil de investidor (renda ou valorização, prazo)",
    "ticket": "valor disponível para investir (ticket)",
    "expected_return": "expectativa de retorno",
}

_UPDATABLE = [f for f in LeadAnalysis.model_fields if f not in ("route", "intent", "wants_meeting", "notes")]


def _informed(value) -> bool:
    return value not in (None, "", 0, [], "desconhecida", "nao_informado")


def apply_analysis(lead: Lead, analysis: LeadAnalysis) -> None:
    """Mescla a análise no lead: só sobrescreve o que veio informado."""
    if analysis.intent != Intent.INDEFINIDO or not lead.intent:
        lead.intent = analysis.intent
    for field in _UPDATABLE:
        value = getattr(analysis, field)
        if isinstance(value, str):
            value = value.strip()
        if _informed(value):
            setattr(lead, field, value)
    extra = dict(lead.extra or {})
    if analysis.wants_meeting != "nao_informado":
        extra["wants_meeting"] = analysis.wants_meeting == "sim"
    if analysis.notes.strip():
        extra["preferences"] = analysis.notes.strip()  # o supervisor já consolida a conversa inteira
    lead.extra = extra


def _is_filled(lead: Lead, field: str) -> bool:
    if field == "intent":
        return lead.intent not in (None, Intent.INDEFINIDO)
    value = getattr(lead, field)
    return value not in (None, [], "")


def missing_fields(lead: Lead) -> list[str]:
    return [f for f in REQUIRED_FIELDS.get(lead.intent or Intent.INDEFINIDO, []) if not _is_filled(lead, f)]


def compute_score(lead: Lead) -> int:
    """Score 0-100 com regras transparentes."""
    score = 0
    if _is_filled(lead, "intent"):
        score += 10
    if lead.budget_max or lead.ticket:
        score += 20
    if lead.regions:
        score += 10
    if lead.bedrooms or lead.property_type or lead.expected_return or lead.investor_profile:
        score += 10
    score += {"alta": 25, "media": 12}.get(lead.urgency or "", 0)
    if lead.financing:
        score += 5
    if lead.name:
        score += 5
    if (lead.extra or {}).get("wants_meeting"):
        score += 20
    return min(score, 100)


def temperature_for(score: int) -> Temperature:
    if score >= 65:
        return Temperature.QUENTE
    if score >= 35:
        return Temperature.MORNO
    return Temperature.FRIO


def refresh_funnel(lead: Lead) -> list[str]:
    """Recalcula score, temperatura e status. Retorna os campos ainda faltantes."""
    missing = missing_fields(lead)
    lead.score = compute_score(lead)
    lead.temperature = temperature_for(lead.score)
    if lead.status in (LeadStatus.NOVO, LeadStatus.EM_QUALIFICACAO, LeadStatus.QUALIFICADO, LeadStatus.PERDIDO):
        lead.status = LeadStatus.QUALIFICADO if not missing else LeadStatus.EM_QUALIFICACAO
    return missing
