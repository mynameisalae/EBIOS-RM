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

from ebios_rm.agent_runtime import StructuredCallFailed, arun_structured, run_structured
from ebios_rm.config import get_model
from ebios_rm.domain.operational_scenario import OperationalScenario
from ebios_rm.repositories.attack_repository import AttackCatalogue
from ebios_rm.workshops.workshop4_scenarios_operationnels import prompts
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import (
    CoherenceBatch,
    CoherenceFindingProposal,
    ScenarioAnalysisProposal,
    Workshop4Input,
)


class Workshop4AgentError(RuntimeError):
    """The model could not return the expected structured output.

    Raised rather than swallowed: a failed call is never an analysis (an empty path,
    a scenario nobody could attack) nor a clean coherence review.
    """


class AgnoWorkshop4Runner:
    """Concrete Workshop4AgentRunner backed by Agno + OpenRouter."""

    def __init__(self, model=None, *, max_attempts: int = 4, base_delay: float = 3.0,
                 progress=print) -> None:
        self._model = model or get_model()
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._progress = progress

    def _agent(self, instructions: str, output_schema):
        from agno.agent import Agent  # noqa: PLC0415 — lazy so tests don't need Agno

        return Agent(model=self._model, instructions=instructions,
                     output_schema=output_schema, markdown=False)

    async def analyse_scenario(
        self, w4_input: Workshop4Input, pending: OperationalScenario, catalogue: AttackCatalogue,
    ) -> ScenarioAnalysisProposal:
        redo = f", reprise {pending.iterations}" if pending.iterations else ""
        try:
            return await arun_structured(
                lambda: self._agent(prompts.SYSTEM_INSTRUCTIONS, ScenarioAnalysisProposal),
                prompts.analysis_prompt(w4_input, pending, catalogue),
                ScenarioAnalysisProposal,
                what=f"analyse opérationnelle {pending.scenario_strategique_id}{redo}",
                max_attempts=self._max_attempts, base_delay=self._base_delay, progress=self._progress,
            )
        except StructuredCallFailed as exc:
            raise Workshop4AgentError(str(exc)) from exc

    def check_coherence(
        self, w4_input: Workshop4Input, scenarios: list[OperationalScenario],
    ) -> list[CoherenceFindingProposal]:
        try:
            batch = run_structured(
                lambda: self._agent(prompts.COHERENCE_INSTRUCTIONS, CoherenceBatch),
                prompts.coherence_prompt(w4_input, scenarios),
                CoherenceBatch,
                what="vérification de cohérence des scénarios opérationnels",
                max_attempts=self._max_attempts, base_delay=self._base_delay, progress=self._progress,
            )
        except StructuredCallFailed as exc:
            raise Workshop4AgentError(str(exc)) from exc
        return batch.constats
