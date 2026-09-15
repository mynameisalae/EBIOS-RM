"""Agno-backed Workshop 2 agent runner (white-box §16; conception §3.2, §10.1).

Implements Workshop2AgentRunner using Agno + OpenRouter. Agno is imported lazily
so the deterministic core and its tests never require it.

Structured output only, no tool calling: free OpenRouter models do not reliably
support tool calls, so the approved SR/OV base is read in code (plugins.registry)
and passed into the prompt. The evidence and methodology discipline is enforced
in assessment.py either way.
"""

from __future__ import annotations

from ebios_rm.agent_runtime import AgnoRunner
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

class AgnoWorkshop2Runner(AgnoRunner):
    """Concrete Workshop2AgentRunner backed by Agno + OpenRouter.

    A call that cannot produce its schema raises StructuredCallFailed
    (agent_runtime), never a methodology outcome (no plausible source found, an
    empty couple list...).
    """

    INSTRUCTIONS = prompts.SYSTEM_INSTRUCTIONS

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
