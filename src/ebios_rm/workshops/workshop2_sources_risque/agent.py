"""Agno-backed Workshop 2 agent runner (white-box §16; conception §3.2, §10.1).

Implements Workshop2AgentRunner using Agno + OpenRouter. Agno is imported lazily
so the deterministic core and its tests never require it.

Structured output only, no tool calling: free OpenRouter models do not reliably
support tool calls, so the approved SR/OV base is read in code (plugins.registry)
and passed into the prompt. The evidence and methodology discipline is enforced
in assessment.py either way.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from ebios_rm.agent_runtime import StructuredCallFailed, run_structured
from ebios_rm.config import get_model
from ebios_rm.domain.risk_source import ObjectifVise, RiskSource
from ebios_rm.plugins.registry import EbiosBase
from ebios_rm.workshops.workshop2_sources_risque import prompts
from ebios_rm.workshops.workshop2_sources_risque.models import (
    CoupleBatch,
    CoupleProposal,
    ObjectifViseBatch,
    ObjectifViseProposal,
    RiskSourceBatch,
    RiskSourceProposal,
    Workshop2Input,
)

T = TypeVar("T", bound=BaseModel)


class Workshop2AgentError(RuntimeError):
    """The model could not return the expected structured output.

    Raised rather than swallowed: a failed LLM call must never be reinterpreted as
    a methodology outcome (no plausible source found, an empty couple list...).
    """


class AgnoWorkshop2Runner:
    """Concrete Workshop2AgentRunner backed by Agno + OpenRouter."""

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
            raise Workshop2AgentError(str(exc)) from exc

    def propose_sources(
        self, w2_input: Workshop2Input, base: EbiosBase,
        revision_notes: list[str] | None = None,
    ) -> list[RiskSourceProposal]:
        batch = self._run_structured(
            RiskSourceBatch,
            prompts.sources_prompt(w2_input, base, revision_notes),
            what="sources de risque candidates",
        )
        return batch.sources

    def propose_objectifs(
        self, w2_input: Workshop2Input, base: EbiosBase, sources: list[RiskSource],
        revision_notes: list[str] | None = None,
    ) -> list[ObjectifViseProposal]:
        if not sources:
            return []
        batch = self._run_structured(
            ObjectifViseBatch,
            prompts.objectifs_prompt(w2_input, base, sources, revision_notes),
            what="objectifs visés candidats",
        )
        return batch.objectifs

    def propose_couples(
        self, w2_input: Workshop2Input, sources: list[RiskSource],
        objectifs: list[ObjectifVise], revision_notes: list[str] | None = None,
    ) -> list[CoupleProposal]:
        if not sources or not objectifs:
            return []
        batch = self._run_structured(
            CoupleBatch,
            prompts.couples_prompt(w2_input, sources, objectifs, revision_notes),
            what="couples SR/OV",
        )
        return batch.couples
