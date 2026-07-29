"""The dossier is read before the auditor is interrogated (conception §2, §7)."""

from fakes import ScriptedHuman

from ebios_rm.domain.enums import Origin
from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.ingestion import ExtractedAnswer, questionnaire_answers_to_facts
from ebios_rm.mission_context.priority_matrix import FollowUpQuestion
from ebios_rm.domain.enums import PriorityLevel
from ebios_rm.workshops.workshop1_cadrage.intake_ingestion import complete_intake_from_facts
from ebios_rm.workshops.workshop1_cadrage.intake_review import (
    QuestionReview,
    enrich,
    valid_reviews,
)


def _facts():
    facts, _ = questionnaire_answers_to_facts([
        ExtractedAnswer(question_id="organisation_nom", found=True, answer="ACME"),
        ExtractedAnswer(question_id="acces_distant_moyens", found=True,
                        answer="VPN obligatoire pour tout accès distant"),
    ], "questionnaire.docx")
    return facts


def _q(field_name):
    return FollowUpQuestion(field_name, f"question {field_name}", PriorityLevel.IMPORTANT, "")


def test_an_answer_living_in_another_field_is_recognised():
    pending = [_q("teletravail_autorise")]
    reviews = [QuestionReview(field_name="teletravail_autorise", status="answered",
                              answer="Oui, via VPN", based_on_fact="acces_distant_moyens")]

    answered, thin = valid_reviews(reviews, _facts(), pending)
    assert [r.field_name for r in answered] == ["teletravail_autorise"]
    assert thin == []


def test_a_review_citing_a_fact_that_does_not_exist_is_dropped():
    # The model must not talk a question away by inventing its source: it stays pending.
    reviews = [QuestionReview(field_name="teletravail_autorise", status="answered",
                              answer="Oui", based_on_fact="fait_inexistant")]
    answered, _ = valid_reviews(reviews, _facts(), [_q("teletravail_autorise")])
    assert answered == []


def test_an_answered_review_with_no_answer_is_dropped():
    reviews = [QuestionReview(field_name="teletravail_autorise", status="answered",
                              answer="   ", based_on_fact="acces_distant_moyens")]
    answered, _ = valid_reviews(reviews, _facts(), [_q("teletravail_autorise")])
    assert answered == []


def test_a_thin_answer_reframes_the_question_instead_of_asking_it_cold():
    thin = [QuestionReview(field_name="authentification_forte", status="thin",
                           missing_detail="sur quels systèmes elle s'applique")]
    question = enrich(_q("authentification_forte"), thin)

    assert "Ce qui manque" in question.help_text
    assert question.question == "question authentification_forte"   # the question itself is unchanged


def test_a_question_with_no_review_is_untouched():
    assert enrich(_q("wifi"), []).help_text == ""


class _Reviewer:
    """Claims every pending question is already answered by the first known fact."""

    def __init__(self, source):
        self._source = source
        self.calls = 0

    def review(self, facts, pending):
        self.calls += 1
        return [QuestionReview(field_name=q.field_name, status="answered",
                               answer=f"déduit pour {q.field_name}", based_on_fact=self._source)
                for q in pending]


def test_accepted_derivations_become_facts_and_are_not_asked():
    human = ScriptedHuman()
    reviewer = _Reviewer("acces_distant_moyens")
    mc = complete_intake_from_facts(_facts(), [], human, intake_reviewer=reviewer)

    derived = mc.get("teletravail_autorise")
    assert derived is not None and derived.origin is Origin.ASSESSMENT
    assert derived.assessment_basis == ["acces_distant_moyens"]
    assert reviewer.calls >= 1


def test_no_reviewer_keeps_the_old_behaviour():
    human = ScriptedHuman()
    mc = complete_intake_from_facts(_facts(), [], human)
    derived = mc.get("teletravail_autorise")
    assert derived is None or derived.origin is not Origin.ASSESSMENT
