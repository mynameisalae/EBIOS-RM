"""Agno-backed Workshop 1 agent runner (conception §3.2, §10.1, §15).

Implements Workshop1AgentRunner using Agno + OpenRouter. Agno is imported lazily
so the deterministic core and its tests never require it. Each call builds an
Agent with the appropriate structured output_schema and returns response.content.

Note (conception §3.2): free OpenRouter models do not reliably support tool
calling, on which a Toolkit-based agent would depend. Workshop 1 therefore drives
the model through structured output only — the compliance queries
(get_baseline_controls, get_legal_impact_provisions) run in code via the
ReferenceRepository, and their results are passed into the prompt. This keeps the
dev model (nvidia/nemotron-3-ultra-550b-a55b:free) usable while preserving the
evaluation-by-evidence discipline, which is enforced in assessment.py.
"""

from __future__ import annotations

import time
from typing import TypeVar

from pydantic import BaseModel

from ebios_rm.config import get_model
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.reference_repository import BaselineControl
from ebios_rm.workshops.workshop1_cadrage import prompts
from ebios_rm.workshops.workshop1_cadrage.agent_runner import (
    ControlAssessmentBatch,
    LegalImpactAssignment,
    LegalImpactBatch,
)
from ebios_rm.workshops.workshop1_cadrage.models import (
    CadrageProposal,
    ControlAssessmentProposal,
)


T = TypeVar("T", bound=BaseModel)


class Workshop1AgentError(RuntimeError):
    """Raised when the model cannot return the expected structured output.

    On an API error or an unparseable response, Agno returns the raw string as
    response.content instead of the schema. Rather than let that surface as an
    opaque AttributeError downstream, the runner retries with backoff and then
    fails loudly — a failed LLM call is never silently reinterpreted as a
    methodology outcome (an empty gap list, a clean verdict...).
    """


class AgnoWorkshop1Runner:
    """Concrete Workshop1AgentRunner backed by Agno + OpenRouter."""

    def __init__(self, model=None, *, max_attempts: int = 4, base_delay: float = 3.0, progress=print) -> None:
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
        """Run one structured call, retrying transient failures with backoff (conception §3.2 note)."""
        self._progress(f"   {what}...")
        last: object = None
        for attempt in range(1, self._max_attempts + 1):
            if attempt > 1:
                self._progress(f"   ... nouvel essai {attempt}/{self._max_attempts} ({what})")
            try:
                response = self._agent(output_schema).run(prompt)
                content = response.content
            except Exception as exc:  # noqa: BLE001 — Agno/network errors are heterogeneous
                last = exc
            else:
                if isinstance(content, output_schema):
                    return content
                last = content  # a raw string (API error / parse failure) — retry
            if attempt < self._max_attempts:
                time.sleep(self._base_delay * attempt)
        raise Workshop1AgentError(
            f"Model did not return {output_schema.__name__} for {what} after "
            f"{self._max_attempts} attempts. Last result: {str(last)[:300]!r}"
        )

    def propose_cadrage(self, mission_context: MissionContext) -> CadrageProposal:
        return self._run_structured(
            CadrageProposal, prompts.cadrage_prompt(mission_context), what="cadrage"
        )

    def assess_controls(
        self,
        mission_context: MissionContext,
        framework: str,
        controls: list[BaselineControl],
    ) -> list[ControlAssessmentProposal]:
        if not controls:
            return []
        batch = self._run_structured(
            ControlAssessmentBatch,
            prompts.controls_prompt(mission_context, framework, controls),
            what=f"baseline assessment ({framework})",
        )
        return batch.assessments

    def assess_legal_impacts(
        self,
        mission_context: MissionContext,
        events: list[FearedEvent],
        provisions: list[BaselineControl],
    ) -> list[LegalImpactAssignment]:
        if not events or not provisions:
            return []
        batch = self._run_structured(
            LegalImpactBatch,
            prompts.legal_impacts_prompt(mission_context, events, provisions),
            what="legal-impact assessment",
        )
        return batch.impacts
