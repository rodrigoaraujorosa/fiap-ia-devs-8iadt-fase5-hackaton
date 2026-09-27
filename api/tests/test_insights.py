"""Painel de observabilidade sem rede: respostas do Langfuse simuladas."""

import json

import pytest

from app.core.config import get_settings
from app.services import insights


def fake_langfuse(path: str, params: dict | None = None) -> dict:
    if path == "/api/public/projects":
        return {"data": [{"id": "proj1"}]}
    q = json.loads(params["query"])
    assert {"column": "environment", "operator": "=", "value": "test", "type": "string"} in q["filters"]
    dims = [d["field"] for d in q["dimensions"]]
    measures = [m["measure"] for m in q["metrics"]]
    names = {f["value"] for f in q["filters"] if f["column"] == "name"}
    if "timeDimension" in q:
        return {"data": [{"time_dimension": "2026-09-27", "sum_totalCost": 1.5}]}
    if "turno" in names:
        return {"data": [{"count_count": "40", "p50_latency": 7000, "p95_latency": 12000}]}
    if "suspeita_injecao" in names:
        return {"data": [{"count_count": "2"}]}
    if dims == ["name"] and "latency" in measures:
        return {
            "data": [
                {"name": "compra_aluguel.llm", "sum_totalCost": 1.0, "count_count": "30", "p50_latency": 2500},
                {"name": "extrair_perfil", "sum_totalCost": 0.5, "count_count": "40", "p50_latency": 3000},
            ]
        }
    if dims == ["name"]:
        return {"data": [{"name": "buscar_imoveis", "count_count": "12"}]}
    if "usageByType" in measures:
        return {"data": [{"providedModelName": "claude-sonnet-5", "usageType": "input", "sum_usageByType": "1000"},
                         {"providedModelName": "claude-sonnet-5", "usageType": "cache_read_input_tokens",
                          "sum_usageByType": "3000"}]}  # fmt: skip
    if "costByType" in measures:
        return {"data": [{"costType": "cache_read_input_tokens", "sum_costByType": 0.1}]}
    if dims == ["providedModelName"]:
        return {"data": [{"providedModelName": "claude-sonnet-5", "sum_totalCost": 1.0, "count_count": "30"}]}
    raise AssertionError(q)


@pytest.fixture
def langfuse(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(s, "langfuse_secret_key", "sk-test")
    monkeypatch.setattr(insights, "_get", fake_langfuse)
    insights._project_id.cache_clear()
    insights._cache.clear()
    yield
    insights._project_id.cache_clear()
    insights._cache.clear()


def test_insights_combine_langfuse_and_business_numbers(db, client, langfuse):
    data = client.get("/observability?period=7d").json()
    assert data["totals"]["cost"] == 1.5 and data["totals"]["llm_calls"] == 70 and data["totals"]["turns"] == 40
    assert data["totals"]["cost_per_conversation"] == round(1.5 / data["totals"]["conversations"], 4)
    assert data["cache"] == {"hit_rate": 0.75, "savings": 0.9}  # 3000 de 4000 tokens; 0,1 a preço cheio = 1,0
    assert data["latency"] == {"p50_ms": 7000, "p95_ms": 12000}
    assert [a["name"] for a in data["by_agent"]] == ["compra_aluguel.llm", "extrair_perfil"]
    assert data["tools"] == [{"name": "buscar_imoveis", "calls": 12}] and data["injections"] == 2
    assert data["links"]["session_url"] == "https://cloud.langfuse.com/project/proj1/sessions/{session_id}"


def test_insights_without_langfuse(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "langfuse_public_key", None)
    assert client.get("/observability").json()["enabled"] is False
    assert client.get("/observability/links").json() == {"enabled": False, "project_url": None, "session_url": None}


def test_insights_require_admin(client, langfuse, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_password", "senha")
    assert client.get("/observability").status_code == 401
    assert client.get("/observability/links").status_code == 200  # só links, sem dados


def test_langfuse_failure_becomes_502(client, langfuse, monkeypatch):
    def down(path, params=None):
        raise insights.InsightsError("Langfuse indisponível: ConnectError")

    monkeypatch.setattr(insights, "_get", down)
    response = client.get("/observability?period=24h")
    assert response.status_code == 502 and "indisponível" in response.json()["detail"]
