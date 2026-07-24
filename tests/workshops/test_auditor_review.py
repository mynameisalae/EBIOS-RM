"""Dynamic expert follow-ups on top of the fixed catalog (conception §2)."""

from fakes import FakeAuditorReviewRunner, ScriptedHuman

from ebios_rm.mission_context.ingestion import ExtractedAnswer, questionnaire_answers_to_facts
from ebios_rm.workshops.workshop1_cadrage.auditor_review import (
    MAX_ROUNDS,
    MAX_TOTAL_QUESTIONS,
    AuditorFollowUp,
    to_followup_question,
)
from ebios_rm.workshops.workshop1_cadrage.intake_ingestion import complete_intake_from_facts


def _minimal_facts():
    facts, _ = questionnaire_answers_to_facts([
        ExtractedAnswer(question_id="organisation_nom", found=True, answer="Clinique Test"),
        ExtractedAnswer(question_id="secteur_activite", found=True, answer="Santé"),
        ExtractedAnswer(question_id="edr_av_deploye", found=True, answer="CrowdStrike Falcon"),
    ], "questionnaire.docx")
    return facts


def test_no_review_runner_keeps_old_behavior():
    human = ScriptedHuman()
    mc = complete_intake_from_facts(_minimal_facts(), [], human, auditor_reviewer=None)
    assert not any(f.field_name.startswith("AUD-") for f in mc.facts)


def test_grounded_followup_is_asked_and_captured():
    reviewer = FakeAuditorReviewRunner({
        1: [AuditorFollowUp(question="Quelle version de CrowdStrike Falcon ?",
                            why="EDR nommé sans version précisée", priority="important",
                            based_on_fact="edr_av_deploye")],
    })
    human = ScriptedHuman(answers={to_followup_question(
        AuditorFollowUp(question="Quelle version de CrowdStrike Falcon ?", why="", based_on_fact="")
    ).field_name: "Falcon Insight XDR 7.x"})
    mc = complete_intake_from_facts(_minimal_facts(), [], human, auditor_reviewer=reviewer)

    aud_facts = [f for f in mc.facts if f.field_name.startswith("AUD-")]
    assert len(aud_facts) == 1
    assert aud_facts[0].value == "Falcon Insight XDR 7.x"
    assert reviewer.rounds_seen == [1, 2]  # round 2 ran and found nothing more (empty script)


def test_empty_round_stops_review_early():
    reviewer = FakeAuditorReviewRunner({1: []})  # nothing proposed -> should not reach round 2
    human = ScriptedHuman()
    complete_intake_from_facts(_minimal_facts(), [], human, auditor_reviewer=reviewer)
    assert reviewer.rounds_seen == [1]


def test_review_never_exceeds_max_rounds():
    always_one = {r: [AuditorFollowUp(question=f"Question round {r} ?", why="générique")]
                  for r in range(1, MAX_ROUNDS + 3)}  # more rounds than allowed, if it were unbounded
    reviewer = FakeAuditorReviewRunner(always_one)
    human = ScriptedHuman()
    complete_intake_from_facts(_minimal_facts(), [], human, auditor_reviewer=reviewer)
    assert reviewer.rounds_seen == list(range(1, MAX_ROUNDS + 1))


def test_keeps_probing_while_new_questions_come():
    # Five straight rounds of genuinely new questions: it must not stop at some
    # arbitrary small round count, only when the agent runs dry.
    script = {r: [AuditorFollowUp(question=f"Question spécifique {r} ?", why="creuse")] for r in range(1, 6)}
    reviewer = FakeAuditorReviewRunner(script)  # round 6 -> nothing -> stop
    human = ScriptedHuman()
    mc = complete_intake_from_facts(_minimal_facts(), [], human, auditor_reviewer=reviewer)

    assert reviewer.rounds_seen == [1, 2, 3, 4, 5, 6]
    assert len([f for f in mc.facts if f.field_name.startswith("AUD-")]) == 5


def test_stops_when_round_only_repeats_known_questions():
    repeat = AuditorFollowUp(question="Toujours la même question ?", why="x")
    reviewer = FakeAuditorReviewRunner({r: [repeat] for r in range(1, MAX_ROUNDS + 1)})
    human = ScriptedHuman()
    complete_intake_from_facts(_minimal_facts(), [], human, auditor_reviewer=reviewer)

    # Asked in round 1; round 2 brings nothing new -> stop, no runaway to MAX_ROUNDS.
    assert reviewer.rounds_seen == [1, 2]


def test_total_question_ceiling_caps_interrogation():
    # Every round floods with unique questions; the total ceiling must hold.
    script = {r: [AuditorFollowUp(question=f"Q{r}-{i} ?", why="x") for i in range(6)]
              for r in range(1, MAX_ROUNDS + 1)}
    reviewer = FakeAuditorReviewRunner(script)
    human = ScriptedHuman()
    mc = complete_intake_from_facts(_minimal_facts(), [], human, auditor_reviewer=reviewer)

    assert len([f for f in mc.facts if f.field_name.startswith("AUD-")]) == MAX_TOTAL_QUESTIONS


def test_duplicate_question_across_rounds_is_not_reasked():
    same_question = AuditorFollowUp(question="Quelle est la fréquence de mise à jour ?", why="x")
    reviewer = FakeAuditorReviewRunner({1: [same_question], 2: [same_question]})
    human = ScriptedHuman(answers={to_followup_question(same_question).field_name: "Automatique quotidienne"})
    mc = complete_intake_from_facts(_minimal_facts(), [], human, auditor_reviewer=reviewer)

    aud_facts = [f for f in mc.facts if f.field_name.startswith("AUD-")]
    assert len(aud_facts) == 1  # asked once in round 1, round 2's identical proposal skipped
