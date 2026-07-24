"""Document ingestion + answer sanity-check (conception §2, §5, §11)."""

from fakes import FakeIngestionRunner, ScriptedHuman

from ebios_rm.domain.enums import Origin
from ebios_rm.mission_context.ingestion import (
    ExtractedAnswer,
    questionnaire_answers_to_facts,
    supporting_answers_to_facts,
)
from ebios_rm.mission_context.mission_context import assemble_from_facts
from ebios_rm.orchestrator import mission_state
from ebios_rm.repositories.mission_repository import MissionRepository, connect
from ebios_rm.workshops.workshop1_cadrage.intake_ingestion import (
    apply_flags,
    complete_intake_from_facts,
    resume_intake,
)


# --- pure conversion rules ---

def test_questionnaire_answers_become_declaration_facts_and_flags():
    answers = [
        ExtractedAnswer(question_id="organisation_nom", found=True, answer="Clinique Test",
                        source_quote="Nom : Clinique Test"),
        ExtractedAnswer(question_id="taille_effectif", found=True, answer="beaucoup de gens",
                        source_quote="Effectif : beaucoup de gens", plausibility="implausible",
                        plausibility_reason="Un effectif doit être un nombre."),
        ExtractedAnswer(question_id="secteur_activite", found=False),  # not found -> ignored
        ExtractedAnswer(question_id="not_a_real_question", found=True, answer="x"),  # unknown -> ignored
    ]
    facts, flags = questionnaire_answers_to_facts(answers, "questionnaire.docx")
    ids = {f.field_name for f in facts}
    assert ids == {"organisation_nom", "taille_effectif"}
    assert all(f.origin is Origin.DECLARATION for f in facts)
    assert len(flags) == 1 and flags[0].question_id == "taille_effectif"
    assert flags[0].kind == "implausible"


def test_supporting_answers_require_source_quote():
    answers = [
        ExtractedAnswer(question_id="edr_av_deploye", found=True, answer="CrowdStrike",
                        source_quote="EDR déployé : CrowdStrike Falcon"),
        ExtractedAnswer(question_id="sauvegarde_strategie", found=True, answer="quotidienne",
                        source_quote=""),  # no quote -> dropped (extraction rule §5.3)
    ]
    facts = supporting_answers_to_facts(answers, "politique.pdf")
    assert [f.field_name for f in facts] == ["edr_av_deploye"]
    assert facts[0].origin is Origin.EXTRACTION
    assert facts[0].source_quote


# --- flag resolution (auditor rules) ---

def test_apply_flags_correct_and_discard():
    facts, flags = questionnaire_answers_to_facts([
        ExtractedAnswer(question_id="taille_effectif", found=True, answer="beaucoup",
                        plausibility="implausible", plausibility_reason="pas un nombre"),
        ExtractedAnswer(question_id="secteur_activite", found=True, answer="???",
                        plausibility="unclear", plausibility_reason="incompréhensible"),
    ], "q.docx")
    human = ScriptedHuman(flag_decisions={"taille_effectif": "420", "secteur_activite": None})
    out = apply_flags(facts, flags, human)
    values = {f.field_name: f.value for f in out}
    assert values.get("taille_effectif") == "420"       # corrected by auditor
    assert "secteur_activite" not in values             # discarded by auditor
    assert set(human.reviewed) == {"taille_effectif", "secteur_activite"}


# --- full ingestion flow (facts -> mission context) ---

def test_complete_intake_from_facts_runs_followups_and_validates():
    declaration_facts, _ = questionnaire_answers_to_facts([
        ExtractedAnswer(question_id="organisation_nom", found=True, answer="Clinique Test"),
        ExtractedAnswer(question_id="secteur_activite", found=True, answer="Santé"),
        ExtractedAnswer(question_id="applicable_frameworks", found=True, answer="RGPD, NIST"),
        ExtractedAnswer(question_id="donnees_personnelles_traitees", found=True, answer="Oui"),
    ], "questionnaire.docx")
    # An EDR value found only in a supporting document -> confirmed by the auditor.
    extraction_facts = supporting_answers_to_facts([
        ExtractedAnswer(question_id="edr_av_deploye", found=True, answer="Defender",
                        source_quote="EDR: Microsoft Defender"),
    ], "politique.pdf")

    human = ScriptedHuman()  # answers every follow-up with a default, confirms doc-only values
    mc = complete_intake_from_facts(declaration_facts, extraction_facts, human)

    assert mc.organisation_nom == "Clinique Test"
    assert mc.secteur_activite == "Santé"
    assert mc.applicable_frameworks == ["RGPD", "NIST"]        # parsed from comma text
    assert mc.value("edr_av_deploye") == "Defender"           # doc-only value confirmed
    # A critical field like processus_metier_critiques was missing -> it was asked.
    assert "processus_metier_critiques" in human.asked


# --- incremental checkpointing + resume (persistence, phase A) ---

def _identity_facts():
    facts, _ = questionnaire_answers_to_facts([
        ExtractedAnswer(question_id="organisation_nom", found=True, answer="Horizon"),
        ExtractedAnswer(question_id="secteur_activite", found=True, answer="Santé"),
        ExtractedAnswer(question_id="applicable_frameworks", found=True, answer="RGPD"),
    ], "questionnaire.pdf")
    return facts


def test_checkpoint_fires_after_each_answer():
    calls: list[int] = []
    complete_intake_from_facts(_identity_facts(), [], ScriptedHuman(),
                               checkpoint=lambda facts: calls.append(len(facts)))
    assert len(calls) >= 2                 # at least the post-validation save + follow-up answers
    assert calls == sorted(calls)          # fact set only grows


def test_resume_skips_already_answered_questions():
    facts = _identity_facts()
    facts.append(next(iter(questionnaire_answers_to_facts(
        [ExtractedAnswer(question_id="edr_av_deploye", found=True, answer="CrowdStrike")], "q")[0])))
    human = ScriptedHuman()
    resume_intake(facts, human)
    assert "organisation_nom" not in human.asked   # identity already saved
    assert "edr_av_deploye" not in human.asked      # already answered
    assert "sauvegarde_strategie" in human.asked    # still missing -> asked


def test_mid_intake_crash_reopen_and_continue(tmp_path):
    db = tmp_path / "mission.db"
    # First session: save a partial intake, then "crash" (close the connection).
    conn = connect(db)
    repo = MissionRepository(conn)
    mid = repo.create_mission("Horizon", ["RGPD"])
    mission_state.checkpoint_mission_context(repo, mid, assemble_from_facts(_identity_facts()))
    conn.close()

    # New session: reopen the file and continue from the checkpoint.
    conn2 = connect(db)
    repo2 = MissionRepository(conn2)
    saved = mission_state.load_mission_context(repo2, mid)
    human = ScriptedHuman()
    mc = resume_intake(saved.facts, human,
                       checkpoint=lambda f: mission_state.checkpoint_mission_context(
                           repo2, mid, assemble_from_facts(f)))

    assert mc.organisation_nom == "Horizon"            # kept across the crash
    assert "organisation_nom" not in human.asked        # not re-asked
    assert mc.get("sauvegarde_strategie") is not None    # remaining questions completed
    conn2.close()
