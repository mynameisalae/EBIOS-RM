"""Workshop 1 end-to-end with a scripted auditor and a fake agent runner (conception §15).

Exercises the deterministic guarantees without any LLM: assessment discipline,
RGPD security/legal split, stable gap ids, the stripped Workshop-4 handoff, the
legal-impact attachment, and the never-empty scope decisions.
"""

from fakes import FakeRunner, ScriptedHuman

from ebios_rm.domain.enums import Gravite
from ebios_rm.mission_context.ingestion import ExtractedAnswer, questionnaire_answers_to_facts
from ebios_rm.workshops.workshop1_cadrage.assessment import assess_framework
from ebios_rm.workshops.workshop1_cadrage.intake_ingestion import complete_intake_from_facts
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap
from ebios_rm.workshops.workshop1_cadrage.workshop import run_workshop1


def _ingested_facts():
    facts, _ = questionnaire_answers_to_facts([
        ExtractedAnswer(question_id="organisation_nom", found=True, answer="Clinique Test"),
        ExtractedAnswer(question_id="secteur_activite", found=True, answer="Santé"),
        ExtractedAnswer(question_id="applicable_frameworks", found=True,
                        answer="ANSSI_hygiene, RGPD, NIST"),
        ExtractedAnswer(question_id="acces_distant_moyens", found=True, answer="VPN"),
    ], "questionnaire.pdf")
    return facts


# --- Phase 1: intake completion ---

def test_intake_asks_followups_and_records_skip():
    human = ScriptedHuman(
        answers={"edr_av_deploye": "Microsoft Defender for Endpoint"},
        skips={"sauvegarde_strategie": "Information non disponible côté client pour l'instant"},
    )
    mc = complete_intake_from_facts(_ingested_facts(), [], human)

    assert "edr_av_deploye" in human.asked and "sauvegarde_strategie" in human.asked
    assert mc.value("edr_av_deploye") == "Microsoft Defender for Endpoint"
    skip_fact = mc.get("sauvegarde_strategie")
    assert skip_fact is not None and skip_fact.justification  # non-empty reason (§8)


# --- Phase 2: workshop run ---

def _run(reference_repo):
    human = ScriptedHuman(answers={"edr_av_deploye": "Defender", "sauvegarde_strategie": "quotidienne hors ligne"})
    mc = complete_intake_from_facts(_ingested_facts(), [], human)
    return run_workshop1(mc, FakeRunner(), reference_repo)


def test_scope_decisions_never_empty(reference_repo):
    out = _run(reference_repo)
    assert out.baseline_scope_decisions  # fiche de test §15


def test_gap_produced_with_stable_id_and_risk_categories(reference_repo):
    out = _run(reference_repo)
    gaps = {g.control_id: g for g in out.baseline_gaps_full}
    assert "ANSSI-H-21" in gaps
    g = gaps["ANSSI-H-21"]
    assert g.risk_categories  # carried from covers_risk_category
    # gap_id is a stable content hash, not a counter.
    assert g.gap_id == BaselineGap.make_gap_id("ANSSI_hygiene", "ANSSI-H-21", g.weakness)
    assert g.gap_id.startswith("BG-")


def test_workshop4_handoff_is_stripped_and_excludes_empty_risk_categories(reference_repo):
    out = _run(reference_repo)
    for g4 in out.baseline_gaps_for_w4():
        # Stripped of framework/control_id (§12.3, §18): only these fields exist.
        assert set(g4.model_dump().keys()) == {"gap_id", "weakness", "risk_categories"}
        assert g4.risk_categories  # empty-risk gaps (legal-only) never handed to W4


def test_insufficient_controls_stay_unverified(reference_repo):
    out = _run(reference_repo)
    # The fake marks every non-ANSSI-H-21 control insufficient -> tracked, not invented into gaps.
    assert out.unverified_controls
    assert "ANSSI-H-21" not in out.unverified_controls


def test_legal_impact_attached_to_feared_event(reference_repo):
    out = _run(reference_repo)
    event = out.evenements_redoutes[0]
    assert event.legal_impacts, "a legal provision should be attached with evidence (§15.1)"
    li = event.legal_impacts[0]
    assert li.framework == "RGPD"
    assert li.evidence_mission_context  # double-citation discipline


def test_gravite_is_one_of_the_four_fixed_values(reference_repo):
    out = _run(reference_repo)
    assert all(e.gravite in set(Gravite) for e in out.evenements_redoutes)


# --- assessment unit: evidence discipline ---

def test_gap_without_evidence_is_downgraded_to_insufficient(reference_repo):
    from ebios_rm.workshops.workshop1_cadrage.models import ControlAssessmentProposal

    controls = reference_repo.get_baseline_controls("ANSSI_hygiene")
    # Claim a gap but cite no evidence -> must not become a gap.
    proposals = [ControlAssessmentProposal(control_id=controls[0].control_id, verdict="gap", evidence_quote="")]
    result = assess_framework("ANSSI_hygiene", controls, proposals)
    assert result.gaps == []
    assert controls[0].control_id in result.insufficient
