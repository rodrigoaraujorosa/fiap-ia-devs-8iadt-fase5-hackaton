from app.schemas.property import PropertySearchParams
from app.services.property_search import search_properties


def test_structured_filters_respected(db):
    """Clínica procurando sala: finalidade, tipo (com sinônimo), atividade permitida, preço e área."""
    params = PropertySearchParams(
        purpose="aluguel", property_type="consultório", activity="clinica", max_price=8000, min_area=40, limit=20
    )
    results = search_properties(db, params)
    assert results
    for r in results:
        assert r.purpose == "aluguel"
        assert r.property_type == "sala comercial"
        assert "clínica" in r.features["atividades"]
        assert r.price <= 8000
        assert r.area_m2 >= 40


def test_type_synonyms(db):
    """Linguagem do cliente → tipos da base: escritório, ponto, depósito."""
    office = {
        r.property_type for r in search_properties(db, PropertySearchParams(property_type="escritório", limit=20))
    }
    assert office and office <= {"sala comercial", "conjunto comercial", "laje corporativa"}
    shop = {r.property_type for r in search_properties(db, PropertySearchParams(property_type="ponto", limit=20))}
    assert shop == {"loja"}
    warehouse = search_properties(db, PropertySearchParams(property_type="depósito", limit=20))
    assert warehouse and {r.property_type for r in warehouse} == {"galpão"}


def test_accent_and_case_insensitive_filters(db):
    a = search_properties(db, PropertySearchParams(neighborhoods=["itaim bibi"], limit=20))
    b = search_properties(db, PropertySearchParams(neighborhoods=["Itaim Bibi"], limit=20))
    assert a and [r.id for r in a] == [r.id for r in b]


def test_warehouse_filters(db):
    params = PropertySearchParams(property_type="galpão", min_docks=4, min_ceiling_height=9, limit=20)
    results = search_properties(db, params)
    assert results
    assert all(r.features["docas"] >= 4 and r.features["pe_direito_m"] >= 9 for r in results)


def test_investor_leased_properties(db):
    """Investidor buscando renda imediata: imóveis já locados, com rentabilidade mínima."""
    results = search_properties(db, PropertySearchParams(purpose="venda", leased=True, min_yield=7, limit=20))
    assert results
    for r in results:
        assert r.features["locado"]["inquilino"]
        assert r.estimated_yield >= 7
    not_leased = search_properties(db, PropertySearchParams(purpose="venda", leased=False, limit=20))
    assert not_leased and all("locado" not in r.features for r in not_leased)


def test_hybrid_search_finds_landmarks(db):
    """O ranking lexical deve capturar referências que o embedding sozinho não pega."""
    cases = {
        "escritório na Faria Lima": {"Itaim Bibi", "Pinheiros"},
        "loja na Rua Oscar Freire": {"Jardins"},
        "galpão perto da Via Dutra": {"Guarulhos"},
        "sala perto da Avenida Paulista": {"Bela Vista", "Paraíso"},
    }
    for query, expected in cases.items():
        top = search_properties(db, PropertySearchParams(query=query, limit=3))
        assert top[0].neighborhood in expected, (query, [r.neighborhood for r in top])
        assert top[0].similarity is not None


def test_hybrid_search_keeps_filters(db):
    results = search_properties(db, PropertySearchParams(query="perto da Paulista", purpose="aluguel", limit=5))
    assert results and all(r.purpose == "aluguel" for r in results)


def test_segment_filter(db):
    """A base da demo é só comercial; o filtro de segmento existe para carteiras mistas."""
    assert search_properties(db, PropertySearchParams(segment="comercial", limit=5))
    assert search_properties(db, PropertySearchParams(segment="residencial", limit=5)) == []


def test_streets_and_axes_map_to_neighborhoods(db):
    """ "Augusta" e "Faria Lima" são ruas/eixos: a busca traduz para os bairros da base."""
    augusta = search_properties(db, PropertySearchParams(neighborhoods=["Rua Augusta"], property_type="loja", limit=10))
    assert augusta and {r.neighborhood for r in augusta} == {"Consolação"}
    faria_lima = search_properties(db, PropertySearchParams(neighborhoods=["Faria Lima"], limit=20))
    assert faria_lima and {r.neighborhood for r in faria_lima} <= {"Itaim Bibi", "Pinheiros"}
