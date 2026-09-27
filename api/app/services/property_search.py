"""Busca híbrida de imóveis (RAG).

1. Filtros estruturados (SQL): finalidade, tipo, zona, preço, quartos...
2. Sobre os candidatos filtrados, dois rankings:
   - semântico: distância de cosseno entre embeddings (pgvector)
   - lexical: full-text search em português (tsvector) — pega nomes próprios como "Paulista", "Ibirapuera"
3. Fusão dos rankings com Reciprocal Rank Fusion (RRF).
"""

import unicodedata

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.models import Property
from app.schemas.property import PropertySearchParams, PropertySearchResult

RRF_K = 60  # constante padrão do RRF
# Atividades que os imóveis comerciais declaram permitir (features.atividades)
ACTIVITIES = ["escritório", "consultório", "clínica", "coworking", "varejo", "alimentação", "serviços", "showroom",
              "logística", "armazenagem", "e-commerce", "indústria leve", "educação"]  # fmt: skip
# Ruas e eixos que o cliente cita como se fossem bairros → bairros da base
NEIGHBORHOOD_ALIASES = {
    "augusta": ["Consolação"],
    "rua augusta": ["Consolação"],
    "oscar freire": ["Jardins"],
    "rua oscar freire": ["Jardins"],
    "jardim paulista": ["Jardins"],
    "faria lima": ["Itaim Bibi", "Pinheiros", "Jardim Europa"],
    "av faria lima": ["Itaim Bibi", "Pinheiros", "Jardim Europa"],
    "jk": ["Itaim Bibi", "Vila Olímpia"],
    "av jk": ["Itaim Bibi", "Vila Olímpia"],
    "juscelino kubitschek": ["Itaim Bibi", "Vila Olímpia"],
    "berrini": ["Brooklin", "Cidade Monções"],
    "chucri zaidan": ["Chácara Santo Antônio"],
    "marginal pinheiros": ["Vila Leopoldina", "Jaguaré", "Cidade Monções", "Chácara Santo Antônio"],
    "paulista": ["Bela Vista", "Cerqueira César", "Paraíso"],
    "av paulista": ["Bela Vista", "Cerqueira César", "Paraíso"],
    "avenida paulista": ["Bela Vista", "Cerqueira César", "Paraíso"],
    "centro": ["República", "Sé", "Liberdade"],
    "itaim": ["Itaim Bibi"],
    "morumbi": ["Jardim Guedala"],
    "ibirapuera": ["Vila Nova Conceição", "Moema"],
    "barueri": ["Alphaville"],
    "dutra": ["Guarulhos"],
    "via dutra": ["Guarulhos"],
    "anhanguera": ["Cajamar", "Jundiaí"],
    "bandeirantes": ["Jundiaí", "Cajamar"],
    "castello branco": ["Alphaville", "Itapevi", "Araçariguama"],
    "castelo branco": ["Alphaville", "Itapevi", "Araçariguama"],
    "fernao dias": ["Extrema"],
    "regis bittencourt": ["Embu das Artes"],
    "rodoanel": ["Jaguaré", "Embu das Artes", "Itapevi"],
}


def _expand_neighborhoods(names: list[str]) -> list[str]:
    expanded = []
    for name in names:
        key = _normalize(name).replace(".", "")
        expanded += NEIGHBORHOOD_ALIASES.get(key, [name])
    return [_normalize(n) for n in expanded]


# Tipos equivalentes na linguagem do cliente (quem pede "escritório" aceita conjunto, andar ou laje)
OFFICE = ["conjunto comercial", "andar corporativo", "laje corporativa"]
TYPE_SYNONYMS = {
    "escritorio": OFFICE,
    "sede": OFFICE + ["prédio comercial"],
    "sala": ["conjunto comercial", "sala comercial"],
    "sala comercial": ["conjunto comercial", "sala comercial"],
    "consultorio": ["conjunto comercial", "sala comercial"],
    "conjunto": ["conjunto comercial"],
    "andar": ["andar corporativo", "laje corporativa"],
    "andar corporativo": ["andar corporativo", "laje corporativa"],
    "andar inteiro": ["andar corporativo", "laje corporativa"],
    "laje": ["laje corporativa", "andar corporativo"],
    "laje corporativa": ["laje corporativa", "andar corporativo"],
    "ponto": ["loja"],
    "ponto comercial": ["loja"],
    "loja de rua": ["loja"],
    "galpao": ["galpão"],
    "galpao logistico": ["galpão"],
    "deposito": ["galpão"],
    "armazem": ["galpão"],
    "centro de distribuicao": ["galpão"],
    "cd": ["galpão"],
    "predio": ["prédio comercial"],
    "predio comercial": ["prédio comercial"],
    "predio inteiro": ["prédio comercial"],
    "edificio": ["prédio comercial"],
    "monousuario": ["prédio comercial"],
    # residencial (compatibilidade)
    "apartamento": ["apartamento", "studio", "cobertura"],
    "ape": ["apartamento", "studio", "cobertura"],
    "kitnet": ["studio"],
    "estudio": ["studio"],
    "loft": ["studio"],
}
MAX_CANDIDATES = 200


def _normalize(text: str) -> str:
    """Minúsculas e sem acento, para comparar 'Zona Sul' com 'zona sul'."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower().strip()) if unicodedata.category(c) != "Mn")


def _unaccent_lower(column):
    return func.translate(func.lower(column), "áàâãéêíóôõúüç", "aaaaeeiooouuc")


def _document_tsv():
    doc = func.concat_ws(
        " ",
        Property.title,
        Property.neighborhood,
        Property.zone,
        Property.property_type,
        Property.description,
        func.array_to_string(Property.amenities, " "),
        cast(Property.features, String),
    )
    return func.to_tsvector("portuguese", doc)


def _any_term_tsquery(query: str):
    # plainto_tsquery faz AND entre os termos; trocamos por OR para ranquear por termos em comum
    and_query = cast(func.plainto_tsquery("portuguese", query), String)
    return func.to_tsquery("portuguese", func.replace(and_query, "&", "|"))


def _apply_filters(stmt, params: PropertySearchParams):
    stmt = stmt.where(Property.available.is_(True))
    if params.purpose:
        stmt = stmt.where(Property.purpose == _normalize(params.purpose))
    if params.segment:
        stmt = stmt.where(Property.segment == _normalize(params.segment))
    if params.property_type:
        wanted = _normalize(params.property_type)
        types = [_normalize(t) for t in TYPE_SYNONYMS.get(wanted, [wanted])]
        stmt = stmt.where(_unaccent_lower(Property.property_type).in_(types))
    if params.zones:
        stmt = stmt.where(_unaccent_lower(Property.zone).in_([_normalize(z) for z in params.zones]))
    if params.neighborhoods:
        stmt = stmt.where(_unaccent_lower(Property.neighborhood).in_(_expand_neighborhoods(params.neighborhoods)))
    if params.min_price is not None:
        stmt = stmt.where(Property.price >= params.min_price)
    if params.max_price is not None:
        stmt = stmt.where(Property.price <= params.max_price)
    if params.min_area is not None:
        stmt = stmt.where(Property.area_m2 >= params.min_area)
    if params.max_area is not None:
        stmt = stmt.where(Property.area_m2 <= params.max_area)
    if params.min_parking is not None:
        stmt = stmt.where(Property.parking >= params.min_parking)
    if params.activity:
        canonical = {_normalize(x): x for x in ACTIVITIES}
        activity = canonical.get(_normalize(params.activity), params.activity.strip().lower())
        stmt = stmt.where(Property.features["atividades"].contains([activity]))
    if params.min_docks is not None:
        stmt = stmt.where(Property.features["docas"].as_integer() >= params.min_docks)
    if params.min_ceiling_height is not None:
        stmt = stmt.where(Property.features["pe_direito_m"].as_float() >= params.min_ceiling_height)
    if params.leased is not None:
        has_tenant = Property.features.has_key("locado")
        stmt = stmt.where(has_tenant if params.leased else ~has_tenant)
    if params.min_bedrooms is not None:
        stmt = stmt.where(Property.bedrooms >= params.min_bedrooms)
    if params.pet_friendly is not None:
        stmt = stmt.where(Property.pet_friendly.is_(params.pet_friendly))
    if params.furnished is not None:
        stmt = stmt.where(Property.furnished.is_(params.furnished))
    if params.min_yield is not None:
        stmt = stmt.where(Property.estimated_yield >= params.min_yield)
    return stmt


def search_properties(db: Session, params: PropertySearchParams) -> list[PropertySearchResult]:
    if not params.query:
        props = db.scalars(_apply_filters(select(Property), params).order_by(Property.price).limit(params.limit)).all()
        return [PropertySearchResult.model_validate(p) for p in props]

    from app.services.embeddings import embed_query  # import tardio: só carrega o modelo quando necessário

    distance = Property.embedding.cosine_distance(embed_query(params.query))
    text_rank = func.ts_rank(_document_tsv(), _any_term_tsquery(params.query))
    rows = db.execute(
        _apply_filters(select(Property, distance.label("distance"), text_rank.label("text_rank")), params)
        .where(Property.embedding.is_not(None))
        .limit(MAX_CANDIDATES)
    ).all()

    semantic_order = sorted(rows, key=lambda r: r.distance)
    lexical_order = sorted((r for r in rows if r.text_rank > 0), key=lambda r: -r.text_rank)
    scores: dict[str, float] = {}
    for ranking in (semantic_order, lexical_order):
        for pos, row in enumerate(ranking):
            scores[row.Property.id] = scores.get(row.Property.id, 0.0) + 1 / (RRF_K + pos + 1)

    best = sorted(rows, key=lambda r: -scores[r.Property.id])[: params.limit]
    return [
        PropertySearchResult.model_validate(r.Property).model_copy(update={"similarity": round(1 - r.distance, 4)})
        for r in best
    ]
