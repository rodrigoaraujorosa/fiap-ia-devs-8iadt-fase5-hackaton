from fastapi import APIRouter

from app.services.app_config import get_widget_config

router = APIRouter(prefix="/widget", tags=["widget"])


@router.get("/policy")
def widget_policy():
    """Domínios que podem embutir o widget (público: o app web usa para montar o frame-ancestors do /embed)."""
    cfg = get_widget_config()
    return {"restrict": cfg.restrict, "allowed_domains": cfg.allowed_domains}
