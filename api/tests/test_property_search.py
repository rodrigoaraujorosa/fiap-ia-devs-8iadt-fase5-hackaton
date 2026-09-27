from app.schemas.property import PropertySearchParams
from app.services.property_search import OFFICE, search_properties


def test_structured_filters_respected(db):
    """Clínica procurando conjunto: finalidade, tipo (com sinônimo), atividade permitida, preço e área."""
    params = PropertySearchParams(
        purpose="aluguel", property_type="consultório", activity="clinica", max_price=25000, min_area=90, limit=20
    )
    results = search_properties(db, params)
    assert results
    for r in results:
        assert r.purpose == "aluguel"
        assert r.property_type == "conjunto comercial"
        assert "clínica" in r.features["atividades"]
        assert r.price <= 25000
        assert r.area_m2 >= 90


def test_type_synonyms(db):
    """Linguagem do cliente → tipos da base: escritório, andar, sede, depósito."""
    office = {
        r.property_type for r in search_properties(db, PropertySearchParams(property_type="escritório", limit=20))
    }
    assert office and office <= set(OFFICE)
    floors = {r.property_type for r in search_properties(db, PropertySearchParams(property_type="andar", limit=20))}
    assert floors == {"andar corporativo", "laje corporativa"}
    big_hq = PropertySearchParams(property_type="sede", min_area=3000, limit=20)
    hq = {r.property_type for r in search_properties(db, big_hq)}
    assert "prédio comercial" in hq and hq <= {*OFFICE, "prédio comercial"}
    warehouse = search_properties(db, PropertySearchParams(property_type="depósito", limit=20))
    assert warehouse and {r.property_type for r in warehouse} == {"galpão"}


def test_accent_and_case_insensitive_filters(db):
    a = search_properties(db, PropertySearchParams(neighborhoods=["itaim bibi"], limit=20))
    b = search_properties(db, PropertySearchParams(neighborhoods=["Itaim Bibi"], limit=20))
    assert a and [r.id for r in a] == [r.id for r in b]


def test_warehouse_filters(db):
    params = PropertySearchParams(property_type="galpão", min_docks=10, min_ceiling_height=12, limit=20)
    results = search_properties(db, params)
    assert results
    assert all(r.features["docas"] >= 10 and r.features["pe_direito_m"] >= 12 for r in results)


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
        "escritório na Faria Lima": {"Itaim Bibi", "Pinheiros", "Jardim Europa"},
        "galpão na Rodovia Fernão Dias": {"Extrema"},
        "galpão perto da Via Dutra": {"Guarulhos"},
        "conjunto perto da Avenida Paulista": {"Bela Vista", "Paraíso", "Cerqueira César"},
    }
    for query, expected in cases.items():
        top = search_properties(db, PropertySearchParams(query=query, limit=3))
        assert top[0].neighborhood in expected, (query, [r.neighborhood for r in top])
        assert top[0].similarity is not None


def test_hybrid_search_keeps_filters(db):
    results = search_properties(db, PropertySearchParams(query="perto da Paulista", purpose="aluguel", limit=5))
    assert results and all(r.purpose == "aluguel" for r in results)


def test_segment_filter(db):
    """Carteira mista: comercial é o grosso da base; há alguns residenciais de alto padrão à venda."""
    assert search_properties(db, PropertySearchParams(segment="comercial", limit=5))
    homes = search_properties(db, PropertySearchParams(segment="residencial", limit=20))
    assert homes and {r.property_type for r in homes} <= {"apartamento", "cobertura", "casa", "studio"}
    assert all(r.purpose == "venda" for r in homes)


def test_streets_and_axes_map_to_neighborhoods(db):
    """Berrini, Faria Lima e rodovias são ruas/eixos: a busca traduz para os bairros da base."""
    berrini = search_properties(db, PropertySearchParams(neighborhoods=["Berrini"], limit=20))
    assert berrini and {r.neighborhood for r in berrini} <= {"Brooklin", "Cidade Monções"}
    faria_lima = search_properties(db, PropertySearchParams(neighborhoods=["Faria Lima"], limit=20))
    assert faria_lima and {r.neighborhood for r in faria_lima} <= {"Itaim Bibi", "Pinheiros", "Jardim Europa"}
    dutra = search_properties(db, PropertySearchParams(neighborhoods=["Via Dutra"], property_type="galpão", limit=10))
    assert dutra and {r.neighborhood for r in dutra} == {"Guarulhos"}
