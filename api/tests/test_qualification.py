"""Regras determinísticas de qualificação (não chamam LLM nem banco)."""

from app.agents.qualification import LeadAnalysis, apply_analysis, compute_score, missing_fields, refresh_funnel
from app.models import Lead
from app.models.enums import LeadStatus, Temperature


def _analysis(**overrides) -> LeadAnalysis:
    base = dict(
        name="", intent="indefinido", property_type="", budget_min=0, budget_max=0, bedrooms=0, regions=[],
        urgency="desconhecida", timeline="", financing="", investor_profile="", ticket=0, expected_return="",
        wants_meeting="nao_informado", notes="", route="compra_aluguel",
    )  # fmt: skip
    return LeadAnalysis(**{**base, **overrides})


def _lead(**kwargs) -> Lead:
    return Lead(**{"regions": [], "extra": {}, "status": LeadStatus.NOVO, "intent": "indefinido", **kwargs})


def test_sentinels_do_not_overwrite_known_data():
    lead = _lead(name="Ricardo", budget_max=1_300_000)
    apply_analysis(lead, _analysis(intent="compra", regions=["zona sul"]))
    assert lead.name == "Ricardo"
    assert lead.budget_max == 1_300_000
    assert lead.intent == "compra"
    assert lead.regions == ["zona sul"]
    assert lead.urgency is None


def test_indefinido_does_not_erase_known_intent():
    lead = _lead()
    lead.intent = "aluguel"
    apply_analysis(lead, _analysis(intent="indefinido"))
    assert lead.intent == "aluguel"


def test_meeting_and_notes_go_to_extra():
    lead = _lead()
    apply_analysis(lead, _analysis(wants_meeting="sim", notes="tem um cachorro"))
    assert lead.extra == {"wants_meeting": True, "preferences": "tem um cachorro"}


def test_missing_fields_follow_intent():
    assert missing_fields(_lead()) == ["intent", "name"]
    lead = _lead(name="Fernanda", ticket=500_000)
    lead.intent = "investimento"
    assert missing_fields(lead) == ["investor_profile", "expected_return", "urgency"]


def test_score_and_temperature():
    cold = _lead()
    assert compute_score(cold) == 0
    hot = _lead(name="Ricardo", budget_max=1_300_000, regions=["zona sul"], bedrooms=3, urgency="alta",
                financing="financiamento", extra={"wants_meeting": True})  # fmt: skip
    hot.intent = "compra"
    assert compute_score(hot) == 100  # 105 pontos, limitado a 100
    refresh_funnel(hot)
    assert hot.temperature == Temperature.QUENTE

    warm = _lead(budget_max=4000, regions=["centro"])  # 10 intent + 20 orçamento + 10 região
    warm.intent = "aluguel"
    assert compute_score(warm) == 40
    refresh_funnel(warm)
    assert warm.temperature == Temperature.MORNO


def test_funnel_status_becomes_qualified_when_complete():
    lead = _lead(name="Ana", budget_max=4000, regions=["centro"], bedrooms=1, urgency="media")
    lead.intent = "aluguel"
    assert refresh_funnel(lead) == []
    assert lead.status == LeadStatus.QUALIFICADO

    lead.status = LeadStatus.AGENDADO  # etapas posteriores não regridem
    refresh_funnel(lead)
    assert lead.status == LeadStatus.AGENDADO
