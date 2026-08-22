"""Read the documents like an auditor before interrogating one (conception §2, §7).

The catalog decides what to ask by looking up a question's own field name. That makes
the returned document a script rather than a helper: an answer written in another
field's prose, or spread across a supporting document, leaves the slot empty and the
question gets asked again — the auditor answers twice. And a slot filled with "oui" is
indistinguishable from one filled properly, so a thin answer is never challenged.

One pass over the whole fact set fixes both. For each question still pending the model
says whether the facts already answer it (naming which fact), whether the answer on
record is too thin to use, or whether it is genuinely missing. Nothing is recorded
without the auditor accepting it, and anything the model does not settle is asked
exactly as before.
"""

from __future__ import annotations

import json
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from ebios_rm.agent_runtime import StructuredCallFailed, facts_as_json, run_structured
from ebios_rm.config import get_model
from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.priority_matrix import FollowUpQuestion

# Questions reviewed per call, matching the ingestion's batch size: one structured
# response covering the whole catalog overflows the output budget.
QUESTIONS_PER_CALL = 12


class QuestionReview(BaseModel):
    """What the known facts already say about one pending question."""

    field_name: str
    status: Literal["answered", "thin", "missing"]
    # status == 'answered': the answer the facts establish, and the fact it comes from.
    answer: str = ""
    based_on_fact: str = ""
    # status == 'thin': what is on record is unusable — say what is missing from it.
    missing_detail: str = ""


class IntakeReviewBatch(BaseModel):
    reviews: list[QuestionReview] = Field(default_factory=list)


class IntakeReviewRunner(Protocol):
    def review(self, facts: list[Fact], pending: list[FollowUpQuestion]) -> list[QuestionReview]:
        ...


_SYSTEM = """\
Tu es un auditeur EBIOS Risk Manager qui relit le dossier remis par le client avant
de l'interroger. Le dossier est une aide, pas un formulaire : une réponse peut se
trouver ailleurs que dans la case prévue.

Pour chaque question en attente, choisis un statut :
- "answered" : les faits connus répondent DÉJÀ à cette question, même si c'est écrit
  dans la réponse à une autre question ou dans un document annexe. Renseigne answer
  (la réponse telle qu'elle ressort des faits) et based_on_fact (le field_name EXACT
  du fait qui l'établit). Ne déduis pas au-delà de ce qui est écrit.
- "thin" : un fait existe mais il est trop pauvre pour être exploité (« oui », un mot
  isolé, une réponse qui élude). Renseigne missing_detail : ce qu'il faut demander en
  plus. Ne remplis PAS answer.
- "missing" : rien dans les faits ne répond à cette question.

Règles absolues :
- Tu n'inventes JAMAIS une réponse. Dans le doute, réponds "missing".
- based_on_fact doit être un field_name qui existe réellement dans les faits fournis.
- Une réponse plausible mais non écrite dans les faits est un "missing", pas un
  "answered".

Réponds uniquement au format structuré demandé.
"""


class AgnoIntakeReviewRunner:
    """Concrete IntakeReviewRunner backed by Agno + OpenRouter."""

    def __init__(self, model=None, *, max_attempts: int = 4, base_delay: float = 3.0,
                 progress=print) -> None:
        self._model = model or get_model()
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._progress = progress

    def review(self, facts: list[Fact], pending: list[FollowUpQuestion]) -> list[QuestionReview]:
        from agno.agent import Agent  # noqa: PLC0415

        out: list[QuestionReview] = []
        slices = [pending[i:i + QUESTIONS_PER_CALL] for i in range(0, len(pending), QUESTIONS_PER_CALL)]
        for i, chunk in enumerate(slices, 1):
            questions = json.dumps(
                [{"field_name": q.field_name, "question": q.question} for q in chunk],
                ensure_ascii=False, indent=2,
            )
            self._progress(f"   relecture du dossier, lot {i}/{len(slices)}...")
            try:
                batch = run_structured(
                    lambda: Agent(model=self._model, instructions=_SYSTEM,
                                  output_schema=IntakeReviewBatch, markdown=False),
                    f"FAITS CONNUS :\n{facts_as_json(facts)}\n\nQUESTIONS EN ATTENTE :\n{questions}",
                    IntakeReviewBatch,
                    what=f"relecture du dossier {i}/{len(slices)}",
                    max_attempts=self._max_attempts, base_delay=self._base_delay,
                    progress=self._progress,
                )
            except StructuredCallFailed as exc:
                # A failed review is not a finding: every question of this slice stays
                # pending and gets asked normally. Never treated as 'already answered'.
                self._progress(f"   (relecture indisponible ce lot : {str(exc)[:100]})")
                continue
            out.extend(batch.reviews)
        return out


def valid_reviews(
    reviews: list[QuestionReview], facts: list[Fact], pending: list[FollowUpQuestion]
) -> tuple[list[QuestionReview], list[QuestionReview]]:
    """Split into (already answered, thin), dropping anything the model got wrong.

    An 'answered' review is kept only when it names a fact that exists and carries an
    actual answer — the same evidence rule the baseline assessment applies. Everything
    dropped simply stays pending, so a bad review costs a question, never a fact.
    """
    known = {f.field_name for f in facts}
    asked = {q.field_name for q in pending}
    answered: list[QuestionReview] = []
    thin: list[QuestionReview] = []
    for r in reviews:
        if r.field_name not in asked:
            continue
        if r.status == "answered" and r.answer.strip() and r.based_on_fact in known:
            answered.append(r)
        elif r.status == "thin" and r.missing_detail.strip():
            thin.append(r)
    return answered, thin


def enrich(question: FollowUpQuestion, thin: list[QuestionReview]) -> FollowUpQuestion:
    """Re-frame a question whose answer on record is too thin, instead of asking it cold.

    « La MFA est-elle en place ? » to someone who already said yes wastes the turn; what
    is missing is where it applies. The question text is kept — only the help text says
    what to add, so the auditor sees what the agent already has.
    """
    detail = next((r.missing_detail for r in thin if r.field_name == question.field_name), "")
    if not detail:
        return question
    return FollowUpQuestion(
        question.field_name, question.question, question.priority,
        f"Déjà partiellement répondu. Ce qui manque : {detail}",
    )
