"""Document ingestion + answer sanity-check (conception §2, §5, §11)."""

from fakes import FakeIngestionRunner, ScriptedHuman

from ebios_rm.domain.enums import Origin
from ebios_rm.mission_context.ingestion import (
    ExtractedAnswer,
    questionnaire_answers_to_facts,
    supporting_answers_to_facts,
)
from ebios_rm.workshops.workshop1_cadrage.intake_ingestion import (
    apply_flags,
    complete_intake_from_facts,
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
