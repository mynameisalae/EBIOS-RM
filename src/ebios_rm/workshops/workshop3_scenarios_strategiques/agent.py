"""Agno-backed Workshop 3 agent runner (conception §17; §3.2, §10.1).

Implements Workshop3AgentRunner using Agno + OpenRouter. Agno is imported lazily
so the deterministic core and its tests never require it.

One agent, two passes, structured output only — no tool calling: free OpenRouter
models do not reliably support it, and everything the passes need (the couples,
the context, the scenarios to criticise) is already in the prompt.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from ebios_rm.agent_runtime import StructuredCallFailed, run_structured
from ebios_rm.config import get_model
from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.workshops.workshop3_scenarios_strategiques import prompts
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import (
    CritiqueBatch,
    CritiqueVerdict,
    ScenarioBatch,
    ScenarioProposal,
    Workshop3Input,
)

T = TypeVar("T", bound=BaseModel)


class Workshop3AgentError(RuntimeError):
    """The model could not return the expected structured output.

    Raised rather than swallowed: a failed LLM call must never be reinterpreted as
    a methodology outcome (no scenario found, an empty critique).
    """


class AgnoWorkshop3Runner:
    """Concrete Workshop3AgentRunner backed by Agno + OpenRouter."""

    def __init__(self, model=None, *, max_attempts: int = 4, base_delay: float = 3.0,
                 progress=print) -> None:
        self._model = model or get_model()
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._progress = progress

    def _agent(self, output_schema):
        from agno.agent import Agent  # noqa: PLC0415 — lazy so tests don't need Agno

        return Agent(
            model=self._model,
            instructions=prompts.SYSTEM_INSTRUCTIONS,
            output_schema=output_schema,
            markdown=False,
        )

    def _run_structured(self, output_schema: type[T], prompt: str, *, what: str) -> T:
        try:
            return run_structured(
                lambda: self._agent(output_schema), prompt, output_schema,
                what=what,
                max_attempts=self._max_attempts, base_delay=self._base_delay,
                progress=self._progress,
            )
        except StructuredCallFailed as exc:
            raise Workshop3AgentError(str(exc)) from exc

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
