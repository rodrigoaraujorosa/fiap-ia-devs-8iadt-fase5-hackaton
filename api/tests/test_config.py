"""Configuração em tempo real (/configuration): validação, persistência, horário de silêncio e liga/desliga."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.jobs import followup
from app.services.app_config import FollowupConfig, get_followup_config, save_followup_config

SP = ZoneInfo("America/Sao_Paulo")


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 24, hour, minute, tzinfo=SP)


def test_quiet_hours_across_midnight():
    cfg = FollowupConfig(
        enabled=True, minutes=2, max_attempts=3, quiet_hours=True, quiet_start="21:00", quiet_end="08:00"
    )
    assert cfg.in_quiet_hours(at(23))
    assert cfg.in_quiet_hours(at(7, 59))
    assert not cfg.in_quiet_hours(at(8))
    assert not cfg.in_quiet_hours(at(14))
    assert not cfg.model_copy(update={"quiet_hours": False}).in_quiet_hours(at(23))


def test_quiet_hours_same_day():
    cfg = FollowupConfig(
        enabled=True, minutes=2, max_attempts=3, quiet_hours=True, quiet_start="12:00", quiet_end="14:00"
    )
    assert cfg.in_quiet_hours(at(13))
    assert not cfg.in_quiet_hours(at(15))


@pytest.fixture
def restore_config(db):
    original = get_followup_config(db)
    yield original
    save_followup_config(db, original)


def test_config_api_roundtrip(client, restore_config):
    body = {**restore_config.model_dump(), "minutes": 7, "max_attempts": 2, "quiet_hours": True}
    assert client.put("/config/followup", json=body).status_code == 200
    assert client.get("/config/followup").json() == body
    assert client.put("/config/followup", json={**body, "max_attempts": 9}).status_code == 422
    assert client.put("/config/followup", json={**body, "quiet_start": "25:00"}).status_code == 422


def test_disabled_followup_skips_job_unless_forced(db, restore_config, monkeypatch):
    claimed = []
    monkeypatch.setattr(followup, "_claim_due_leads", lambda: claimed.append(True) or [])
    save_followup_config(db, restore_config.model_copy(update={"enabled": False}))
    assert followup.run_followups() == 0
    assert not claimed  # desligado: o job nem reserva leads
    followup.run_followups(force=True)
    assert claimed  # disparo manual ignora o liga/desliga
