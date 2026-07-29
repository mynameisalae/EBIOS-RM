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
    gaps = {c.control_id: g for g in out.baseline_gaps_full for c in g.controls}
    assert "ANSSI-H-21" in gaps
    g = gaps["ANSSI-H-21"]
    assert g.risk_categories  # carried from covers_risk_category
    assert g.frameworks == ["ANSSI_hygiene"]
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
    ids = [u.control_id for u in out.unverified_controls]
    assert "ANSSI-H-21" not in ids
    # Each one says why it could not be concluded (§15 step 2).
    assert all(u.reason and u.reason_label for u in out.unverified_controls)


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


# --- reject -> redo: the auditor's reason reaches the agent (phase B, §12.6) ---

def test_revision_notes_are_passed_to_the_agent(reference_repo):
    human = ScriptedHuman(answers={"edr_av_deploye": "Defender", "sauvegarde_strategie": "quotidienne"})
    mc = complete_intake_from_facts(_ingested_facts(), [], human)
    fake = FakeRunner()
    run_workshop1(mc, fake, reference_repo, revision_notes=["gravité de la fuite sous-évaluée"])
    assert fake.revision_notes_seen == ["gravité de la fuite sous-évaluée"]


def test_cadrage_prompt_injects_revision_notes_only_on_redo():
    from ebios_rm.mission_context.mission_context import MissionContext
    from ebios_rm.workshops.workshop1_cadrage.prompts import cadrage_prompt

    mc = MissionContext(organisation_nom="X", secteur_activite="Santé", applicable_frameworks=["RGPD"])
    assert "REMARQUES DE L'AUDITEUR" not in cadrage_prompt(mc)                    # first run: no notes
    assert "REMARQUES DE L'AUDITEUR" not in cadrage_prompt(mc, [])                # empty: none
    with_notes = cadrage_prompt(mc, ["revoir la gravité de l'événement de fuite"])
    assert "revoir la gravité de l'événement de fuite" in with_notes             # redo: injected


# --- assessment unit: evidence discipline ---

def test_gap_without_evidence_is_downgraded_to_insufficient(reference_repo):
    from ebios_rm.workshops.workshop1_cadrage.models import (
        REASON_NO_EVIDENCE_CITED, ControlAssessmentProposal,
    )

    controls = reference_repo.get_baseline_controls("ANSSI_hygiene")
    # Claim a gap but cite no evidence -> must not become a gap.
    proposals = [ControlAssessmentProposal(control_id=controls[0].control_id, verdict="gap", evidence_quote="")]
    result = assess_framework("ANSSI_hygiene", controls, proposals)
    assert result.gaps == []
    assert [u.control_id for u in result.insufficient] == [controls[0].control_id]
    assert result.insufficient[0].reason == REASON_NO_EVIDENCE_CITED   # prompt problem, not missing info
    assert result.insufficient[0].description                          # what was being checked


# --- hard stop: a declared framework with no controls cannot be assessed (§2, §12.5) ---

def test_frameworks_without_controls_detects_unloaded_ones(reference_repo):
    from ebios_rm.workshops.workshop1_cadrage.assessment import frameworks_without_controls

    missing = frameworks_without_controls(["ANSSI_hygiene", "RGPD", "HDS", "ISO27001"], reference_repo)
    # The dev seed loads ANSSI/RGPD/NIST only; HDS and ISO27001 have nothing.
    assert set(missing) == {"HDS", "ISO27001"}


def test_no_missing_frameworks_when_all_are_loaded(reference_repo):
    from ebios_rm.workshops.workshop1_cadrage.assessment import frameworks_without_controls

    assert frameworks_without_controls(["ANSSI_hygiene", "RGPD"], reference_repo) == []


# --- partial redo: regenerate only the rejected block(s), keep the rest (§12.6) ---

class _CountingRunner(FakeRunner):
    """Counts which agent calls actually happen, so a partial redo can be verified."""

    def __init__(self, gravite=None):
        super().__init__()
        self.calls = {"cadrage": 0, "controls": 0, "legal": 0}
        self._gravite = gravite

    def propose_cadrage(self, mission_context, revision_notes=None):
        self.calls["cadrage"] += 1
        proposal = super().propose_cadrage(mission_context, revision_notes)
        if self._gravite:
            proposal.evenements_redoutes[0].gravite = self._gravite
            proposal.evenements_redoutes[0].description = "Version régénérée"
        return proposal

    def assess_controls(self, mission_context, framework, controls, revision_notes=None):
        self.calls["controls"] += 1
        return super().assess_controls(mission_context, framework, controls, revision_notes)

    def assess_legal_impacts(self, mission_context, events, provisions, revision_notes=None, assets=None):
        self.calls["legal"] += 1
        return super().assess_legal_impacts(mission_context, events, provisions, revision_notes, assets)


def _context():
    human = ScriptedHuman(answers={"edr_av_deploye": "Defender", "sauvegarde_strategie": "quotidienne"})
    return complete_intake_from_facts(_ingested_facts(), [], human)


def test_redoing_only_cadrage_keeps_baseline_and_skips_its_calls(reference_repo):
    from ebios_rm.workshops.workshop1_cadrage.workshop import BLOCK_CADRAGE

    mc = _context()
    first = run_workshop1(mc, _CountingRunner(), reference_repo)
    runner = _CountingRunner(gravite=Gravite.MINIMALE)
    second = run_workshop1(mc, runner, reference_repo, ["gravité à revoir"],
                           blocks={BLOCK_CADRAGE}, previous=first)

    assert runner.calls == {"cadrage": 1, "controls": 0, "legal": 0}   # only the rejected block ran
    assert second.evenements_redoutes[0].description == "Version régénérée"
    assert second.baseline_gaps_full == first.baseline_gaps_full        # untouched, verbatim
    assert second.unverified_controls == first.unverified_controls


def test_redoing_only_baseline_keeps_the_assets_the_auditor_liked(reference_repo):
    from ebios_rm.workshops.workshop1_cadrage.workshop import BLOCK_BASELINE

    mc = _context()
    first = run_workshop1(mc, _CountingRunner(), reference_repo)
    runner = _CountingRunner(gravite=Gravite.MINIMALE)  # would change cadrage if it ran
    second = run_workshop1(mc, runner, reference_repo, ["écart mal formulé"],
                           blocks={BLOCK_BASELINE}, previous=first)

    assert runner.calls["cadrage"] == 0 and runner.calls["legal"] == 0
    assert runner.calls["controls"] >= 1
    assert second.biens_essentiels == first.biens_essentiels            # not reshuffled
    assert second.evenements_redoutes[0].gravite == first.evenements_redoutes[0].gravite


def test_partial_redo_requires_the_previous_output(reference_repo):
    import pytest
    from ebios_rm.workshops.workshop1_cadrage.workshop import BLOCK_LEGAL

    with pytest.raises(ValueError):
        run_workshop1(_context(), _CountingRunner(), reference_repo, blocks={BLOCK_LEGAL})


def test_full_redo_regenerates_everything(reference_repo):
    mc = _context()
    first = run_workshop1(mc, _CountingRunner(), reference_repo)
    runner = _CountingRunner()
    run_workshop1(mc, runner, reference_repo, ["tout revoir"], blocks=None, previous=first)
    assert runner.calls["cadrage"] == 1 and runner.calls["controls"] >= 1 and runner.calls["legal"] == 1


def test_partial_redo_preserves_human_edits(reference_repo):
    from ebios_rm.workshops.workshop1_cadrage.workshop import BLOCK_BASELINE

    mc = _context()
    first = run_workshop1(mc, _CountingRunner(), reference_repo)
    first.human_edits = [{"path": "x", "justification": "correction auditeur"}]
    second = run_workshop1(mc, _CountingRunner(), reference_repo, blocks={BLOCK_BASELINE}, previous=first)
    assert second.human_edits == first.human_edits  # the audit trail survives a redo


# --- unverified controls carry WHY, and the causes are not interchangeable (§15 step 2) ---

def test_each_cause_is_recorded_distinctly(reference_repo):
    from ebios_rm.workshops.workshop1_cadrage.models import (
        REASON_INVALID_VERDICT, REASON_NO_EVIDENCE_CITED, REASON_NO_INFORMATION,
        REASON_UNKNOWN_CONTROL, ControlAssessmentProposal,
    )

    controls = reference_repo.get_baseline_controls("RGPD")   # three controls in the dev seed
    a, b, c = (controls[i].control_id for i in range(3))
    result = assess_framework("RGPD", controls, [
        ControlAssessmentProposal(control_id=a, verdict="insufficient_information"),
        ControlAssessmentProposal(control_id=b, verdict="gap", evidence_quote=""),
        ControlAssessmentProposal(control_id="RGPD-Art999", verdict="gap", evidence_quote="x"),
        ControlAssessmentProposal(control_id=c, verdict="peut-être", evidence_quote="x"),
    ])

    reasons = {u.control_id: u.reason for u in result.insufficient}
    assert reasons[a] == REASON_NO_INFORMATION          # client said nothing -> ask the auditor
    assert reasons[b] == REASON_NO_EVIDENCE_CITED       # model was sloppy -> fix the prompt
    assert reasons["RGPD-Art999"] == REASON_UNKNOWN_CONTROL
    assert reasons[c] == REASON_INVALID_VERDICT
    assert result.gaps == []                            # none of these becomes a finding


def test_unverified_keeps_what_the_model_claimed(reference_repo):
    from ebios_rm.workshops.workshop1_cadrage.models import ControlAssessmentProposal

    controls = reference_repo.get_baseline_controls("ANSSI_hygiene")
    result = assess_framework("ANSSI_hygiene", controls, [
        ControlAssessmentProposal(control_id=controls[0].control_id, verdict="compliant", evidence_quote=""),
    ])
    entry = result.insufficient[0]
    assert entry.model_said == "compliant"      # claimed compliant, proved nothing -> not accepted
    assert entry.framework == "ANSSI_hygiene"
    assert entry.reason_label                   # human-readable for the review screen
