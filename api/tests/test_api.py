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
