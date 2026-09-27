"""Painel de observabilidade do ImobiQ: visão sintética de custo, uso dos agentes e desempenho.

Custo, tokens e latência vêm da API de métricas do Langfuse (GET /api/public/v2/metrics); os números de negócio
(conversas, visitas agendadas, leads qualificados) vêm do banco. O resultado fica em cache por 1 minuto, para não
consultar o Langfuse a cada atualização da tela. Só entra o ambiente atual (ENVIRONMENT): os testes usam "test".
Para o detalhe de cada chamada, o painel leva ao próprio Langfuse.
"""

import json
import threading
import time
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import httpx
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Appointment, Lead, Message
from app.models.enums import MessageRole

PERIODS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
CACHE_SECONDS = 60
CACHE_READ_DISCOUNT = 0.9  # na Anthropic, ler do cache custa 10% do preço normal de entrada

_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


class InsightsError(Exception):
    """Falha ao consultar o Langfuse (a mensagem nunca inclui as chaves)."""


def enabled() -> bool:
    s = get_settings()
    return bool(s.langfuse_public_key and s.langfuse_secret_key)


def _get(path: str, params: dict | None = None) -> dict:
    s = get_settings()
    try:
        r = httpx.get(f"{s.langfuse_base_url.rstrip('/')}{path}", params=params, timeout=20,
                      auth=(s.langfuse_public_key or "", s.langfuse_secret_key or ""))  # fmt: skip
    except httpx.HTTPError as exc:
        raise InsightsError(f"Langfuse indisponível: {type(exc).__name__}") from exc
    if r.status_code != 200:
        raise InsightsError(f"Langfuse respondeu {r.status_code}")
    return r.json()


@lru_cache(maxsize=1)
def _project_id() -> str | None:
    projects = _get("/api/public/projects").get("data") or []
    return projects[0]["id"] if projects else None


def links() -> dict:
    """Endereços do projeto e das sessões (cada conversa é uma sessão no Langfuse)."""
    if not enabled():
        return {"enabled": False, "project_url": None, "session_url": None}
    try:
        pid = _project_id()
    except InsightsError:
        pid = None
    if not pid:
        return {"enabled": True, "project_url": None, "session_url": None}
    project = f"{get_settings().langfuse_base_url.rstrip('/')}/project/{pid}"
    return {"enabled": True, "project_url": project, "session_url": f"{project}/sessions/{{session_id}}"}


def _metrics(since: datetime, until: datetime, metrics: list[tuple[str, str]], dims: tuple[str, ...] = (),
             filters: tuple[tuple[str, str], ...] = (), granularity: str | None = None) -> list[dict]:  # fmt: skip
    conditions = [("environment", get_settings().environment), *filters]
    query = {
        "view": "observations",
        "metrics": [{"measure": m, "aggregation": a} for m, a in metrics],
        "dimensions": [{"field": d} for d in dims],
        "filters": [{"column": c, "operator": "=", "value": v, "type": "string"} for c, v in conditions],
        "fromTimestamp": since.isoformat(),
        "toTimestamp": until.isoformat(),
    }
    if granularity:
        query["timeDimension"] = {"granularity": granularity}
    return _get("/api/public/v2/metrics", {"query": json.dumps(query)}).get("data") or []


def _num(value) -> float:
    return float(value or 0)


def _business(db: Session, since: datetime) -> dict:
    conversations = db.scalar(
        select(func.count(distinct(Message.lead_id))).where(
            Message.role == MessageRole.USER, Message.created_at >= since
        )
    )
    appointments = db.scalar(select(func.count()).select_from(Appointment).where(Appointment.created_at >= since))
    qualified = db.scalar(
        select(func.count())
        .select_from(Lead)
        .where(Lead.last_message_at >= since, Lead.status.in_(("qualificado", "agendado", "encaminhado")))
    )
    return {"conversations": conversations or 0, "appointments": appointments or 0, "qualified": qualified or 0}


def _collect(db: Session, period: str) -> dict:
    until = datetime.now(UTC)
    since = until - PERIODS[period]
    gen = (("type", "GENERATION"),)

    by_agent = _metrics(since, until, [("totalCost", "sum"), ("count", "count"), ("latency", "p50")], ("name",), gen)
    by_model = _metrics(since, until, [("totalCost", "sum"), ("count", "count")], ("providedModelName",), gen)
    usage = _metrics(since, until, [("usageByType", "sum")], ("providedModelName",), gen)
    cost_types = _metrics(since, until, [("costByType", "sum")], (), gen)
    daily = _metrics(since, until, [("totalCost", "sum")], (), gen, "hour" if period == "24h" else "day")
    turns = _metrics(since, until, [("count", "count"), ("latency", "p50"), ("latency", "p95")], (),
                     (("name", "turno"),))  # fmt: skip
    tools = _metrics(since, until, [("count", "count")], ("name",), (("type", "TOOL"),))
    injections = _metrics(since, until, [("count", "count")], (), (("name", "suspeita_injecao"),))

    total = sum(_num(r.get("sum_totalCost")) for r in by_agent)
    tokens = {"input": 0.0, "cache_read": 0.0, "cache_creation": 0.0, "output": 0.0}
    for row in usage:
        kind = row.get("usageType", "")
        key = {"input": "input", "output": "output", "cache_read_input_tokens": "cache_read",
               "cache_creation_input_tokens": "cache_creation"}.get(kind)  # fmt: skip
        if key:
            tokens[key] += _num(row.get("sum_usageByType"))
    prompt_tokens = tokens["input"] + tokens["cache_read"] + tokens["cache_creation"]
    cache_read_cost = sum(
        _num(r.get("sum_costByType")) for r in cost_types if r.get("costType") == "cache_read_input_tokens"
    )
    # o que as leituras do cache teriam custado a preço cheio, menos o que custaram
    cache_savings = cache_read_cost / (1 - CACHE_READ_DISCOUNT) * CACHE_READ_DISCOUNT

    business = _business(db, since)
    turn = turns[0] if turns else {}

    def per(n: int) -> float | None:
        return round(total / n, 4) if n else None

    return {
        "enabled": True,
        "period": period,
        "generated_at": until.isoformat(),
        "usd_brl": get_settings().usd_brl,
        "environment": get_settings().environment,
        "totals": {
            "cost": round(total, 4),
            "llm_calls": int(sum(_num(r.get("count_count")) for r in by_agent)),
            "turns": int(_num(turn.get("count_count"))),
            **business,
            "cost_per_conversation": per(business["conversations"]),
            "cost_per_appointment": per(business["appointments"]),
            "cost_per_qualified": per(business["qualified"]),
        },
        "latency": {"p50_ms": round(_num(turn.get("p50_latency"))), "p95_ms": round(_num(turn.get("p95_latency")))},
        "cache": {
            "hit_rate": round(tokens["cache_read"] / prompt_tokens, 3) if prompt_tokens else 0,
            "savings": round(cache_savings, 4),
        },
        "tokens": {k: int(v) for k, v in tokens.items()},
        "by_agent": sorted(
            (
                {
                    "name": r["name"],
                    "cost": round(_num(r.get("sum_totalCost")), 4),
                    "calls": int(_num(r.get("count_count"))),
                    "p50_ms": round(_num(r.get("p50_latency"))),
                }  # fmt: skip
                for r in by_agent
                if r.get("name")
            ),
            key=lambda r: r["cost"],
            reverse=True,
        ),
        "by_model": [
            {
                "model": r["providedModelName"],
                "cost": round(_num(r.get("sum_totalCost")), 4),
                "calls": int(_num(r.get("count_count"))),
            }  # fmt: skip
            for r in by_model
            if r.get("providedModelName")
        ],
        "daily": [{"date": r["time_dimension"], "cost": round(_num(r.get("sum_totalCost")), 4)} for r in daily],
        "tools": sorted(
            ({"name": r["name"], "calls": int(_num(r.get("count_count")))} for r in tools if r.get("name")),
            key=lambda r: r["calls"],
            reverse=True,
        ),
        "injections": int(sum(_num(r.get("count_count")) for r in injections)),
        "links": links(),
    }


def insights(db: Session, period: str) -> dict:
    if not enabled():
        return {"enabled": False, "links": links()}
    with _lock:
        cached = _cache.get(period)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
    data = _collect(db, period)
    with _lock:
        _cache[period] = (time.monotonic(), data)
    return data
