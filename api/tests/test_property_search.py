from app.schemas.property import PropertySearchParams
from app.services.property_search import search_properties


def test_structured_filters_respected(db):
    """Exemplo 1 do enunciado: apartamento na zona sul, com filtros de preço e quartos."""
    params = PropertySearchParams(
        purpose="venda", property_type="apartamento", zones=["Zona Sul"], min_bedrooms=2, max_price=1_500_000, limit=20
    )
    results = search_properties(db, params)
    assert results
    for r in results:
        assert r.purpose == "venda"
        assert r.property_type == "apartamento"
        assert r.zone == "zona sul"
        assert r.bedrooms >= 2
        assert r.price <= 1_500_000


def test_accent_and_case_insensitive_filters(db):
    a = search_properties(db, PropertySearchParams(neighborhoods=["saude"], limit=20))
    b = search_properties(db, PropertySearchParams(neighborhoods=["Saúde"], limit=20))
    assert a and [r.id for r in a] == [r.id for r in b]


def test_investment_filter_by_yield(db):
    """Exemplo 2: investidor buscando renda."""
    results = search_properties(db, PropertySearchParams(purpose="venda", min_yield=6, limit=20))
    assert results
    assert all(r.estimated_yield and r.estimated_yield >= 6 for r in results)


def test_hybrid_search_finds_landmarks(db):
    """O ranking lexical deve capturar referências que o embedding sozinho não pega."""
    cases = {
        "morar perto da Avenida Paulista": {"Bela Vista", "Consolação"},
        "apartamento perto do parque Ibirapuera": {"Moema"},
        "bairro boêmio com bares": {"Vila Madalena"},
        "perto da USP": {"Butantã"},
    }
    for query, expected in cases.items():
        top = search_properties(db, PropertySearchParams(query=query, limit=3))
        assert top[0].neighborhood in expected, (query, [r.neighborhood for r in top])
        assert top[0].similarity is not None


def test_hybrid_search_keeps_filters(db):
    results = search_properties(db, PropertySearchParams(query="perto da Paulista", purpose="aluguel", limit=5))
    assert results and all(r.purpose == "aluguel" for r in results)
