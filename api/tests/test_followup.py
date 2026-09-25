"""Follow-up automático: tentativas, cadência crescente e 'perdido' (o LLM é substituído por um stub)."""

from datetime import UTC, datetime

import pytest

from app.core.config import get_settings
from app.jobs import followup
from app.models import Lead
from app.models.enums import LeadStatus, MessageRole


@pytest.fixture
def silent_lead(db, monkeypatch):
    monkeypatch.setattr(followup, "_generate_message", lambda lead, history, attempt: f"follow-up {attempt}")
    lead = Lead(
        channel="web", regions=[], extra={}, intent="aluguel", status=LeadStatus.EM_QUALIFICACAO,
        last_lead_message_at=datetime.now(UTC), last_message_at=datetime.now(UTC),
    )  # fmt: skip
    db.add(lead)
    db.commit()
    yield lead
    db.delete(lead)
    db.commit()


def test_followup_cadence_until_lost(db, silent_lead):
    settings = get_settings()
    lead_id, last_msg = silent_lead.id, silent_lead.last_lead_message_at

    for attempt in range(1, settings.followup_max_attempts + 1):
        text = followup.send_followup(lead_id, attempt - 1, last_msg)
        assert text == f"follow-up {attempt}"
        db.refresh(silent_lead)
        assert silent_lead.followup_count == attempt
        wait = (silent_lead.next_followup_at - silent_lead.last_message_at).total_seconds() / 60
        assert wait == pytest.approx(settings.followup_minutes * 2**attempt)  # cadência crescente

    assert followup.send_followup(lead_id, settings.followup_max_attempts, last_msg) is None
    db.refresh(silent_lead)
    assert silent_lead.status == LeadStatus.PERDIDO
    followups = [m for m in silent_lead.messages if m.role == MessageRole.FOLLOWUP]
    assert [m.meta["attempt"] for m in followups] == [1, 2, 3]


def test_followup_discarded_if_lead_replied(db, silent_lead):
    stale = datetime(2020, 1, 1, tzinfo=UTC)  # o lead respondeu depois do momento em que o job o reservou
    assert followup.send_followup(silent_lead.id, 0, stale) is None
    db.refresh(silent_lead)
    assert silent_lead.followup_count == 0
    assert not silent_lead.messages
