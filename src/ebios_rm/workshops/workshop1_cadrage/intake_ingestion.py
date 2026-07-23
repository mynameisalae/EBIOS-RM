"""Document-ingestion intake flow for Workshop 1 (conception §2, §5, §11).

Reads the filled questionnaire (and optional supporting documents), turns answers
into Facts, lets the auditor rule on anything the agent flagged, asks follow-up
questions for what is still missing over the full professional catalog, runs the
three-case validation, and assembles the Mission Context. Every human decision
goes through the HumanInterface; nothing is assumed or auto-resolved.
"""

from __future__ import annotations

from pathlib import Path

from ebios_rm.domain.enums import Confidence, FactStatus, Origin
from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.document_reader import read_document
from ebios_rm.mission_context.ingestion import (
    AnswerFlag,
    IngestionRunner,
    questionnaire_answers_to_facts,
    supporting_answers_to_facts,
)
from ebios_rm.mission_context.mission_context import MissionContext, assemble_from_facts
from ebios_rm.mission_context.priority_matrix import catalog_follow_up_questions
from ebios_rm.mission_context.questionnaire import all_questions
from ebios_rm.mission_context.validation import validate
from ebios_rm.workshops.workshop1_cadrage.human_interface import HumanInterface, SkipRequested


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


def _ask_follow_ups(
    declaration_facts: list[Fact], human: HumanInterface, covered_ids: set[str] | None = None
) -> None:
    """Ask catalog follow-ups for still-missing fields, re-evaluating conditionals as answers arrive.

    ``covered_ids`` are fields already supplied by a supporting document (extraction);
    they are never re-asked — the auditor confirms them through validation instead,
    so no needless question is posed (conception §11).
    """
    covered = covered_ids or set()
    if hasattr(human, "bind_facts"):  # conversational interface: give the agent live context
        human.bind_facts(declaration_facts)
    asked: set[str] = set()
    while True:
        answers = _answers_map(declaration_facts)
        answers.update({cid: True for cid in covered})  # count doc-provided fields as answered
        pending = [
            q for q in catalog_follow_up_questions(answers)
            if q.field_name not in asked
        ]
        if not pending:
            break
        for question in pending:
            asked.add(question.field_name)
            outcome = human.ask_followup(question)
            if isinstance(outcome, SkipRequested):
                declaration_facts.append(Fact(
                    field_name=question.field_name, value=None, origin=Origin.DECLARATION,
                    confidence=Confidence.LOW, status=FactStatus.SKIPPED, justification=outcome.reason,
                ))
            else:
                declaration_facts.append(Fact.declaration(question.field_name, outcome))


def complete_intake_from_facts(
    declaration_facts: list[Fact],
    extraction_facts: list[Fact],
    human: HumanInterface,
) -> MissionContext:
    """Follow-ups + three-case validation + assembly, over the catalog (conception §7, §11)."""
    covered_by_documents = {f.field_name for f in extraction_facts}
    _ask_follow_ups(declaration_facts, human, covered_ids=covered_by_documents)

    result = validate(declaration_facts, extraction_facts)
    final_facts: list[Fact] = list(result.verified) + list(result.declaration_only)

    for extr in result.document_only:
        if human.confirm_document_only(extr.field_name, extr.value, extr.source_quote or ""):
            final_facts.append(extr.model_copy(update={"status": FactStatus.APPROVED, "validated_by": "auditor"}))

    for contradiction in result.contradictions:
        resolved = human.resolve_contradiction(contradiction)
        final_facts.append(Fact(
            field_name=contradiction.field_name, value=resolved, origin=Origin.DECLARATION,
            confidence=Confidence.HIGH, status=FactStatus.APPROVED, validated_by="auditor",
            justification="Résolution de contradiction par l'auditeur (§11).",
        ))

    return assemble_from_facts(final_facts)


def complete_intake_from_documents(
    intake_doc_path: str | Path,
    supporting_doc_paths: list[str | Path],
    ingestion_runner: IngestionRunner,
    human: HumanInterface,
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
        extraction_facts.extend(supporting_answers_to_facts(s_answers, sp_path.name))

    return complete_intake_from_facts(declaration_facts, extraction_facts, human)
