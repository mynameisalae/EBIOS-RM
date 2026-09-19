"""Agno-backed Workshop 5 runner (conception §3.1, §19; §10.1).

One call, real tool calling. Every other atelier's agent.py explains why it
avoids tool calls (free models do not call tools reliably) — this is the one
place the conception requires it anyway, so the risk is accepted here rather
than worked around: a call that never resolves into the schema still raises
StructuredCallFailed like any other (agent_runtime), and the caller (workshop.py)
treats it exactly like a failed call from any earlier atelier.
"""

from __future__ import annotations

from ebios_rm.agent_runtime import AgnoRunner
from ebios_rm.repositories.attack_repository import MitigationCatalogue
from ebios_rm.toolkits.attack_toolkit import AttackToolkit
from ebios_rm.workshops.workshop5_traitement_risque import prompts
from ebios_rm.workshops.workshop5_traitement_risque.models import MesuresBatch, Workshop5Input


class AgnoWorkshop5Runner(AgnoRunner):
    """Concrete Workshop5AgentRunner backed by Agno + OpenRouter + the ATT&CK tool."""

    INSTRUCTIONS = prompts.SYSTEM_INSTRUCTIONS

    def propose_mesures(self, w5_input: Workshop5Input, mitigations: MitigationCatalogue) -> MesuresBatch:
        toolkit = AttackToolkit(mitigations)
        return self._run_structured(
            MesuresBatch,
            prompts.proposal_prompt(w5_input),
            what="propositions de traitement du risque",
            tools=[toolkit],
        )
