"""A referential is assessed in slices, and a legal impact knows whose asset it concerns."""

from ebios_rm.domain.enums import Origin
from ebios_rm.domain.essential_asset import EssentialAsset
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.reference_repository import BaselineControl
from ebios_rm.workshops.workshop1_cadrage import prompts
from ebios_rm.workshops.workshop1_cadrage.agent import CONTROLS_PER_CALL, AgnoWorkshop1Runner
from ebios_rm.workshops.workshop1_cadrage.agent_runner import ControlAssessmentBatch
from ebios_rm.workshops.workshop1_cadrage.models import ControlAssessmentProposal


def _mc():
    return MissionContext(organisation_nom="ACME", secteur_activite="Finance",
                          applicable_frameworks=["RGPD"])


def _controls(n):
    return [BaselineControl(control_id=f"A.{i}", framework="ISO27001", description=f"desc {i}",
                            category="tech", covers_risk_category=[], framework_version="2022",
                            legal_impact_type=None, legal_impact_details=None) for i in range(n)]


def test_a_large_referential_is_split_across_calls(monkeypatch):
    # ISO 27001 is 93 controls; one structured response covering all of them cannot fit
    # the output budget, so every control comes back unconcluded.
    seen = []

    def fake_run(self, schema, prompt, *, what):
        seen.append(what)
        return ControlAssessmentBatch(assessments=[
            ControlAssessmentProposal(control_id="A.1", verdict="insufficient_information")])

    monkeypatch.setattr(AgnoWorkshop1Runner, "_run_structured", fake_run)
    runner = AgnoWorkshop1Runner(model=object())
    runner.assess_controls(_mc(), "ISO27001", _controls(93))

    assert len(seen) == 8                      # 93 controls / 12 per call, rounded up
    assert "1/8" in seen[0] and "8/8" in seen[-1]


def test_a_small_referential_still_takes_one_call(monkeypatch):
    seen = []
    monkeypatch.setattr(AgnoWorkshop1Runner, "_run_structured",
                        lambda self, schema, prompt, *, what: (seen.append(what),
                                                               ControlAssessmentBatch())[1])
    AgnoWorkshop1Runner(model=object()).assess_controls(_mc(), "RGPD", _controls(CONTROLS_PER_CALL))

    assert len(seen) == 1
    assert "/" not in seen[0]                  # no slice suffix when there is nothing to slice


def test_the_legal_prompt_names_the_asset_each_event_concerns():
    # Two events read alike; only the asset distinguishes health data from financial data,
    # and without it the evidence of one gets attached to the other.
    assets = [
        EssentialAsset(id="BE_01", nom="Données de santé", description="Dossiers patients",
                       nature="Information", origin=Origin.ASSESSMENT),
        EssentialAsset(id="BE_03", nom="Données financières", description="Données d'entreprise",
                       nature="Information", origin=Origin.DECLARATION),
    ]
    events = [
        FearedEvent(id="ER_02", description="Accès non autorisé", bien_essentiel_id="BE_01",
                    categorie_impact="vie_privee_personnes_concernees", gravite="Critique",
                    origin=Origin.ASSESSMENT),
        FearedEvent(id="ER_03", description="Accès non autorisé", bien_essentiel_id="BE_03",
                    categorie_impact="juridique", gravite="Significative",
                    origin=Origin.EXTRACTION),
    ]
    prompt = prompts.legal_impacts_prompt(_mc(), events, [], None, assets)

    assert "Données de santé" in prompt and "Données financières" in prompt
