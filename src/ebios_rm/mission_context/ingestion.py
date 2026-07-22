"""Document ingestion — filled questionnaire + supporting docs -> Facts (conception §4, §5, §11).

The agent reads documents and *proposes* extracted answers with a plausibility
judgment; this module converts those proposals into Facts under the provenance
rules and collects the answers the agent flagged as implausible/unclear so the
auditor can rule on them (the AI flags, the auditor decides — §2).

Origin rules:
- Answers taken from the client's own filled questionnaire -> 'declaration'
  (the questionnaire *is* the intake form, returned as a document); the client's
  written text is kept as source_quote for traceability.
- Answers extracted from a supporting document (policy, network diagram, prior
  report) -> 'extraction', with a mandatory source_quote (§5.3); any extraction
  without a citation is dropped before it reaches the auditor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import Confidence, FactStatus, Origin
from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.questionnaire import Question, all_questions, question_by_id

PLAUSIBILITY_OK = "ok"
PLAUSIBILITY_IMPLAUSIBLE = "implausible"
PLAUSIBILITY_UNCLEAR = "unclear"


class ExtractedAnswer(BaseModel):
    """One answer the agent read from a document (conception §11)."""

    question_id: str
    found: bool = False
    answer: str = ""
    source_quote: str = ""  # exact supporting text from the document
    plausibility: str = PLAUSIBILITY_OK  # ok | implausible | unclear
    plausibility_reason: str = ""        # why flagged (empty when ok)


class ExtractedAnswerBatch(BaseModel):
    """Structured-output wrapper for a batch of extracted answers."""

    answers: list[ExtractedAnswer] = Field(default_factory=list)


@dataclass
class AnswerFlag:
    """An answer the agent could not accept at face value — for the auditor to rule on (§2)."""

    question_id: str
    question: str
    answer: str
    kind: str  # 'implausible' | 'unclear'
    reason: str


class IngestionRunner(Protocol):
    """The LLM boundary for reading documents (conception §11)."""

    def extract_questionnaire(self, doc_text: str, questions: list[Question]) -> list[ExtractedAnswer]:
        """Read a filled intake questionnaire: per question, the client's answer + a plausibility check."""
        ...

    def extract_supporting(
        self, doc_text: str, doc_name: str, questions: list[Question]
    ) -> list[ExtractedAnswer]:
        """Read a supporting document: extract facts that map to intake questions, each with a quote."""
        ...


def _valid_question_ids() -> set[str]:
    return {q.id for q in all_questions()}


def questionnaire_answers_to_facts(
    answers: list[ExtractedAnswer], doc_name: str
) -> tuple[list[Fact], list[AnswerFlag]]:
    """Convert filled-questionnaire answers into declaration Facts + plausibility flags (conception §4, §11)."""
    valid = _valid_question_ids()
    qby_id = question_by_id()
    facts: list[Fact] = []
    flags: list[AnswerFlag] = []
    for a in answers:
        if a.question_id not in valid:
            continue  # never accept an answer to a question that does not exist
        if not a.found or not a.answer.strip():
            continue
        facts.append(
            Fact(
                field_name=a.question_id,
                value=a.answer.strip(),
                origin=Origin.DECLARATION,
                source_document=doc_name,
                source_quote=(a.source_quote.strip() or None),
                confidence=Confidence.HIGH,
                status=FactStatus.DECLARED,
            )
        )
        if a.plausibility in {PLAUSIBILITY_IMPLAUSIBLE, PLAUSIBILITY_UNCLEAR}:
            flags.append(
                AnswerFlag(
                    question_id=a.question_id,
                    question=qby_id[a.question_id].question,
                    answer=a.answer.strip(),
                    kind=a.plausibility,
                    reason=a.plausibility_reason.strip(),
                )
            )
    return facts, flags


def supporting_answers_to_facts(answers: list[ExtractedAnswer], doc_name: str) -> list[Fact]:
    """Convert supporting-document answers into extraction Facts (conception §5.3, §11).

    Extraction requires a non-empty source_quote — answers without one are dropped,
    exactly as validate_extraction would reject them.
    """
    valid = _valid_question_ids()
    facts: list[Fact] = []
    for a in answers:
        if a.question_id not in valid:
            continue
        if not a.found or not a.answer.strip() or not a.source_quote.strip():
            continue
        facts.append(
            Fact.extraction(
                a.question_id,
                a.answer.strip(),
                source_document=doc_name,
                source_quote=a.source_quote.strip(),
            )
        )
    return facts
