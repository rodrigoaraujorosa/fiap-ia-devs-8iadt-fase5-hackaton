"""Regras determinísticas de qualificação (não chamam LLM nem banco)."""

from app.agents.qualification import (
    LeadAnalysis,
    apply_analysis,
    compute_score,
    missing_fields,
    normalize_phone,
    refresh_funnel,
)
from app.models import Lead
from app.models.enums import LeadStatus, Temperature


def _analysis(**overrides) -> LeadAnalysis:
    base = dict(
        name="", phone="", declined_phone="nao", intent_evidence="", intent="indefinido", property_type="",
        budget_min=0, budget_max=0, bedrooms=0, regions=[],
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


def test_normalize_phone():
    assert normalize_phone("11 98888-7777") == "+55 11 98888-7777"
    assert normalize_phone("+55 (11) 98888-7777") == "+55 11 98888-7777"
    assert normalize_phone("1133334444") == "+55 11 3333-4444"
    assert normalize_phone("123") is None
    assert normalize_phone("") is None


def test_phone_is_captured_and_scores():
    lead = _lead(name="Rodrigo")
    before = compute_score(lead)
    apply_analysis(lead, _analysis(phone="(11) 98888-7777"))
    assert lead.phone == "+55 11 98888-7777"
    assert compute_score(lead) == before + 5


def test_declined_phone_is_remembered():
    lead = _lead()
    apply_analysis(lead, _analysis(declined_phone="sim"))
    assert lead.phone is None and lead.extra["phone_declined"] is True
    apply_analysis(lead, _analysis(phone="garbage"))  # texto que não é telefone não sobrescreve nada
    assert lead.phone is None


def test_intent_requires_quote_from_client():
    """O analisador não pode 'deduzir' a finalidade: sem citação real do cliente, fica indefinido."""
    client = "Oi, procuro um apartamento perto do metrô. Meu orçamento é até 2 mil reais"
    lead = _lead()
    apply_analysis(lead, _analysis(intent="compra", intent_evidence=""), client)
    assert lead.intent == "indefinido"
    apply_analysis(lead, _analysis(intent="aluguel", intent_evidence="é para alugar"), client)
    assert lead.intent == "indefinido"  # citação inventada
    apply_analysis(lead, _analysis(intent="aluguel", intent_evidence="E para ALUGAR!"), client + ". É para alugar.")
    assert lead.intent == "aluguel"  # acento, caixa e pontuação não importam
