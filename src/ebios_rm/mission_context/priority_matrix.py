"""The information priority matrix — Critical / Important, two levels only (conception §7).

Critical: the workshop cannot continue without an explicit supply or confirmation.
Important: the AI asks for the missing information; Skip/Unknown/Not-Applicable are
accepted only with a non-empty justification (§8). There is no silent-omission
third level — a field that would once have been "Optionnel" is simply not tracked
as a Fact (§5.2) and therefore never raised here.

This module only *decides what to ask*. It never fills a value and never assumes
one — that is the auditor's job (principe directeur, §2).
"""

from __future__ import annotations

from dataclasses import dataclass

from ebios_rm.domain.enums import PriorityLevel
from ebios_rm.mission_context.intake_form import FIELD_SPECS, FieldSpec, OrgContextForm


def _is_empty(value: object) -> bool:
    """A field is empty (unanswered) when it is None, blank text, or an empty list.

    Booleans are never empty — False is a valid, explicit answer.
    """
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


@dataclass(frozen=True)
class FollowUpQuestion:
    """A question the auditor must answer (Critical) or may skip-with-reason (Important)."""

    field_name: str
    question: str
    priority: PriorityLevel
    help_text: str = ""

    @property
    def blocking(self) -> bool:
        """Critical questions block the workshop; Important ones can be skipped with a justification."""
        return self.priority is PriorityLevel.CRITICAL


def _should_ask(spec: FieldSpec, form: OrgContextForm) -> bool:
    if not spec.askable:
        return False
    if spec.depends_on_true is not None and getattr(form, spec.depends_on_true) is not True:
        # Conditional field whose trigger is not set — not applicable, so never asked.
        return False
    return _is_empty(getattr(form, spec.name))


def follow_up_questions(form: OrgContextForm) -> list[FollowUpQuestion]:
    """Return the questions to raise for still-empty fields, Critical first (conception §7).

    A field already answered in the form — or confirmed by a document, once its
    value has landed on the form — is never asked again ("aucune question inutile
    posée si l'évidence est déjà disponible", §11).
    """
    questions = [
        FollowUpQuestion(spec.name, spec.question, spec.priority, spec.help_text)
        for spec in FIELD_SPECS
        if _should_ask(spec, form)
    ]
    # Critical before Important; stable within a level (declaration order).
    questions.sort(key=lambda q: 0 if q.priority is PriorityLevel.CRITICAL else 1)
    return questions


def blocking_questions(form: OrgContextForm) -> list[FollowUpQuestion]:
    """Only the Critical questions that must be answered before the workshop can proceed."""
    return [q for q in follow_up_questions(form) if q.blocking]


# --- Catalog-based follow-ups (used by the document-ingestion path) ---

_AFFIRMATIVE = {"oui", "yes", "true", "vrai", "o", "y", "1"}


def _is_affirmative(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in _AFFIRMATIVE or "oui" in str(value).casefold()


def catalog_follow_up_questions(answers: dict[str, object]) -> list[FollowUpQuestion]:
    """Which catalog questions remain to be asked, given the answers gathered so far.

    Mirrors the two-level matrix over the full professional questionnaire
    (conception §7): a question already answered (by the client's document or a
    previous follow-up) is never re-asked; genuinely optional questions
    (askable=False) and unmet conditional questions (depends_on_true) are skipped.
    """
    from ebios_rm.mission_context.questionnaire import QUESTIONNAIRE  # local import avoids a cycle

    questions: list[FollowUpQuestion] = []
    for section in QUESTIONNAIRE:
        for q in section.questions:
            if not q.askable:
                continue
            if q.depends_on_true is not None and not _is_affirmative(answers.get(q.depends_on_true)):
                continue
            if not _is_empty(answers.get(q.id)):
                continue
            questions.append(FollowUpQuestion(q.id, q.question, q.priority, q.explanation))
    questions.sort(key=lambda x: 0 if x.priority is PriorityLevel.CRITICAL else 1)
    return questions
