"""Priority matrix over the questionnaire catalog — what gets asked, what never does (§7, §11.1)."""

from ebios_rm.domain.enums import PriorityLevel
from ebios_rm.mission_context.priority_matrix import catalog_follow_up_questions


def test_unanswered_question_is_asked():
    names = {q.field_name for q in catalog_follow_up_questions({})}
    assert "edr_av_deploye" in names
    assert "sauvegarde_strategie" in names


def test_answered_question_is_never_reasked():
    answers = {"organisation_nom": "Clinique Test", "edr_av_deploye": "Defender"}
    names = {q.field_name for q in catalog_follow_up_questions(answers)}
    assert "organisation_nom" not in names
    assert "edr_av_deploye" not in names


def test_optional_question_is_never_asked():
    # documents_fournis is askable=False — genuinely optional, never raised.
    names = {q.field_name for q in catalog_follow_up_questions({})}
    assert "documents_fournis" not in names


def test_conditional_question_follows_its_trigger():
    without = {q.field_name for q in catalog_follow_up_questions({"donnees_personnelles_traitees": "Non"})}
    assert "categories_donnees_personnelles" not in without

    with_pii = {q.field_name for q in catalog_follow_up_questions({"donnees_personnelles_traitees": "Oui"})}
    assert "categories_donnees_personnelles" in with_pii


def test_critical_questions_sort_before_important():
    priorities = [q.priority for q in catalog_follow_up_questions({})]
    assert priorities == sorted(priorities, key=lambda p: 0 if p is PriorityLevel.CRITICAL else 1)
    assert PriorityLevel.CRITICAL in priorities
