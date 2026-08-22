"""The LLM boundary for Workshop 1, behind a Protocol so orchestration is testable.

The agent only ever *proposes* (extracts assets/feared events, drafts per-control
verdicts, flags relevant legal provisions). Every acceptance, rejection, and
resolution is enforced downstream — deterministically in assessment.py or by the
auditor through the HumanInterface. Tests inject a fake runner; the real one
(agent.py) drives Agno + OpenRouter.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from ebios_rm.domain.essential_asset import EssentialAsset
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.reference_repository import BaselineControl
from ebios_rm.workshops.workshop1_cadrage.models import (
    CadrageProposal,
    ControlAssessmentProposal,
)


class ControlAssessmentBatch(BaseModel):
    """Structured-output wrapper: all per-control verdicts for one framework."""

    assessments: list[ControlAssessmentProposal] = Field(default_factory=list)


class LegalImpactAssignment(BaseModel):
    """The LLM's judgment that a legal provision is relevant to a feared event (conception §15.1).

    Both citations mandatory (double-citation discipline): the provision (by
    control_id) and the precise Mission Context fact that makes it relevant.
    """

    evenement_id: str
    provision_control_id: str
    evidence_mission_context: str


class LegalImpactBatch(BaseModel):
    impacts: list[LegalImpactAssignment] = Field(default_factory=list)


class Workshop1AgentRunner(Protocol):
    """Everything Workshop 1 asks the model to do (conception §15, §15.1)."""

    def propose_cadrage(
        self, mission_context: MissionContext, revision_notes: list[str] | None = None
    ) -> CadrageProposal:
        """Propose essential/support assets and feared events with gravity + impact category.

        revision_notes carries the auditor's rejection reasons from prior versions so
        the redo addresses them explicitly (conception §12.6, redo path)."""
        ...

    def assess_controls(
        self,
        mission_context: MissionContext,
        framework: str,
        controls: list[BaselineControl],
        revision_notes: list[str] | None = None,
    ) -> list[ControlAssessmentProposal]:
        """Draft an evidence-cited verdict for each baseline control of a framework."""
        ...

    def assess_legal_impacts(
        self,
        mission_context: MissionContext,
        events: list[FearedEvent],
        provisions: list[BaselineControl],
        revision_notes: list[str] | None = None,
        assets: list[EssentialAsset] | None = None,
    ) -> list[LegalImpactAssignment]:
        """Flag which declared legal provisions are relevant to which feared events."""
        ...
