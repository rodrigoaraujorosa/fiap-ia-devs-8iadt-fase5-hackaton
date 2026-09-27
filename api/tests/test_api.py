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


def test_metrics_by_channel_counts_transitions(client, db):
    from datetime import UTC, datetime

    from app.models import Lead

    before = client.get("/dashboard/metrics").json()["by_channel"]
    now = datetime.now(UTC)
    lead = Lead(channel="site", regions=[], requirements=[], last_message_at=now,
                extra={"telegram": {"chat_id": None, "linked_at": now.isoformat()}})  # fmt: skip
    db.add(lead)
    db.commit()
    try:
        after = client.get("/dashboard/metrics").json()["by_channel"]
        assert after.get("site_telegram", 0) == before.get("site_telegram", 0) + 1
        assert after.get("site", 0) == before.get("site", 0)
    finally:
        db.delete(lead)
        db.commit()


def test_demo_leads_cover_every_channel_journey():
    import json
    from datetime import UTC, datetime, timedelta

    from app.core.config import get_settings
    from app.services.demo import _channel_extra

    specs = json.loads((get_settings().data_dir / "demo_leads.json").read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    extras = [(s.get("channel", "web"), _channel_extra(s, lambda m: now - timedelta(minutes=m["minutes_ago"])))
              for s in specs]  # fmt: skip
    journeys = {f"{c}_telegram" if "telegram" in e and c != "telegram" else c for c, e in extras}
    assert journeys == {"web", "site", "telegram", "site_telegram"}
    for channel, extra in extras:
        if "telegram" in extra:
            assert extra["telegram"]["chat_id"] is None  # demo nunca envia nada ao Telegram
            assert ("linked_at" in extra["telegram"]) == (channel != "telegram")
