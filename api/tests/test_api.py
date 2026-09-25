def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_list_properties_with_query_params(client):
    resp = client.get("/properties", params={"purpose": "aluguel", "zones": ["centro"], "limit": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body and all(p["purpose"] == "aluguel" and p["zone"] == "centro" for p in body)


def test_search_endpoint(client):
    resp = client.post("/properties/search", json={"query": "casa com quintal para cachorro", "limit": 3})
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_get_property(client):
    assert client.get("/properties/IMV-001").json()["id"] == "IMV-001"
    assert client.get("/properties/NAO-EXISTE").status_code == 404


def test_widget_session_records_source(client, db):
    """Lead vindo do widget: canal "site", origem guardada e imóvel da página em foco."""
    from app.models import Lead

    source = {"brand": "Imobiliária Exemplo", "page_url": "https://exemplo/imovel", "utm_source": "instagram",
              "property_id": "IMV-055"}  # fmt: skip
    res = client.post("/chat/sessions", json={"source": source})
    assert res.status_code == 201
    lead = res.json()
    assert lead["channel"] == "site"
    assert lead["extra"]["source"]["utm_source"] == "instagram"
    assert lead["extra"]["viewing"] == "IMV-055"
    assert client.post("/chat/sessions", json={"source": {"property_id": "<script>"}}).status_code == 422
    db.delete(db.get(Lead, lead["id"]))
    db.commit()
