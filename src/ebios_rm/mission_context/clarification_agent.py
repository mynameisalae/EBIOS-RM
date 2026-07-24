"""Agno-backed clarification runner (conception §2).

Answers the auditor's question strictly from the mission context (and optional
workshop output). The system instruction forbids inventing anything: if the
answer is not supported by the provided facts, the model must set answered=false.
Agno is imported lazily so the deterministic core stays importable without it.
"""

from __future__ import annotations

import json

from ebios_rm.agent_runtime import StructuredCallFailed, facts_as_json, run_structured
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
    header = json.dumps(
        {
            "organisation_nom": mc.organisation_nom,
            "secteur_activite": mc.secteur_activite,
            "applicable_frameworks": mc.applicable_frameworks,
        },
        ensure_ascii=False, indent=2,
    )
    return f"{header}\nfacts: {facts_as_json(mc.facts, with_origin=True)}"


class AgnoClarificationRunner:
    """Concrete ClarificationRunner backed by Agno + OpenRouter."""

    def __init__(self, model=None, *, max_attempts: int = 4, base_delay: float = 3.0, progress=print) -> None:
        self._model = model or get_model()
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._progress = progress

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

        try:
            return run_structured(
                lambda: Agent(model=self._model, instructions=_SYSTEM,
                              output_schema=ClarificationAnswer, markdown=False),
                prompt, ClarificationAnswer,
                what="recherche dans le contexte",
                max_attempts=self._max_attempts, base_delay=self._base_delay, progress=self._progress,
            )
        except StructuredCallFailed as exc:
            # A failed clarification is not an audit output — degrade to an explicit non-answer.
            return ClarificationAnswer(
                answered=False,
                answer=f"La demande de clarification n'a pas abouti techniquement ({str(exc)[:150]}).",
            )
