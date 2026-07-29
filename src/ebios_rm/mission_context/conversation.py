"""Conversational turn handler for intake (conception §2).

Every time the auditor types something at a follow-up question, one LLM call
decides what they meant — an answer, a question, or something unclear — and
reacts: capture the answer, explain the question, answer the auditor's question
(grounded in the mission context), or push back on a nonsensical answer. The
auditor still decides; the agent never invents a value.
"""

from __future__ import annotations

import json
from typing import Literal, Protocol

from pydantic import BaseModel

from ebios_rm.agent_runtime import StructuredCallFailed, facts_as_json, run_structured
from ebios_rm.config import get_model
from ebios_rm.domain.fact import Fact


class TurnResult(BaseModel):
    """What the agent made of one auditor input.

    ``intent`` is stated by the model rather than inferred from the reply text:
    'answer' = the question is answered and the loop may advance;
    'answer_and_more' = answered, and one follow-up is worth asking before advancing;
    'question' = the auditor asked something / needs an explanation;
    'insufficient' = they replied, but too vaguely to record.

    'answer_and_more' exists because a real turn can be both. Forced to pick one, a
    model either drops the answer or writes its follow-up into the reply while still
    labelling the turn 'answer' — and the loop, which reads only the label, advances
    and leaves that question printed on screen but never asked.
    """

    intent: Literal["answer", "answer_and_more", "question", "insufficient"]
    answer: str = ""         # the captured/normalized answer when intent == 'answer'
    reply: str = ""          # message to show the auditor (explanation, answer, or note)

    @property
    def is_answer(self) -> bool:
        return self.intent in {"answer", "answer_and_more"}

    @property
    def wants_more(self) -> bool:
        return self.intent == "answer_and_more"


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
Choisis intent parmi exactement quatre valeurs :
- intent="answer" : l'auditeur a RÉPONDU de façon exploitable. answer = la valeur
  normalisée et claire. reply = éventuelle courte remarque (jamais une demande).
- intent="answer_and_more" : il a RÉPONDU, et une seule question de suivi mérite
  d'être posée avant de continuer. answer = ce qu'il a répondu ; reply = cette
  question de suivi. À n'utiliser que si le complément est vraiment utile : ce n'est
  pas un moyen d'enchaîner les questions indéfiniment.
- intent="insufficient" : il a répondu, mais trop vaguement (« oui », « non », un
  mot isolé) alors que la question attend un détail (un produit, des règles, une
  fréquence). reply = demande précisément ce qui manque. N'enregistre rien.
- intent="question" : il POSE une question, demande une clarification, dit « que
  veux-tu dire », ou écrit quelque chose d'incompréhensible / hors sujet. reply =
  ta réponse utile : explique la question en langage simple, ou réponds à partir
  des faits déjà connus. Si l'information n'est pas connue, dis-le — n'invente jamais.

RÈGLE ABSOLUE : si ton reply pose une question ou réclame une précision, intent
n'est JAMAIS "answer" — c'est "answer_and_more" si tu as tout de même capté une
réponse, sinon "insufficient" ou "question". Ne laisse jamais une question dans ton
reply sous un intent qui fait avancer la boucle : elle ne serait jamais posée.

CAS DE LA CONFIRMATION : si TON tour précédent (voir ÉCHANGE RÉCENT) proposait une
reformulation à valider (« est-ce bien cela ? »), un « oui » isolé confirme CETTE
reformulation — intent="answer", answer = la reformulation que tu avais proposée.
Un « non » isolé la rejette — intent="question", reply = demande la correction.
Dans ce cas précis, ne réévalue pas ce « oui »/« non » comme s'il répondait à la
question d'origine : ce serait boucler sur une réponse déjà obtenue.

TON reply N'AJOUTE AUCUN FAIT. Tu peux reformuler ce que l'auditeur vient de dire,
jamais le compléter : « c'est noté, vos collaborateurs utilisent des portables
professionnels » alors qu'il a seulement dit « oui » invente un fait qu'il lira
comme acquis. Reste strictement à ce qui a été dit ou figure dans les faits connus.

Réponds en français, concis, au format structuré demandé.
"""


def _facts_block(facts: list[Fact]) -> str:
    return facts_as_json(facts)


class AgnoConversationRunner:
    def __init__(self, model=None, *, max_attempts: int = 5, base_delay: float = 4.0, progress=print) -> None:
        self._model = model or get_model()
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._progress = progress

    def handle_turn(self, question, explanation, user_input, facts, history) -> TurnResult:
        from agno.agent import Agent  # noqa: PLC0415

        prompt = (
            f"QUESTION COURANTE : {question}\n"
            f"EXPLICATION DE LA QUESTION : {explanation}\n"
            f"FAITS DÉJÀ CONNUS : {_facts_block(facts)}\n"
            f"ÉCHANGE RÉCENT : {json.dumps(history[-6:], ensure_ascii=False)}\n\n"
            f"L'AUDITEUR ÉCRIT : {user_input}"
        )
        try:
            return run_structured(
                lambda: Agent(model=self._model, instructions=_SYSTEM,
                              output_schema=TurnResult, markdown=False),
                prompt, TurnResult,
                what="l'agent réfléchit",
                max_attempts=self._max_attempts, base_delay=self._base_delay, progress=self._progress,
            )
        except StructuredCallFailed as exc:
            # Agent unreachable: treat the raw input as the answer rather than block the auditor.
            return TurnResult(intent="answer", answer=user_input,
                              reply=f"(assistant indisponible, réponse enregistrée telle quelle : {str(exc)[:80]})")
