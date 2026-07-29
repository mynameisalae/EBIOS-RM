"""Document-ingestion intake flow for Workshop 1 (conception §2, §5, §11).

Reads the filled questionnaire (and optional supporting documents), turns answers
into Facts, lets the auditor rule on anything the agent flagged, asks follow-up
questions for what is still missing over the full professional catalog, runs the
three-case validation, and assembles the Mission Context. Every human decision
goes through the HumanInterface; nothing is assumed or auto-resolved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ebios_rm.domain.enums import Confidence, FactStatus, Origin
from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.document_reader import read_document
from ebios_rm.workshops.workshop1_cadrage.auditor_review import (
    MAX_ROUNDS,
    MAX_TOTAL_QUESTIONS,
    AuditorReviewRunner,
    to_followup_question,
)
from ebios_rm.mission_context.ingestion import (
    AnswerFlag,
    IngestionRunner,
    questionnaire_answers_to_facts,
    supporting_answers_to_facts,
)
from ebios_rm.mission_context.mission_context import MissionContext, assemble_from_facts
from ebios_rm.mission_context.priority_matrix import FollowUpQuestion, catalog_follow_up_questions
from ebios_rm.mission_context.questionnaire import all_questions
from ebios_rm.mission_context.validation import validate
from ebios_rm.workshops.workshop1_cadrage.human_interface import HumanInterface, SkipRequested
from ebios_rm.workshops.workshop1_cadrage.intake_review import (
    IntakeReviewRunner,
    enrich,
    valid_reviews,
)


def _answers_map(facts: list[Fact]) -> dict[str, object]:
    return {f.field_name: f.value for f in facts if f.value not in (None, "")}


def apply_flags(
    declaration_facts: list[Fact], flags: list[AnswerFlag], human: HumanInterface
) -> list[Fact]:
    """Let the auditor rule on each flagged answer: keep, correct, or discard (conception §2)."""
    remove: set[str] = set()
    updates: dict[str, str] = {}
    for flag in flags:
        decision = human.review_flag(flag)
        if decision is None:
            remove.add(flag.question_id)
        elif str(decision).strip() and str(decision).strip() != flag.answer:
            updates[flag.question_id] = str(decision).strip()

    out: list[Fact] = []
    for fact in declaration_facts:
        if fact.field_name in remove:
            continue
        if fact.field_name in updates:
            out.append(fact.model_copy(update={
                "value": updates[fact.field_name],
                "justification": "Réponse corrigée par l'auditeur après signalement de l'agent (§2).",
            }))
        else:
            out.append(fact)
    return out


# A checkpoint is called with the current fact set after every captured answer, so
# a mid-intake crash resumes at the next unanswered question (persistence, phase A).
Checkpoint = Callable[[list[Fact]], None]


def _noop_checkpoint(_facts: list[Fact]) -> None:
    pass


def _append_outcome(facts: list[Fact], question: FollowUpQuestion, outcome) -> None:
    """Record an answer (or a skip) together with the question that produced it.

    The question text is kept on the Fact so a resumed expert review can see what
    was already asked instead of re-proposing it reworded (its field_name is a hash).
    """
    if isinstance(outcome, SkipRequested):
        facts.append(Fact(
            field_name=question.field_name, value=None, origin=Origin.DECLARATION,
            confidence=Confidence.LOW, status=FactStatus.SKIPPED, justification=outcome.reason,
            question=question.question,
        ))
    else:
        facts.append(Fact.declaration(question.field_name, outcome, question=question.question))


def _apply_review(
    facts: list[Fact], pending: list[FollowUpQuestion], reviewer: IntakeReviewRunner | None,
    human: HumanInterface,
) -> list[FollowUpQuestion]:
    """Drop questions the documents already answer; sharpen the ones answered too thinly.

    The auditor confirms the derived answers in a single pass — one per question would
    trade a question for a confirmation and save nobody anything. Whatever they decline,
    and everything the review did not settle, is asked exactly as before (§2).
    """
    if reviewer is None or not pending:
        return pending

    answered, thin = valid_reviews(reviewer.review(facts, pending), facts, pending)
    accepted = human.confirm_derived_answers(answered) if answered else []
    by_field = {q.field_name: q for q in pending}
    for review in accepted:
        question = by_field[review.field_name]
        facts.append(Fact(
            field_name=review.field_name, value=review.answer, origin=Origin.ASSESSMENT,
            # The fact it was read from, so the trail survives into the report (§5.1).
            assessment_basis=[review.based_on_fact],
            confidence=Confidence.MEDIUM, status=FactStatus.APPROVED, validated_by="auditor",
            justification="Déjà répondu dans le dossier, confirmé par l'auditeur (§2, §7).",
            question=question.question,
        ))

    settled = {r.field_name for r in accepted}
    return [enrich(q, thin) for q in pending if q.field_name not in settled]


def _ask_follow_ups(facts: list[Fact], human: HumanInterface, checkpoint: Checkpoint,
                    reviewer: IntakeReviewRunner | None = None) -> None:
    """Ask catalog follow-ups for still-missing fields (conception §7, §11).

    Fields already present (from the questionnaire or a supporting document) are
    seen as answered by the catalog matrix and never re-asked. Every answer is
    checkpointed so the intake resumes at the next gap after a crash.
    """
    if hasattr(human, "bind_facts"):  # conversational interface: give the agent live context
        human.bind_facts(facts)
    asked: set[str] = set()
    while True:
        pending = [q for q in catalog_follow_up_questions(_answers_map(facts)) if q.field_name not in asked]
        if not pending:
            break
        pending = _apply_review(facts, pending, reviewer, human)
        for question in pending:
            asked.add(question.field_name)
            _append_outcome(facts, question, human.ask_followup(question))
            checkpoint(facts)


def _run_expert_review(
    facts: list[Fact], reviewer: AuditorReviewRunner, human: HumanInterface, checkpoint: Checkpoint
) -> None:
    """Dynamic professional follow-ups on top of the catalog (conception §2).

    Keeps probing while the auditor-agent still has something worth asking — the
    normal end condition, reached when a round proposes nothing new. MAX_ROUNDS /
    MAX_TOTAL_QUESTIONS are runaway backstops only. Reuses ask_followup entirely,
    and checkpoints each answer.
    """
    asked = {f.field_name for f in facts if f.field_name.startswith("AUD-")}  # already asked before a resume
    for round_number in range(1, MAX_ROUNDS + 1):
        proposals = reviewer.review(assemble_from_facts(facts), round_number)
        new = [p for p in proposals if to_followup_question(p).field_name not in asked]
        if not new:
            break
        for proposal in new:
            if len(asked) >= MAX_TOTAL_QUESTIONS:
                return
            fq = to_followup_question(proposal)
            asked.add(fq.field_name)
            _append_outcome(facts, fq, human.ask_followup(fq))
            checkpoint(facts)


def _follow_and_review(
    facts: list[Fact], human: HumanInterface,
    auditor_reviewer: AuditorReviewRunner | None, checkpoint: Checkpoint,
    intake_reviewer: IntakeReviewRunner | None = None,
) -> MissionContext:
    _ask_follow_ups(facts, human, checkpoint, intake_reviewer)
    if auditor_reviewer is not None:
        _run_expert_review(facts, auditor_reviewer, human, checkpoint)
    return assemble_from_facts(facts)


def complete_intake_from_facts(
    declaration_facts: list[Fact],
    extraction_facts: list[Fact],
    human: HumanInterface,
    auditor_reviewer: AuditorReviewRunner | None = None,
    checkpoint: Checkpoint = _noop_checkpoint,
    intake_reviewer: IntakeReviewRunner | None = None,
) -> MissionContext:
    """Three-case validation, then catalog follow-ups + expert review, over one fact set (§7, §11).

    Validation runs first so document facts, confirmations and contradiction
    resolutions land in the working set before the long Q&A; every subsequent
    answer is checkpointed for crash-safe resume.
    """
    result = validate(declaration_facts, extraction_facts)
    working: list[Fact] = list(result.verified) + list(result.declaration_only)

    for extr in result.document_only:
        if human.confirm_document_only(extr.field_name, extr.value, extr.source_quote or ""):
            working.append(extr.model_copy(update={"status": FactStatus.APPROVED, "validated_by": "auditor"}))

    for contradiction in result.contradictions:
        resolved = human.resolve_contradiction(contradiction)
        working.append(Fact(
            field_name=contradiction.field_name, value=resolved, origin=Origin.DECLARATION,
            confidence=Confidence.HIGH, status=FactStatus.APPROVED, validated_by="auditor",
            justification="Résolution de contradiction par l'auditeur (§11).",
        ))

    checkpoint(working)  # ingestion + validation done, saved before the interactive Q&A
    return _follow_and_review(working, human, auditor_reviewer, checkpoint, intake_reviewer)


def resume_intake(
    saved_facts: list[Fact],
    human: HumanInterface,
    auditor_reviewer: AuditorReviewRunner | None = None,
    checkpoint: Checkpoint = _noop_checkpoint,
    intake_reviewer: IntakeReviewRunner | None = None,
) -> MissionContext:
    """Continue a partially-completed intake from its checkpointed facts (persistence, phase A).

    Ingestion and validation are already reflected in ``saved_facts``; catalog
    follow-ups skip whatever is already answered and resume at the first gap.
    """
    return _follow_and_review(list(saved_facts), human, auditor_reviewer, checkpoint, intake_reviewer)


def complete_intake_from_documents(
    intake_doc_path: str | Path,
    supporting_doc_paths: list[str | Path],
    ingestion_runner: IngestionRunner,
    human: HumanInterface,
    auditor_reviewer: AuditorReviewRunner | None = None,
    checkpoint: Checkpoint = _noop_checkpoint,
    intake_reviewer: IntakeReviewRunner | None = None,
) -> MissionContext:
    """Full document-ingestion intake: filled questionnaire + supporting docs -> Mission Context."""
    questions = list(all_questions())

    intake_path = Path(intake_doc_path)
    q_answers = ingestion_runner.extract_questionnaire(read_document(intake_path), questions)
    declaration_facts, flags = questionnaire_answers_to_facts(q_answers, intake_path.name)
    declaration_facts = apply_flags(declaration_facts, flags, human)

    extraction_facts: list[Fact] = []
    for sp in supporting_doc_paths:
        sp_path = Path(sp)
        s_answers = ingestion_runner.extract_supporting(read_document(sp_path), sp_path.name, questions)
        s_facts, s_flags = supporting_answers_to_facts(s_answers, sp_path.name)
        extraction_facts.extend(s_facts)
        # Ruled on exactly like a questionnaire flag: the auditor keeps, corrects or
        # discards it before the value ever reaches validation.
        extraction_facts = apply_flags(extraction_facts, s_flags, human)

    return complete_intake_from_facts(
        declaration_facts, extraction_facts, human, auditor_reviewer, checkpoint, intake_reviewer
    )
