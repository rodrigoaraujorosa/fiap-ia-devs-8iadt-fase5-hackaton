from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(tags=["infra"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@router.get("/info")
def info():
    """Endereços públicos que o app web mostra (site da imobiliária de exemplo, com o widget da Laris)."""
    return {"site_url": get_settings().public_site_url}
