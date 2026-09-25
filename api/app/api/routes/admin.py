from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.jobs.followup import run_followups
from app.services.app_config import FollowupConfig, get_followup_config, save_followup_config
from app.services.demo import reset_demo

router = APIRouter(tags=["configuração"])


@router.get("/config/followup", response_model=FollowupConfig)
def read_followup_config(db: Session = Depends(get_db)):
    """Configuração atual do follow-up (banco, ou padrões do .env se nunca foi alterada)."""
    return get_followup_config(db)


@router.put("/config/followup", response_model=FollowupConfig)
def update_followup_config(config: FollowupConfig, db: Session = Depends(get_db)):
    """Altera o follow-up em tempo real: vale a partir do próximo ciclo do job (até 30s)."""
    return save_followup_config(db, config)


@router.post("/followups/run")
def trigger_followups():
    """Dispara o ciclo de follow-up agora, mesmo com o envio automático desligado ou em horário de silêncio."""
    return {"enviados": run_followups(force=True)}


@router.post("/admin/demo/reset")
def demo_reset(db: Session = Depends(get_db)):
    """Apaga leads, conversas, resumos e agenda e recria o cenário de demonstração (imóveis são mantidos)."""
    return reset_demo(db)
