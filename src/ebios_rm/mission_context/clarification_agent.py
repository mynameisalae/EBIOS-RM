"""Agno-backed clarification runner (conception §2).

Answers the auditor's question strictly from the mission context (and optional
workshop output). The system instruction forbids inventing anything: if the
answer is not supported by the provided facts, the model must set answered=false.
Agno is imported lazily so the deterministic core stays importable without it.
"""

from __future__ import annotations

import json
import time

from ebios_rm.config import get_model
from ebios_rm.mission_context.clarification import ClarificationAnswer
from ebios_rm.mission_context.mission_context import MissionContext

_SYSTEM = """\
Tu réponds aux questions de l'auditeur sur une mission EBIOS Risk Manager, en
t'appuyant UNIQUEMENT sur le contexte fourni (faits de la mission et, le cas
échéant, le résultat de l'atelier).

Règles absolues :
- Tu ne réponds qu'à partir des informations présentes dans le contexte. Tu
  n'inventes jamais, tu ne supposes jamais, tu ne complètes jamais de mémoire.
- Si l'information nécessaire n'est pas dans le contexte, mets answered=false et
  explique brièvement ce qui manque — ne devine pas.
- Quand tu réponds (answered=true), cite dans based_on_facts les field_name des
  faits (ou éléments) sur lesquels repose ta réponse.
- Réponds de façon claire et concise, en français, au format structuré demandé.
"""


def _facts_block(mc: MissionContext) -> str:
    return json.dumps(
        {
            "organisation_nom": mc.organisation_nom,
            "secteur_activite": mc.secteur_activite,
            "applicable_frameworks": mc.applicable_frameworks,
            "facts": [
                {"field_name": f.field_name, "value": f.value, "origin": f.origin.value}
                for f in mc.facts
            ],
        },
        ensure_ascii=False, indent=2,
    )


class AgnoClarificationRunner:
    """Concrete ClarificationRunner backed by Agno + OpenRouter."""

    def __init__(self, model=None, *, max_attempts: int = 4, base_delay: float = 3.0) -> None:
        self._model = model or get_model()
        self._max_attempts = max_attempts
        self._base_delay = base_delay

    def answer(
        self,
        question: str,
        mission_context: MissionContext,
        workshop_output: object | None = None,
    ) -> ClarificationAnswer:
        from agno.agent import Agent  # noqa: PLC0415

        output_block = ""
        if workshop_output is not None:
            dumped = workshop_output.model_dump(mode="json") if hasattr(workshop_output, "model_dump") else workshop_output
            output_block = f"\n\nRÉSULTAT DE L'ATELIER:\n{json.dumps(dumped, ensure_ascii=False, indent=2)}"

        prompt = (
            f"QUESTION DE L'AUDITEUR:\n{question}\n\n"
            f"CONTEXTE DE LA MISSION:\n{_facts_block(mission_context)}{output_block}"
        )

        last: object = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                agent = Agent(model=self._model, instructions=_SYSTEM,
                              output_schema=ClarificationAnswer, markdown=False)
                content = agent.run(prompt).content
            except Exception as exc:  # noqa: BLE001
                last = exc
            else:
                if isinstance(content, ClarificationAnswer):
                    return content
                last = content
            if attempt < self._max_attempts:
                time.sleep(self._base_delay * attempt)
        # A failed clarification is not an audit output — degrade to an explicit non-answer.
        return ClarificationAnswer(
            answered=False,
            answer=f"La demande de clarification n'a pas abouti techniquement (dernier retour : {str(last)[:150]}).",
        )
