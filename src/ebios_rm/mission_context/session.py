"""Working-session questions — what an atelier asks the client before it reasons.

The intake questionnaire is asked once, before atelier 1. Each later atelier can
still need something the form never covered: atelier 2 needs what makes a
particular actor plausible here, atelier 3 needs who is already connected to the
organisation. Those are put in session, to the client, and they are the same
mechanics every time — ask only what the context does not already answer, never
block on any of them, and keep a skip with its reason.

That mechanism lives here once. What differs is the list of questions, which each
atelier owns: the questions *are* the methodology, the asking is not.

Answers become Facts of origin ``declaration`` so they stay distinguishable from
the AI's own assumptions all the way into the workshop's justifications (§8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ebios_rm.domain.enums import Confidence, FactStatus, Origin, PriorityLevel
from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.priority_matrix import FollowUpQuestion
from ebios_rm.workshops.workshop1_cadrage.human_interface import HumanInterface, SkipRequested


@dataclass(frozen=True)
class SessionQuestion:
    """One session question and what it is there to decide."""

    field_name: str
    question: str
    help_text: str


class HasContext(Protocol):
    """A workshop input carrying context values and the Facts behind them.

    Workshop2Input and Workshop3Input both satisfy this; the session does not need
    to know which atelier it is running for.
    """

    contexte: dict[str, object]
    faits_contexte: list[Fact]


def _is_answered(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def pending_questions(
    questions: tuple[SessionQuestion, ...], target: HasContext
) -> list[FollowUpQuestion]:
    """The questions the context does not already answer.

    All Important: an atelier can be conducted without any single one of them, so
    none may block the study. A skip still costs a justification (§8).

    A skipped question counts as settled. Its Fact carries no value, so it never
    reaches ``contexte`` — asking on the strength of that alone would put the same
    question again at every rerun, and the auditor already said why they passed.
    """
    skipped = {f.field_name for f in target.faits_contexte if f.status is FactStatus.SKIPPED}
    return [
        FollowUpQuestion(
            field_name=q.field_name,
            question=q.question,
            priority=PriorityLevel.IMPORTANT,
            help_text=q.help_text,
        )
        for q in questions
        if q.field_name not in skipped and not _is_answered(target.contexte.get(q.field_name))
    ]


def ask_questions(
    questions: tuple[SessionQuestion, ...], target, human: HumanInterface
):
    """Run the session and return the enriched input — the original is left untouched.

    Returning a new value rather than mutating keeps the workshop a pure function
    over typed input, which is what makes pause/resume and replay the orchestrator's
    business instead of this module's.
    """
    enriched = target.model_copy(deep=True)
    for question in pending_questions(questions, target):
        outcome = human.ask_followup(question)
        if isinstance(outcome, SkipRequested):
            # The refusal is recorded, not discarded: an auditor reading the study
            # must see that the question was put and why it went unanswered.
            enriched.faits_contexte.append(Fact(
                field_name=question.field_name,
                value=None,
                origin=Origin.DECLARATION,
                confidence=Confidence.LOW,
                status=FactStatus.SKIPPED,
                justification=outcome.reason,
                question=question.question,
            ))
            continue
        answer = str(outcome).strip()
        if not answer:
            continue
        enriched.contexte[question.field_name] = answer
        enriched.faits_contexte.append(
            Fact.declaration(question.field_name, answer, question=question.question)
        )
    return enriched
