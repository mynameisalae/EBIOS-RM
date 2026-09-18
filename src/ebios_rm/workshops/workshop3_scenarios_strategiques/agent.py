"""Agno-backed Workshop 3 agent runner (conception §17; §3.2, §10.1).

Implements Workshop3AgentRunner using Agno + OpenRouter. Agno is imported lazily
so the deterministic core and its tests never require it.

One agent, two passes, structured output only — no tool calling: free OpenRouter
models do not reliably support it, and everything the passes need (the couples,
the context, the scenarios to criticise) is already in the prompt.
"""

from __future__ import annotations

from ebios_rm.agent_runtime import AgnoRunner
from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.workshops.workshop3_scenarios_strategiques import prompts
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import (
    CritiqueBatch,
    CritiqueVerdict,
    ScenarioBatch,
    ScenarioProposal,
    Workshop3Input,
)

class AgnoWorkshop3Runner(AgnoRunner):
    """Concrete Workshop3AgentRunner backed by Agno + OpenRouter.

    A call that cannot produce its schema raises StructuredCallFailed
    (agent_runtime), never a methodology outcome (no scenario found, an empty
    critique).
    """

    INSTRUCTIONS = prompts.SYSTEM_INSTRUCTIONS

    def propose_scenarios(
        self, w3_input: Workshop3Input, revision_notes: list[str] | None = None,
    ) -> list[ScenarioProposal]:
        if not w3_input.couples:
            return []
        batch = self._run_structured(
            ScenarioBatch,
            prompts.scenarios_prompt(w3_input, revision_notes),
            what="scénarios stratégiques candidats",
        )
        return batch.scenarios

    def critique_scenarios(
        self, w3_input: Workshop3Input, scenarios: list[StrategicScenario],
    ) -> list[CritiqueVerdict]:
        # Nothing to compare below two scenarios: the pass would cost a call to be
        # told that a single scenario does not repeat itself.
        if len(scenarios) < 2:
            return []
        batch = self._run_structured(
            CritiqueBatch,
            prompts.critique_prompt(w3_input, scenarios),
            what="relecture des scénarios (quasi-doublons)",
        )
        return batch.verdicts
