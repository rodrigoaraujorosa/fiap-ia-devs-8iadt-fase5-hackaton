"""Ferramentas que os agentes podem chamar (tool use do Claude)."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.models import Lead, Property
from app.models.enums import Intent, LeadStatus
from app.schemas.property import PropertyOut, PropertySearchParams
from app.services import scheduling
from app.services.property_search import search_properties
from app.services.summary import submit_summary


class PropertyDetailsParams(BaseModel):
    property_id: str = Field(description="Código do imóvel, ex.: IMV-012")


class ListSlotsParams(BaseModel):
    tipo: Literal["visita", "reuniao"] = Field(
        description="'visita' para conhecer um imóvel com um corretor; 'reuniao' para conversa com especialista "
        "(investimentos) ou quando ainda não há imóvel definido"
    )
    data: date | None = Field(None, description="Dia preferido pelo cliente (AAAA-MM-DD), se ele indicou")
    periodo: Literal["manha", "tarde"] | None = Field(None, description="Período preferido, se o cliente indicou")
    property_id: str | None = Field(None, description="Imóvel da visita (ajuda a escolher o corretor da região)")


class BookParams(BaseModel):
    slot_id: int = Field(description="slot_id retornado por listar_horarios e escolhido pelo cliente")
    tipo: Literal["visita", "reuniao"]
    property_id: str | None = Field(None, description="Imóvel a visitar, se houver")
    observacoes: str | None = Field(None, description="Informações úteis para o corretor")


class HandoffParams(BaseModel):
    motivo: str = Field(description="Por que o cliente precisa de um humano agora (ex.: pediu para ligarem)")


@dataclass
class ToolContext:
    db: Session
    lead_id: uuid.UUID


@dataclass
class ToolOutcome:
    content: str  # o que volta para o modelo
    is_error: bool = False
    properties: list[dict] = field(default_factory=list)  # cards de imóveis para a interface
    event: dict | None = None  # evento extra para a interface (ex.: agendamento confirmado)


def _schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema


def _tool(name: str, description: str, params: type[BaseModel]) -> dict[str, Any]:
    # eager_input_streaming: a entrada da ferramenta chega em streaming; por isso validamos com Pydantic abaixo
    return {"name": name, "description": description, "input_schema": _schema(params), "eager_input_streaming": True}


BUSCAR = _tool(
    "buscar_imoveis",
    "Busca imóveis disponíveis na base da imobiliária. Combine filtros estruturados (finalidade, tipo, zonas, "
    "bairros, preço, quartos, rentabilidade) com 'query' em linguagem natural para preferências subjetivas ou "
    "referências de localização (ex.: 'perto do metrô', 'rua tranquila', 'perto da Paulista'). "
    "Zonas válidas: 'zona sul', 'zona oeste', 'zona norte', 'zona leste', 'centro'. "
    "purpose: 'venda' para compra/investimento, 'aluguel' para locação. Preços em reais "
    "(aluguel = valor mensal). Retorna até 'limit' imóveis.",
    PropertySearchParams,
)
DETALHES = _tool(
    "detalhes_imovel",
    "Retorna todos os detalhes de um imóvel pelo código (ex.: IMV-012), com condomínio e IPTU.",
    PropertyDetailsParams,
)
LISTAR_HORARIOS = _tool(
    "listar_horarios",
    "Lista horários livres na agenda do corretor ou especialista adequado ao cliente (dias úteis, 9h às 18h). "
    "Use antes de agendar e ofereça 2 ou 3 opções ao cliente.",
    ListSlotsParams,
)
AGENDAR = _tool(
    "agendar",
    "Confirma o agendamento no horário escolhido pelo cliente. Só chame depois que o cliente escolheu um dos "
    "horários listados. Se o cliente já tinha um agendamento, ele é remarcado automaticamente.",
    BookParams,
)
TRANSFERIR = _tool(
    "transferir_para_humano",
    "Encaminha o lead para um corretor humano entrar em contato (quando o cliente pede para falar com uma pessoa, "
    "pede ligação ou tem uma questão que você não pode resolver). Gera o resumo para o corretor.",
    HandoffParams,
)

TOOLSETS: dict[str, list[dict[str, Any]]] = {
    "compra_aluguel": [BUSCAR, DETALHES, TRANSFERIR],
    "investimento": [BUSCAR, DETALHES, TRANSFERIR],
    "agendamento": [LISTAR_HORARIOS, AGENDAR, DETALHES, TRANSFERIR],
}


def _brief(p: PropertyOut) -> dict:
    """Resumo do imóvel que volta para o modelo (campos do segmento; sem ruído de campos vazios)."""
    data = {
        "id": p.id,
        "titulo": p.title,
        "tipo": p.property_type,
        "finalidade": p.purpose,
        "bairro": p.neighborhood,
        "zona": p.zone,
        "cidade": p.city,
        "preco": p.price,
        "area_m2": p.area_m2,
        "vagas": p.parking,
        "condominio": p.condo_fee,
        "destaques": p.amenities[:5],
        "perto_metro": p.near_metro,
        "mobiliado": p.furnished,
    }
    if p.segment == "residencial":
        data.update({"quartos": p.bedrooms, "suites": p.suites, "pet": p.pet_friendly})
    f = p.features or {}
    for key in ("atividades", "andar", "pe_direito_m", "docas", "piso_carga_ton_m2", "acesso", "fachada_m", "andares"):
        if f.get(key):
            data[key] = f[key]
    if f.get("locado"):
        data["locado"] = f["locado"]  # inquilino, contrato_ate, aluguel_atual
    if p.estimated_yield:
        data["rentabilidade_estimada_aa"] = p.estimated_yield
    return {k: v for k, v in data.items() if v not in (None, [], "")}


def _buscar(ctx: ToolContext, raw: Any) -> ToolOutcome:
    lead = ctx.db.get(Lead, ctx.lead_id)
    if lead.intent in (None, Intent.INDEFINIDO):  # trava determinística: a finalidade vem do cliente, não de palpite
        return ToolOutcome(
            "O cliente ainda não disse se quer comprar, alugar ou investir. Pergunte isso antes de buscar imóveis "
            "(não presuma pelo valor).",
            is_error=True,
        )
    results = search_properties(ctx.db, PropertySearchParams.model_validate(raw))
    if not results:
        return ToolOutcome(json.dumps({"resultados": [], "aviso": "Nenhum imóvel com esses filtros."}))
    payload = {"total": len(results), "resultados": [_brief(r) for r in results]}
    return ToolOutcome(json.dumps(payload, ensure_ascii=False), properties=[r.model_dump() for r in results])


def _detalhes(ctx: ToolContext, raw: Any) -> ToolOutcome:
    params = PropertyDetailsParams.model_validate(raw)
    prop = ctx.db.get(Property, params.property_id.strip().upper())
    if not prop:
        return ToolOutcome(f"Imóvel {params.property_id} não encontrado.", is_error=True)
    out = PropertyOut.model_validate(prop)
    return ToolOutcome(out.model_dump_json(), properties=[out.model_dump()])


def _listar_horarios(ctx: ToolContext, raw: Any) -> ToolOutcome:
    params = ListSlotsParams.model_validate(raw)
    lead = ctx.db.get(Lead, ctx.lead_id)
    property_id = params.property_id.strip().upper() if params.property_id else None
    brokers = scheduling.pick_brokers(ctx.db, lead, params.tipo, property_id)
    slots = scheduling.free_slots(ctx.db, brokers, params.data, params.periodo)
    if not slots and (params.data or params.periodo):
        slots = scheduling.free_slots(ctx.db, brokers)  # sem horário na preferência: sugere os próximos
        aviso = "Sem horários livres na preferência do cliente; estes são os próximos disponíveis."
    else:
        aviso = None
    names = {b.id: b.name for b in brokers}
    payload = {
        "horarios": [
            {"slot_id": s.id, "quando": scheduling.format_slot(s.start_at), "com": names[s.broker_id]} for s in slots
        ],
        **({"aviso": aviso} if aviso else {}),
    }
    if not slots:
        payload["aviso"] = "Agenda cheia nos próximos dias; ofereça transferir para um corretor ligar."
    return ToolOutcome(json.dumps(payload, ensure_ascii=False))


def _agendar(ctx: ToolContext, raw: Any) -> ToolOutcome:
    params = BookParams.model_validate(raw)
    lead = ctx.db.get(Lead, ctx.lead_id)
    property_id = params.property_id.strip().upper() if params.property_id else None
    try:
        appt = scheduling.book(ctx.db, lead, params.slot_id, params.tipo, property_id, params.observacoes)
    except scheduling.SchedulingError as exc:
        return ToolOutcome(str(exc), is_error=True)
    submit_summary(lead.id, "agendamento")
    when = scheduling.format_slot(appt.slot.start_at)
    info = {"confirmado": True, "tipo": appt.kind, "quando": when, "com": appt.broker.name,
            "imovel": appt.property_id}  # fmt: skip
    event = {"type": "appointment", "id": str(appt.id), **info}
    return ToolOutcome(json.dumps(info, ensure_ascii=False), event=event)


def _transferir(ctx: ToolContext, raw: Any) -> ToolOutcome:
    params = HandoffParams.model_validate(raw)
    lead = ctx.db.get(Lead, ctx.lead_id)
    broker = lead.assigned_broker or scheduling.pick_brokers(ctx.db, lead, "reuniao")[0]
    if lead.status != LeadStatus.AGENDADO:
        lead.status = LeadStatus.ENCAMINHADO
    lead.assigned_broker_id = broker.id
    lead.next_followup_at = None
    lead.extra = {**(lead.extra or {}), "handoff_reason": params.motivo}
    ctx.db.commit()
    submit_summary(lead.id, "encaminhamento")
    info = {"encaminhado": True, "corretor": broker.name, "prazo_retorno": "em até 1 hora útil"}
    return ToolOutcome(json.dumps(info, ensure_ascii=False), event={"type": "handoff", **info})


_HANDLERS = {
    "buscar_imoveis": _buscar,
    "detalhes_imovel": _detalhes,
    "listar_horarios": _listar_horarios,
    "agendar": _agendar,
    "transferir_para_humano": _transferir,
}


def run_tool(ctx: ToolContext, name: str, raw_input: Any) -> ToolOutcome:
    handler = _HANDLERS.get(name)
    if handler is None:
        return ToolOutcome(f"Ferramenta desconhecida: {name}", is_error=True)
    try:
        return handler(ctx, raw_input)
    except ValidationError as exc:
        # Com eager_input_streaming o servidor não valida a entrada — validamos aqui
        return ToolOutcome(f"Argumentos inválidos para {name}: {exc.errors(include_url=False)}", is_error=True)
