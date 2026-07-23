"""Conversational turn handler for intake (conception §2).

Every time the auditor types something at a follow-up question, one LLM call
decides what they meant — an answer, a question, or something unclear — and
reacts: capture the answer, explain the question, answer the auditor's question
(grounded in the mission context), or push back on a nonsensical answer. The
auditor still decides; the agent never invents a value.
"""

from __future__ import annotations

import json
import time
from typing import Protocol

from pydantic import BaseModel

from ebios_rm.config import get_model
from ebios_rm.domain.fact import Fact


class TurnResult(BaseModel):
    """What the agent made of one auditor input."""

    is_answer: bool          # True = the input answers the current question
    answer: str = ""         # the captured/normalized answer when is_answer
    reply: str = ""          # message to show the auditor (explanation, answer, or note)


class ConversationRunner(Protocol):
    def handle_turn(
        self,
        question: str,
        explanation: str,
        user_input: str,
        facts: list[Fact],
        history: list[dict],
    ) -> TurnResult:
        ...


_SYSTEM = """\
Tu es un assistant EBIOS Risk Manager qui aide l'auditeur à remplir le contexte
d'une mission. Tu es intelligent et conversationnel, pas un formulaire figé.

À chaque tour, l'auditeur écrit quelque chose pendant qu'une question précise lui
est posée. Décide ce qu'il veut :
- Si c'est une RÉPONSE à la question courante : is_answer=true, answer = la valeur
  normalisée et claire, reply = éventuelle courte remarque (ex. si la réponse
  semble incohérente ou trop vague, signale-le brièvement — mais tu la retiens
  quand même, c'est l'auditeur qui tranche).
- Si l'auditeur POSE une question, demande une clarification, ou dit « que veux-tu
  dire » : is_answer=false, reply = ta réponse utile. Explique la question dans un
  langage simple, ou réponds à partir des faits déjà connus de la mission. Si
  l'information n'est pas connue, dis-le — n'invente jamais.
- Si c'est hors sujet ou incompréhensible : is_answer=false, reply = ramène
  poliment l'auditeur à la question courante.

Réponds en français, concis, au format structuré demandé.
"""


def _facts_block(facts: list[Fact]) -> str:
    known = {f.field_name: f.value for f in facts if f.value not in (None, "")}
    return json.dumps(known, ensure_ascii=False)


class AgnoConversationRunner:
    def __init__(self, model=None, *, max_attempts: int = 5, base_delay: float = 4.0, progress=print) -> None:
        self._model = model or get_model()
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._progress = progress

    def handle_turn(self, question, explanation, user_input, facts, history) -> TurnResult:
        from agno.agent import Agent  # noqa: PLC0415

        self._progress("   (l'agent réfléchit...)")
        prompt = (
            f"QUESTION COURANTE : {question}\n"
            f"EXPLICATION DE LA QUESTION : {explanation}\n"
            f"FAITS DÉJÀ CONNUS : {_facts_block(facts)}\n"
            f"ÉCHANGE RÉCENT : {json.dumps(history[-6:], ensure_ascii=False)}\n\n"
            f"L'AUDITEUR ÉCRIT : {user_input}"
        )
        last: object = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                agent = Agent(model=self._model, instructions=_SYSTEM,
                              output_schema=TurnResult, markdown=False)
                content = agent.run(prompt).content
            except Exception as exc:  # noqa: BLE001
                last = exc
            else:
                if isinstance(content, TurnResult):
                    return content
                last = content
            if attempt < self._max_attempts:
                time.sleep(self._base_delay * attempt)
        # Agent unreachable: treat the raw input as the answer rather than block the auditor.
        return TurnResult(is_answer=True, answer=user_input,
                          reply=f"(assistant indisponible, réponse enregistrée telle quelle : {str(last)[:80]})")
