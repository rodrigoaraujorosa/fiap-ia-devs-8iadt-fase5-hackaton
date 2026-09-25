"""Jobs em segundo plano (APScheduler): follow-up automático e reposição da agenda dos corretores."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.jobs.followup import run_followups
from app.services.scheduling import ensure_future_slots

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _refresh_slots() -> None:
    with SessionLocal() as db:
        if created := ensure_future_slots(db):
            log.info("Agenda: %s novos horários criados", created)


def start() -> None:
    global _scheduler
    settings = get_settings()
    if _scheduler is not None or not settings.followup_enabled:
        return
    _scheduler = BackgroundScheduler(timezone=settings.timezone)
    _scheduler.add_job(
        run_followups, "interval", seconds=settings.followup_check_seconds, id="followup",
        max_instances=1, coalesce=True,
    )  # fmt: skip
    _scheduler.add_job(_refresh_slots, "interval", hours=6, id="slots")
    _scheduler.start()
    _refresh_slots()
    log.info("Jobs iniciados: follow-up a cada %ss", settings.followup_check_seconds)


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
