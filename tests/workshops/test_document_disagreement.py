"""Supplied documents are scrutinised, and they can disagree with each other (§11)."""

from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.ingestion import ExtractedAnswer, supporting_answers_to_facts
from ebios_rm.mission_context.validation import validate

_MFA_YES = "MFA active sur Microsoft 365"
_MFA_NO = "Pas de MFA sur cette application"


def _extraction(value, doc):
    return Fact.extraction("authentification_forte", value, source_document=doc,
                           source_quote=value)


def test_the_form_and_a_document_disagreeing_is_raised():
    result = validate([Fact.declaration("authentification_forte", _MFA_YES)],
                      [_extraction(_MFA_NO, "audit.pdf")])
    assert len(result.contradictions) == 1


def test_no_document_is_silently_overwritten_by_the_next_one():
    # Keyed by field name, the last document read used to win and the first vanished —
    # the auditor never learned two documents disagreed.
    result = validate([Fact.declaration("authentification_forte", _MFA_YES)],
                      [_extraction(_MFA_YES, "policy.pdf"), _extraction(_MFA_NO, "audit.pdf")])

    assert len(result.contradictions) == 1
    contradiction = result.contradictions[0]
    assert contradiction.extraction.source_document == "audit.pdf"   # the one that disagrees
    assert contradiction.declaration.value == _MFA_YES               # the form is still the reference


def test_two_documents_disagreeing_while_the_form_is_silent_is_raised():
    # Nothing in the questionnaire covers the field; without this the disagreement was
    # invisible and whichever document was read last became the fact.
    result = validate([], [_extraction(_MFA_YES, "policy.pdf"), _extraction(_MFA_NO, "audit.pdf")])

    assert len(result.contradictions) == 1
    assert result.document_only == []
    c = result.contradictions[0]
    assert c.has_declaration is False
    assert {c.declaration.source_document, c.extraction.source_document} == {"policy.pdf", "audit.pdf"}


def test_documents_that_agree_still_need_only_one_confirmation():
    result = validate([], [_extraction(_MFA_YES, "policy.pdf"), _extraction(_MFA_YES, "annexe.pdf")])
    assert result.contradictions == []
    assert len(result.document_only) == 1


def test_three_disagreeing_documents_are_all_offered():
    result = validate([], [_extraction(_MFA_YES, "a.pdf"), _extraction(_MFA_NO, "b.pdf"),
                           _extraction("MFA partielle", "c.pdf")])
    c = result.contradictions[0]
    assert len(c.others) == 1                       # a + b + one more, none dropped


def test_an_implausible_supporting_document_is_flagged_like_the_form():
    # A supplied PDF is the client's word too; an absurd statement in one used to reach
    # the workshop unexamined unless it happened to contradict the form on that field.
    answers = [ExtractedAnswer(question_id="taille_effectif", found=True, answer="3 personnes",
                               source_quote="a team of 3 manages 50,000 servers",
                               plausibility="implausible",
                               plausibility_reason="3 personnes pour 50 000 serveurs")]
    facts, flags = supporting_answers_to_facts(answers, "handover.pdf")

    assert len(facts) == 1
    assert len(flags) == 1
    assert "handover.pdf" in flags[0].question      # the auditor sees which document
