"""The LLM boundary for Workshop 2, behind a Protocol so orchestration is testable.

The agent only ever *proposes*: it contextualises the approved SR/OV base, drafts
candidates, and argues their pertinence. Every acceptance, rejection, score and
scale is enforced downstream in assessment.py, which has no LLM at all
(white-box §16). Tests inject a fake runner; the real one (agent.py) drives
Agno + OpenRouter through structured output only — free models do not reliably
support tool calling, so the base is queried in code and passed into the prompt.
"""

from __future__ import annotations

from typing import Protocol

from ebios_rm.domain.risk_source import ObjectifVise, RiskSource
from ebios_rm.plugins.registry import EbiosBase
from ebios_rm.workshops.workshop2_sources_risque.models import (
    CoupleProposal,
    ObjectifViseProposal,
    RiskSourceProposal,
    Workshop2Input,
)


class Workshop2AgentRunner(Protocol):
    """Everything Workshop 2 asks the model to do (white-box §6, §9, §11)."""

    def propose_sources(
        self,
        w2_input: Workshop2Input,
        base: EbiosBase,
        revision_notes: list[str] | None = None,
    ) -> list[RiskSourceProposal]:
        """Select, from the approved base, the risk-source categories plausible here.

        The model never invents a category (§6); it argues which of the base's
        categories fit this organisation's activity, perimeter and exposure, and
        cites the context fields it relied on.

        revision_notes carries the auditor's rejection reasons from prior versions
        so the redo addresses them explicitly.
        """
        ...

    def propose_objectifs(
        self,
        w2_input: Workshop2Input,
        base: EbiosBase,
        sources: list[RiskSource],
        revision_notes: list[str] | None = None,
    ) -> list[ObjectifViseProposal]:
        """Propose the objectives those sources could pursue (white-box §9).

        Reasoned from the business values, essential assets and security stakes —
        at the EBIOS RM level of an *end*, never an IT technique.
        """
        ...

    def propose_couples(
        self,
        w2_input: Workshop2Input,
        sources: list[RiskSource],
        objectifs: list[ObjectifVise],
        revision_notes: list[str] | None = None,
    ) -> list[CoupleProposal]:
        """Associate the compatible SR and OV, and rate each couple (white-box §11, §13).

        A subset, never the cartesian product. Each couple carries a justification
        and three 1..4 ratings (motivation, ressources, activité); the pertinence
        and the initial likelihood are computed from them in code.
        """
        ...
