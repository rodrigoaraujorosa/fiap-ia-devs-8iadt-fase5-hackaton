"""Ferramentas que os agentes podem chamar (tool use do Claude)."""

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.models import Property
from app.schemas.property import PropertyOut, PropertySearchParams
from app.services.property_search import search_properties


class PropertyDetailsParams(BaseModel):
    property_id: str = Field(description="Código do imóvel, ex.: IMV-012")


@dataclass
class ToolOutcome:
    content: str  # o que volta para o modelo
    is_error: bool = False
    properties: list[dict] = field(default_factory=list)  # cards para a interface


def _schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema


TOOLS: list[dict[str, Any]] = [
    {
        "name": "buscar_imoveis",
        "description": (
            "Busca imóveis disponíveis na base da imobiliária. Combine filtros estruturados (finalidade, tipo, zonas, "
            "bairros, preço, quartos, rentabilidade) com 'query' em linguagem natural para preferências subjetivas ou "
            "referências de localização (ex.: 'perto do metrô', 'rua tranquila', 'perto da Paulista'). "
            "Zonas válidas: 'zona sul', 'zona oeste', 'zona norte', 'zona leste', 'centro'. "
            "purpose: 'venda' para compra/investimento, 'aluguel' para locação. Preços em reais "
            "(aluguel = valor mensal). Retorna até 'limit' imóveis."
        ),
        "input_schema": _schema(PropertySearchParams),
        "eager_input_streaming": True,
    },
    {
        "name": "detalhes_imovel",
        "description": "Retorna todos os detalhes de um imóvel pelo código (ex.: IMV-012), com condomínio e IPTU.",
        "input_schema": _schema(PropertyDetailsParams),
        "eager_input_streaming": True,
    },
]


def _brief(p: PropertyOut, similarity: float | None = None) -> dict:
    data = {
        "id": p.id,
        "titulo": p.title,
        "tipo": p.property_type,
        "finalidade": p.purpose,
        "bairro": p.neighborhood,
        "zona": p.zone,
        "preco": p.price,
        "quartos": p.bedrooms,
        "suites": p.suites,
        "vagas": p.parking,
        "area_m2": p.area_m2,
        "destaques": p.amenities[:4],
        "pet": p.pet_friendly,
        "mobiliado": p.furnished,
        "perto_metro": p.near_metro,
    }
    if p.estimated_yield:
        data["rentabilidade_estimada_aa"] = p.estimated_yield
    return data


def run_tool(db: Session, name: str, raw_input: Any) -> ToolOutcome:
    try:
        if name == "buscar_imoveis":
            params = PropertySearchParams.model_validate(raw_input)
            results = search_properties(db, params)
            if not results:
                return ToolOutcome(json.dumps({"resultados": [], "aviso": "Nenhum imóvel com esses filtros."}))
            payload = {"total": len(results), "resultados": [_brief(r) for r in results]}
            return ToolOutcome(
                json.dumps(payload, ensure_ascii=False),
                properties=[r.model_dump() for r in results],
            )

        if name == "detalhes_imovel":
            params = PropertyDetailsParams.model_validate(raw_input)
            prop = db.get(Property, params.property_id.strip().upper())
            if not prop:
                return ToolOutcome(f"Imóvel {params.property_id} não encontrado.", is_error=True)
            out = PropertyOut.model_validate(prop)
            return ToolOutcome(out.model_dump_json(), properties=[out.model_dump()])

        return ToolOutcome(f"Ferramenta desconhecida: {name}", is_error=True)
    except ValidationError as exc:
        # Com eager_input_streaming o servidor não valida a entrada — validamos aqui
        return ToolOutcome(f"Argumentos inválidos para {name}: {exc.errors(include_url=False)}", is_error=True)
