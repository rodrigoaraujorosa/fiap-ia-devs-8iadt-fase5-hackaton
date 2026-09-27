from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.db.session import get_db
from app.services import insights

router = APIRouter(prefix="/observability", tags=["observabilidade"])


@router.get("/links")
def observability_links():
    """Links do Langfuse (projeto e sessão de cada conversa), para o menu e o detalhe do lead."""
    return insights.links()


@router.get("", dependencies=[Depends(require_admin)])
def observability(period: Literal["24h", "7d", "30d"] = "7d", db: Session = Depends(get_db)):
    """Visão sintética de custo, uso dos agentes, cache e latência (Langfuse) cruzada com os números de negócio."""
    try:
        return insights.insights(db, period)
    except insights.InsightsError as exc:
        raise HTTPException(502, str(exc)) from exc
