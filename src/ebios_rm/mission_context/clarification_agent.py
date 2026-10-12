"""Agno-backed clarification runner (conception §2).

Answers the auditor's question strictly from the mission context (and optional
workshop output). The system instruction forbids inventing anything: if the
answer is not supported by the provided facts, the model must set answered=false.
Agno is imported lazily so the deterministic core stays importable without it.
"""

from __future__ import annotations

import json

from ebios_rm.agent_runtime import AgnoRunner, StructuredCallFailed, facts_as_json
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


class AgnoClarificationRunner(AgnoRunner):
    """Concrete ClarificationRunner backed by Agno + OpenRouter."""

    INSTRUCTIONS = _SYSTEM

    def answer(
        self,
        question: str,
        mission_context: MissionContext,
        workshop_output: object | None = None,
    ) -> ClarificationAnswer:
        output_block = ""
        if workshop_output is not None:
            dumped = workshop_output.model_dump(mode="json") if hasattr(workshop_output, "model_dump") else workshop_output
            output_block = f"\n\nRÉSULTAT DE L'ATELIER:\n{json.dumps(dumped, ensure_ascii=False, indent=2)}"

        prompt = (
            f"QUESTION DE L'AUDITEUR:\n{question}\n\n"
            f"CONTEXTE DE LA MISSION:\n{_facts_block(mission_context)}{output_block}"
        )

        try:
            return self._run_structured(ClarificationAnswer, prompt, what="recherche dans le contexte")
        except StructuredCallFailed as exc:
            # A failed clarification is not an audit output — degrade to an explicit non-answer.
            return ClarificationAnswer(
                answered=False,
                answer=f"La demande de clarification n'a pas abouti techniquement ({str(exc)[:150]}).",
            )
