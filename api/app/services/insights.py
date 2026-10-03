"""Painel de observabilidade do ImobiQ: visão sintética de custo, uso dos agentes e desempenho.

Tudo vem do banco do app: cada chamada ao Claude, ferramenta, turno e suspeita de injection é registrada em
usage_events (app/services/usage.py), com o custo calculado pela tabela de preços (app/core/pricing.py); os
números de negócio (conversas, visitas agendadas, leads qualificados) vêm das tabelas do CRM, só dos leads
atendidos pela IA. O Langfuse fica
para o detalhe de cada chamada: o painel só monta os links para ele (a API de métricas de lá tem cota diária).
"""

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core import pricing
from app.core.config import get_settings
from app.models import Appointment, Lead, UsageEvent
from app.services import exchange

PERIODS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}


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


def _business(db: Session, since: datetime) -> dict:
    """Números de negócio só dos leads atendidos pela IA (com turno registrado em usage_events).

    Os custos são divididos por eles; leads sem atendimento registrado (dados de demonstração, conversas com a
    IA pausada) ficam de fora, para não baratear artificialmente o custo por conversa e por visita.
    """
    E = UsageEvent
    turn = (E.kind == "trace", E.name == "turno", E.lead_id.is_not(None))
    served = select(E.lead_id).where(*turn)  # em qualquer data: a visita pode sair dias depois da conversa
    conversations = db.scalar(select(func.count(distinct(E.lead_id))).where(*turn, E.created_at >= since))
    appointments = db.scalar(
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.created_at >= since, Appointment.lead_id.in_(served))
    )
    qualified = db.scalar(
        select(func.count())
        .select_from(Lead)
        .where(
            Lead.last_message_at >= since,
            Lead.status.in_(("qualificado", "agendado", "encaminhado")),
            Lead.id.in_(served),
        )
    )
    return {"conversations": conversations or 0, "appointments": appointments or 0, "qualified": qualified or 0}


def _median(q: float = 0.5):
    return func.percentile_cont(q).within_group(UsageEvent.latency_ms)


def _daily(db: Session, since: datetime, until: datetime, hourly: bool) -> list[dict]:
    """Custo por hora (24h) ou por dia, no fuso do app, com os intervalos sem uso zerados."""
    E = UsageEvent
    tz = get_settings().timezone
    if hourly:
        bucket = func.date_trunc("hour", E.created_at)
    else:
        bucket = func.to_char(func.timezone(tz, E.created_at), "YYYY-MM-DD")
    rows = db.execute(
        select(bucket, func.sum(E.cost_usd)).where(E.kind == "llm", E.created_at >= since).group_by(bucket)
    ).all()
    if hourly:
        costs = {b.astimezone(UTC).isoformat(): c for b, c in rows}
        first = since.replace(minute=0, second=0, microsecond=0)
        keys = [(first + timedelta(hours=i)).isoformat() for i in range(int((until - first) / timedelta(hours=1)) + 1)]
    else:
        costs = dict(rows)
        zone = ZoneInfo(tz)
        first, last = since.astimezone(zone).date(), until.astimezone(zone).date()
        keys = [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]
    return [{"date": k, "cost": round(costs.get(k) or 0, 4)} for k in keys]


def insights(db: Session, period: str) -> dict:
    E = UsageEvent
    until = datetime.now(UTC)
    since = until - PERIODS[period]
    recent = E.created_at >= since

    by_agent = db.execute(
        select(E.name, func.sum(E.cost_usd), func.count(), _median()).where(E.kind == "llm", recent).group_by(E.name)
    ).all()
    by_model = db.execute(
        select(E.model, func.sum(E.cost_usd), func.count(), func.sum(E.input_tokens), func.sum(E.output_tokens),
               func.sum(E.cache_read_tokens), func.sum(E.cache_creation_tokens))
        .where(E.kind == "llm", recent)
        .group_by(E.model)
    ).all()  # fmt: skip
    turns, p50, p95 = db.execute(
        select(func.count(), _median(), _median(0.95)).where(E.kind == "trace", E.name == "turno", recent)
    ).one()
    tools = db.execute(
        select(E.name, func.count()).where(E.kind == "tool", recent).group_by(E.name).order_by(func.count().desc())
    ).all()
    injections = db.scalar(select(func.count()).where(E.kind == "guardrail", E.name == "suspeita_injecao", recent))

    total = sum(row[1] for row in by_model)
    tokens = {
        "input": sum(r[3] for r in by_model),
        "cache_read": sum(r[5] for r in by_model),
        "cache_creation": sum(r[6] for r in by_model),
        "output": sum(r[4] for r in by_model),
    }
    prompt_tokens = tokens["input"] + tokens["cache_read"] + tokens["cache_creation"]
    business = _business(db, since)

    def per(n: int) -> float | None:
        return round(total / n, 4) if n else None

    return {
        "enabled": True,
        "period": period,
        "generated_at": until.isoformat(),
        "since": db.scalar(select(func.min(E.created_at))),  # o painel conta a partir do primeiro registro
        "usd_brl": (quote := exchange.usd_brl(db))["rate"],
        # enabled: busca ligada nas configurações; live: a cotação veio mesmo do Banco Central
        "usd_brl_source": {"enabled": quote["live"], "live": quote["source"] == "ptax", "date": quote["date"]},
        "environment": get_settings().environment,
        "totals": {
            "cost": round(total, 4),
            "llm_calls": sum(r[2] for r in by_model),
            "turns": turns,
            **business,
            "cost_per_conversation": per(business["conversations"]),
            "cost_per_appointment": per(business["appointments"]),
            "cost_per_qualified": per(business["qualified"]),
        },
        "latency": {"p50_ms": round(p50 or 0), "p95_ms": round(p95 or 0)},
        "cache": {
            "hit_rate": round(tokens["cache_read"] / prompt_tokens, 3) if prompt_tokens else 0,
            "savings": round(sum(pricing.cache_savings(r[0], r[5]) for r in by_model), 4),
        },
        "tokens": tokens,
        "by_agent": sorted(
            ({"name": n, "cost": round(c, 4), "calls": k, "p50_ms": round(ms or 0)} for n, c, k, ms in by_agent),
            key=lambda r: r["cost"],
            reverse=True,
        ),
        "by_model": sorted(
            ({"model": r[0], "cost": round(r[1], 4), "calls": r[2]} for r in by_model if r[0]),
            key=lambda r: r["cost"],
            reverse=True,
        ),
        "daily": _daily(db, since, until, hourly=period == "24h"),
        "tools": [{"name": n, "calls": calls} for n, calls in tools],
        "injections": injections or 0,
        "links": links(),
    }
