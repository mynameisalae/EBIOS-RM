"""Agno-backed Workshop 4 runner (conception §3.1, §18; §3.2, §10.1).

Each analysis builds its own Agno Agent — N independent instances, never a Team
(§3.1) — awaited concurrently by workshop.run_analyses through asyncio.gather.
Agno is imported lazily so the deterministic core and its tests never require it.

Structured output only, no tool calling, same deviation as ateliers 1 to 3: free
OpenRouter models do not reliably call tools, so the ATT&CK queries run in code
and their result — the catalogue of active techniques — is in the prompt. The §18
check « IDs cited vs IDs the tools returned » is therefore made against that
catalogue, in assessment.py.
"""

from __future__ import annotations

from ebios_rm.agent_runtime import AgnoRunner
from ebios_rm.domain.operational_scenario import OperationalScenario
from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.repositories.attack_repository import AttackCatalogue
from ebios_rm.workshops.workshop4_scenarios_operationnels import prompts
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import (
    CoherenceBatch,
    CoherenceFindingProposal,
    ModeCandidateBatch,
    ModeCandidateProposal,
    ScenarioAnalysisProposal,
    Workshop4Input,
)


class AgnoWorkshop4Runner(AgnoRunner):
    """Concrete Workshop4AgentRunner backed by Agno + OpenRouter.

    Two roles, two sets of instructions: the sub-agent that analyses one scenario,
    and the reviewer that reads the confirmed set together. A call that cannot
    produce its schema raises StructuredCallFailed (agent_runtime) — never an
    analysis (an empty path, a scenario nobody could attack) nor a clean coherence
    review.
    """

    INSTRUCTIONS = prompts.SYSTEM_INSTRUCTIONS

    async def enumerate_modes(
        self, w4_input: Workshop4Input, scenario: StrategicScenario,
    ) -> list[ModeCandidateProposal]:
        batch = await self._arun_structured(
            ModeCandidateBatch,
            prompts.modes_prompt(w4_input, scenario),
            what=f"modes opératoires possibles {scenario.id}",
            instructions=prompts.ENUMERATION_INSTRUCTIONS,
        )
        return batch.modes

    async def analyse_scenario(
        self, w4_input: Workshop4Input, pending: OperationalScenario, catalogue: AttackCatalogue,
    ) -> ScenarioAnalysisProposal:
        redo = f", reprise {pending.iterations}" if pending.iterations else ""
        return await self._arun_structured(
            ScenarioAnalysisProposal,
            prompts.analysis_prompt(w4_input, pending, catalogue),
            what=f"analyse opérationnelle {pending.scenario_strategique_id}{redo}",
        )

    def check_coherence(
        self, w4_input: Workshop4Input, scenarios: list[OperationalScenario],
    ) -> list[CoherenceFindingProposal]:
        batch = self._run_structured(
            CoherenceBatch,
            prompts.coherence_prompt(w4_input, scenarios),
            what="vérification de cohérence des scénarios opérationnels",
            instructions=prompts.COHERENCE_INSTRUCTIONS,
        )
        return batch.constats
