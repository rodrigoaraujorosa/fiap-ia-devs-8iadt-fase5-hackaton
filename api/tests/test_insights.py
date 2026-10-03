"""Painel de observabilidade: uso da IA registrado no banco do app, sem rede e sem LLM."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select

from app.core import observability, pricing
from app.core.config import get_settings
from app.models import Appointment, AppSetting, UsageEvent
from app.services import exchange, insights

SONNET, HAIKU = "claude-sonnet-5", "claude-haiku-4-5"


@pytest.fixture
def usage(db):
    """Tabela de uso vazia antes e depois (outros testes também registram ferramentas e fluxos)."""
    db.execute(delete(UsageEvent))
    db.commit()
    yield db
    db.execute(delete(UsageEvent))
    db.commit()


@pytest.fixture
def langfuse(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(s, "langfuse_secret_key", "sk-test")
    monkeypatch.setattr(insights, "_get", lambda path, params=None: {"data": [{"id": "proj1"}]})
    insights._project_id.cache_clear()
    yield
    insights._project_id.cache_clear()


def test_cost_follows_the_price_table():
    usage = {"input": 1_000_000, "output": 100_000, "cache_read_input_tokens": 1_000_000,
             "cache_creation_input_tokens": 1_000_000}  # fmt: skip
    # Sonnet 5: 2 (entrada) + 1 (saída) + 0,2 (leitura do cache) + 2,5 (gravação no cache)
    assert pricing.cost(SONNET, usage) == pytest.approx(5.7)
    assert pricing.cost("claude-haiku-4-5-20251001", {"input": 1_000_000, "output": 1_000_000}) == pytest.approx(6.0)
    assert pricing.cost("modelo-desconhecido", usage) == 0
    assert pricing.cache_savings(SONNET, 1_000_000) == pytest.approx(1.8)  # 2,00 a preço cheio, 0,20 pago


def test_calls_tools_and_flows_are_recorded(usage):
    lead_id = str(uuid.uuid4())
    with observability.trace("turno", session_id=lead_id):
        with observability.observation("compra_aluguel.llm", as_type="generation", model=SONNET) as gen:
            gen.update(output="oi", usage_details={"input": 1000, "output": 200, "cache_read_input_tokens": 3000,
                                                   "cache_creation_input_tokens": 0})  # fmt: skip
        with observability.observation("buscar_imoveis", as_type="tool"):
            pass
        with observability.observation("supervisor", as_type="chain"):  # nó do grafo: não entra
            pass
        with pytest.raises(RuntimeError):  # chamada que falhou não tem uso: não entra
            with observability.observation("investimento.llm", as_type="generation", model=SONNET):
                raise RuntimeError("API fora")
        observability.flag_trace("suspeita_injecao", comment="regex")

    rows = usage.scalars(select(UsageEvent).order_by(UsageEvent.id)).all()
    assert [(r.kind, r.name) for r in rows] == [
        ("llm", "compra_aluguel.llm"),
        ("tool", "buscar_imoveis"),
        ("guardrail", "suspeita_injecao"),
        ("trace", "turno"),
    ]
    call = rows[0]
    assert (call.model, call.input_tokens, call.output_tokens, call.cache_read_tokens) == (SONNET, 1000, 200, 3000)
    assert call.cost_usd == pytest.approx((1000 * 2 + 3000 * 0.2 + 200 * 10) / 1e6)
    assert {str(r.lead_id) for r in rows} == {lead_id}


def test_insights_from_the_database(usage, client, langfuse):
    now = datetime.now(UTC)
    # lead da demo com visita agendada: só conta nos indicadores porque tem turno com a IA registrado
    served = usage.scalars(select(Appointment.lead_id)).first()
    visits = usage.scalar(
        select(func.count()).select_from(Appointment).where(
            Appointment.lead_id == served, Appointment.created_at >= now - timedelta(days=7)
        )
    )
    usage.add_all([
        UsageEvent(kind="llm", name="compra_aluguel.llm", model=SONNET, cost_usd=1.0, latency_ms=2500,
                   input_tokens=1000, cache_read_tokens=3000, output_tokens=500),
        UsageEvent(kind="llm", name="extrair_perfil", model=HAIKU, cost_usd=0.5, latency_ms=3000),
        UsageEvent(kind="llm", name="extrair_perfil", model=HAIKU, cost_usd=9.0, created_at=now - timedelta(days=10)),
        UsageEvent(kind="trace", name="turno", latency_ms=7000, lead_id=served),
        UsageEvent(kind="trace", name="turno", latency_ms=9000, lead_id=served),
        UsageEvent(kind="trace", name="follow_up", latency_ms=1000),
        UsageEvent(kind="tool", name="buscar_imoveis"),
        UsageEvent(kind="guardrail", name="suspeita_injecao"),
    ])  # fmt: skip
    usage.commit()

    data = client.get("/observability?period=7d").json()
    assert data["enabled"] is True and data["since"] is not None
    assert data["totals"]["cost"] == 1.5 and data["totals"]["llm_calls"] == 2 and data["totals"]["turns"] == 2
    # os outros leads da demo (sem atendimento registrado) não entram: 1 conversa, não 8
    assert data["totals"]["conversations"] == 1 and data["totals"]["cost_per_conversation"] == 1.5
    assert data["totals"]["appointments"] == visits
    assert data["totals"]["cost_per_appointment"] == (round(1.5 / visits, 4) if visits else None)
    assert data["cache"] == {"hit_rate": 0.75, "savings": 0.0054}  # 3000 de 4000 tokens; 3000 × US$ 1,80/milhão
    assert data["latency"]["p50_ms"] == 8000
    assert [a["name"] for a in data["by_agent"]] == ["compra_aluguel.llm", "extrair_perfil"]
    assert data["by_model"][0] == {"model": SONNET, "cost": 1.0, "calls": 1}
    assert data["tools"] == [{"name": "buscar_imoveis", "calls": 1}] and data["injections"] == 1
    assert len(data["daily"]) in (8, 9) and data["daily"][-1]["cost"] == 1.5 and data["daily"][0]["cost"] == 0
    assert data["links"]["session_url"] == "https://cloud.langfuse.com/project/proj1/sessions/{session_id}"

    assert client.get("/observability?period=30d").json()["totals"]["cost"] == 10.5
    hourly = client.get("/observability?period=24h").json()["daily"]
    assert len(hourly) == 25 and sum(h["cost"] for h in hourly) == 1.5


def test_panel_works_without_langfuse(usage, client, monkeypatch):
    monkeypatch.setattr(get_settings(), "langfuse_public_key", None)
    data = client.get("/observability").json()
    assert data["enabled"] is True and data["totals"]["cost"] == 0 and data["since"] is None
    assert data["totals"]["conversations"] == 0 and data["totals"]["appointments"] == 0  # demo não conta
    assert client.get("/observability/links").json() == {"enabled": False, "project_url": None, "session_url": None}


def test_dollar_rate_comes_from_the_central_bank(usage, client, monkeypatch):
    calls = []

    def ptax() -> dict:
        calls.append(1)
        return {"rate": 5.2238, "source": "ptax", "date": "2026-10-02"}

    def down() -> dict:
        raise exchange.httpx.ConnectError("fora do ar")

    monkeypatch.setattr(get_settings(), "usd_brl_live", True)
    monkeypatch.setattr(exchange, "_fetch", ptax)
    exchange.reset()
    data = client.get("/observability").json()
    assert data["usd_brl"] == 5.2238
    assert data["usd_brl_source"] == {"enabled": True, "live": True, "date": "2026-10-02"}
    client.get("/observability")
    assert len(calls) == 1  # a cotação fica em memória: uma consulta só

    monkeypatch.setattr(exchange, "_fetch", down)
    exchange._next_try = 0.0  # hora de consultar de novo, e o Banco Central não responde: vale a última cotação
    assert client.get("/observability").json()["usd_brl"] == 5.2238
    exchange.reset()  # sem nenhuma cotação obtida: a fixa da configuração
    data = client.get("/observability").json()
    assert data["usd_brl"] == get_settings().usd_brl
    assert data["usd_brl_source"] == {"enabled": True, "live": False, "date": None}
    exchange.reset()


def test_dollar_lookup_can_be_turned_off_in_settings(usage, client, monkeypatch):
    def never() -> dict:
        raise AssertionError("busca desligada: não pode consultar o Banco Central")

    monkeypatch.setattr(get_settings(), "usd_brl_live", True)
    monkeypatch.setattr(exchange, "_fetch", never)
    exchange.reset()
    try:
        saved = client.put("/config/exchange", json={"live": False, "rate": 5.1}).json()
        assert saved["live"] is False and saved["current"] == {"rate": 5.1, "source": "config", "date": None}
        data = client.get("/observability").json()
        assert data["usd_brl"] == 5.1 and data["usd_brl_source"] == {"enabled": False, "live": False, "date": None}
        assert client.put("/config/exchange", json={"live": False, "rate": 0}).status_code == 422

        monkeypatch.setattr(exchange, "_fetch", lambda: {"rate": 5.2238, "source": "ptax", "date": "2026-10-02"})
        on = client.put("/config/exchange", json={"live": True, "rate": 5.1}).json()  # religada: busca na hora
        assert on["current"]["rate"] == 5.2238 and client.get("/config/exchange").json()["rate"] == 5.1
    finally:
        usage.execute(delete(AppSetting).where(AppSetting.key == "exchange"))
        usage.commit()
        exchange.reset()


def test_insights_require_admin(client, langfuse, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_password", "senha")
    assert client.get("/observability").status_code == 401
    assert client.get("/observability/links").status_code == 200  # só links, sem dados
