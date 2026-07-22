"""Agno-backed ingestion runner (conception §2, §5, §11).

Reads a filled questionnaire / supporting document and returns extracted answers
with a plausibility judgment. Same discipline as the workshop agent: the model
only proposes; provenance and acceptance are enforced downstream (ingestion.py)
and by the auditor. Agno is imported lazily so the deterministic core stays
importable without it.
"""

from __future__ import annotations

import json
import time

from ebios_rm.config import get_model
from ebios_rm.mission_context.ingestion import ExtractedAnswer, ExtractedAnswerBatch
from ebios_rm.mission_context.questionnaire import Question

_SYSTEM = """\
Tu es un assistant d'ingestion documentaire pour une mission EBIOS Risk Manager.
Tu lis un document et tu en extrais des réponses, sans jamais rien inventer.

Règles absolues :
- Tu n'extrais que ce qui est réellement présent dans le document. Si une réponse
  n'y figure pas, mets found=false — n'invente jamais de valeur.
- Pour chaque réponse, cite dans source_quote le passage exact du document qui la
  justifie. Sans passage exact, la réponse ne pourra pas être retenue.
- Contrôle de bon sens : si une réponse est incohérente, absurde, hors sujet, ou
  se contredit avec une autre réponse du même document, signale-le avec
  plausibility='implausible' (aberrant) ou 'unclear' (ambigu/à clarifier) et
  explique brièvement dans plausibility_reason. Sinon plausibility='ok'.
- Tu ne corriges jamais toi-même une réponse douteuse ; tu la signales seulement.
- Tu réponds uniquement au format structuré demandé.
"""


def _questions_block(questions: list[Question]) -> str:
    return json.dumps(
        [{"question_id": q.id, "question": q.question} for q in questions],
        ensure_ascii=False, indent=2,
    )


def _chunk(questions: list[Question], size: int) -> list[list[Question]]:
    return [questions[i:i + size] for i in range(0, len(questions), size)]


class AgnoIngestionRunner:
    """Concrete IngestionRunner backed by Agno + OpenRouter.

    Extraction is done in small batches of questions (``batch_size``) so each
    structured response stays well within the model's output budget — a single
    call covering all ~65 questions overflows and gets truncated into invalid JSON.
    """

    def __init__(
        self, model=None, *, max_attempts: int = 4, base_delay: float = 3.0, batch_size: int = 12
    ) -> None:
        self._model = model or get_model()
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._batch_size = batch_size

    def _run(self, prompt: str, *, what: str) -> list[ExtractedAnswer]:
        from agno.agent import Agent  # noqa: PLC0415

        last: object = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                agent = Agent(model=self._model, instructions=_SYSTEM,
                              output_schema=ExtractedAnswerBatch, markdown=False)
                content = agent.run(prompt).content
            except Exception as exc:  # noqa: BLE001
                last = exc
            else:
                if isinstance(content, ExtractedAnswerBatch):
                    return content.answers
                last = content
            if attempt < self._max_attempts:
                time.sleep(self._base_delay * attempt)
        raise RuntimeError(
            f"Ingestion did not return structured answers for {what} after "
            f"{self._max_attempts} attempts. Last: {str(last)[:200]!r}"
        )

    def extract_questionnaire(self, doc_text: str, questions: list[Question]) -> list[ExtractedAnswer]:
        collected: list[ExtractedAnswer] = []
        for batch in _chunk(questions, self._batch_size):
            prompt = (
                "Voici un questionnaire de contexte REMPLI par le client. Pour chaque question "
                "ci-dessous, extrais la réponse fournie par le client (found=true et answer), "
                "en citant le passage exact (source_quote), et évalue sa plausibilité. Si aucune "
                "réponse n'est fournie pour une question, mets found=false.\n\n"
                f"QUESTIONS:\n{_questions_block(batch)}\n\n"
                f"DOCUMENT REMPLI:\n{doc_text}"
            )
            collected.extend(self._run(prompt, what="questionnaire"))
        return collected

    def extract_supporting(
        self, doc_text: str, doc_name: str, questions: list[Question]
    ) -> list[ExtractedAnswer]:
        collected: list[ExtractedAnswer] = []
        for batch in _chunk(questions, self._batch_size):
            prompt = (
                f"Voici un document justificatif fourni en complément ('{doc_name}'). Extrais-en "
                "toute information qui répond à l'une des questions ci-dessous (found=true, answer, "
                "et source_quote OBLIGATOIRE citant le passage exact). N'extrais que ce qui est "
                "réellement écrit dans le document.\n\n"
                f"QUESTIONS:\n{_questions_block(batch)}\n\n"
                f"DOCUMENT:\n{doc_text}"
            )
            collected.extend(self._run(prompt, what=f"supporting:{doc_name}"))
        return collected
