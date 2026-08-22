"""Dynamic expert follow-ups on top of the fixed catalog (conception §2)."""

from fakes import FakeAuditorReviewRunner, ScriptedHuman

from ebios_rm.mission_context.ingestion import ExtractedAnswer, questionnaire_answers_to_facts
from ebios_rm.workshops.workshop1_cadrage.auditor_review import (
    MAX_ROUNDS,
    MAX_TOTAL_QUESTIONS,
    AuditorFollowUp,
    already_asked,
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


def test_asked_questions_survive_for_a_resumed_review():
    # The question text is kept on each Fact, so a review resumed from the checkpoint
    # knows what was already asked instead of regenerating a reworded round 1.
    proposal = AuditorFollowUp(question="Quelle version de CrowdStrike Falcon ?", why="x")
    reviewer = FakeAuditorReviewRunner({1: [proposal]})
    human = ScriptedHuman(answers={to_followup_question(proposal).field_name: "7.x"})
    mc = complete_intake_from_facts(_minimal_facts(), [], human, auditor_reviewer=reviewer)

    assert "Quelle version de CrowdStrike Falcon ?" in already_asked(mc)
    # Catalog questions are recorded the same way — the reviewer must not re-ask them either.
    assert all(f.question for f in mc.facts if f.field_name.startswith("AUD-"))
    assert len(already_asked(mc)) > 1


def test_skipped_question_is_still_recorded_as_asked():
    human = ScriptedHuman(skips={"processus_metier_critiques": "sera fourni plus tard"})
    mc = complete_intake_from_facts(_minimal_facts(), [], human)
    skipped = mc.get("processus_metier_critiques")

    assert skipped.justification == "sera fourni plus tard"
    assert skipped.question in already_asked(mc)   # never proposed again as if new


def test_duplicate_question_across_rounds_is_not_reasked():
    same_question = AuditorFollowUp(question="Quelle est la fréquence de mise à jour ?", why="x")
    reviewer = FakeAuditorReviewRunner({1: [same_question], 2: [same_question]})
    human = ScriptedHuman(answers={to_followup_question(same_question).field_name: "Automatique quotidienne"})
    mc = complete_intake_from_facts(_minimal_facts(), [], human, auditor_reviewer=reviewer)

    aud_facts = [f for f in mc.facts if f.field_name.startswith("AUD-")]
    assert len(aud_facts) == 1  # asked once in round 1, round 2's identical proposal skipped


def test_trivially_reworded_question_is_not_reasked():
    # The prompt asks the model not to repeat itself "même reformulée"; that is a
    # request, not a guarantee. Case, accents, punctuation and word order must be
    # caught in code, so a free model cannot re-interrogate the auditor by rewrapping.
    first = AuditorFollowUp(question="Quelle est la fréquence de mise à jour ?", why="x")
    reworded = AuditorFollowUp(question="  de quelle MISE A JOUR est la frequence ???  ", why="x")
    assert to_followup_question(first).field_name == to_followup_question(reworded).field_name

    reviewer = FakeAuditorReviewRunner({1: [first], 2: [reworded]})
    human = ScriptedHuman(answers={to_followup_question(first).field_name: "Quotidienne"})
    mc = complete_intake_from_facts(_minimal_facts(), [], human, auditor_reviewer=reviewer)

    assert len([f for f in mc.facts if f.field_name.startswith("AUD-")]) == 1


def test_a_genuinely_different_question_still_gets_through():
    first = AuditorFollowUp(question="Quelle est la fréquence de mise à jour ?", why="x")
    other = AuditorFollowUp(question="Le MFA est-il actif sur les accès distants ?", why="x")
    assert to_followup_question(first).field_name != to_followup_question(other).field_name


def test_a_question_citing_a_fact_that_does_not_exist_is_dropped():
    # The prompt asks for a fact-grounded question; without this the rule binds nothing,
    # and the auditor cannot tell an invented justification from a real one.
    from ebios_rm.mission_context.mission_context import assemble_from_facts
    from ebios_rm.workshops.workshop1_cadrage.auditor_review import grounded

    mc = assemble_from_facts(_minimal_facts())
    proposals = [
        AuditorFollowUp(question="Quelle version de l'EDR ?", why="x", based_on_fact="edr_av_deploye"),
        AuditorFollowUp(question="Combien de datacenters ?", why="x", based_on_fact="fait_invente"),
        AuditorFollowUp(question="Avez-vous un DPO ?", why="lacune RGPD", based_on_fact=""),
    ]
    kept = [p.question for p in grounded(proposals, mc)]

    assert kept == ["Quelle version de l'EDR ?", "Avez-vous un DPO ?"]   # gap-based stays


def test_the_motivating_fact_is_shown_to_the_auditor():
    q = to_followup_question(
        AuditorFollowUp(question="Quelle version ?", why="EDR nommé sans version",
                        based_on_fact="edr_av_deploye"))
    assert "edr_av_deploye" in q.help_text
