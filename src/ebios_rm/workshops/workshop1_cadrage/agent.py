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

from ebios_rm.agent_runtime import AgnoRunner
from ebios_rm.domain.essential_asset import EssentialAsset
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


# Controls assessed per LLM call. Matches the ingestion's question batch size for the
# same reason: a structured response covering a whole referential overflows the output
# budget and degrades recall long before it does.
CONTROLS_PER_CALL = 12


class AgnoWorkshop1Runner(AgnoRunner):
    """Concrete Workshop1AgentRunner backed by Agno + OpenRouter.

    A call that cannot produce its schema after every retry raises
    StructuredCallFailed (agent_runtime) — never silently reinterpreted as a
    methodology outcome (an empty gap list, a clean verdict...).
    """

    INSTRUCTIONS = prompts.SYSTEM_INSTRUCTIONS

    def propose_cadrage(
        self, mission_context: MissionContext, revision_notes: list[str] | None = None
    ) -> CadrageProposal:
        return self._run_structured(
            CadrageProposal, prompts.cadrage_prompt(mission_context, revision_notes), what="cadrage"
        )

    def assess_controls(
        self,
        mission_context: MissionContext,
        framework: str,
        controls: list[BaselineControl],
        revision_notes: list[str] | None = None,
    ) -> list[ControlAssessmentProposal]:
        if not controls:
            return []
        # One call per slice, as the ingestion already does with its questions. A whole
        # referential at once is both an output-budget problem (ISO 27001 is 93 controls,
        # each needing a verdict and a cited quote) and a recall one: the more controls
        # share a call, the more of them come back 'insufficient_information' against a
        # context that does hold the evidence.
        proposals: list[ControlAssessmentProposal] = []
        slices = [controls[i:i + CONTROLS_PER_CALL] for i in range(0, len(controls), CONTROLS_PER_CALL)]
        for i, chunk in enumerate(slices, 1):
            suffix = f" {i}/{len(slices)}" if len(slices) > 1 else ""
            batch = self._run_structured(
                ControlAssessmentBatch,
                prompts.controls_prompt(mission_context, framework, chunk, revision_notes),
                what=f"baseline assessment ({framework}){suffix}",
            )
            proposals.extend(batch.assessments)
        return proposals

    def assess_legal_impacts(
        self,
        mission_context: MissionContext,
        events: list[FearedEvent],
        provisions: list[BaselineControl],
        revision_notes: list[str] | None = None,
        assets: list[EssentialAsset] | None = None,
    ) -> list[LegalImpactAssignment]:
        if not events or not provisions:
            return []
        batch = self._run_structured(
            LegalImpactBatch,
            prompts.legal_impacts_prompt(mission_context, events, provisions, revision_notes, assets),
            what="legal-impact assessment",
        )
        return batch.impacts
