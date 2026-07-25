"""Typed input/output for Workshop 1 (conception §9, §14, §15).

Two families:
  * Proposal models — what the LLM returns (structured output).
  * Output models — the validated w1_output the orchestrator emits after applying
    the deterministic rules (enum checks, evidence discipline, RGPD filter,
    stable gap_id hashing).
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import CategorieImpact, Gravite, Origin
from ebios_rm.domain.essential_asset import EssentialAsset, SupportAsset
from ebios_rm.domain.feared_event import FearedEvent


# --- LLM proposal models (agent structured output) ---

class ControlAssessmentProposal(BaseModel):
    """The LLM's evidence-cited verdict on one baseline control (conception §15).

    Evaluation by evidence, never a bare verdict: a 'compliant' or 'gap' verdict
    must carry a non-empty evidence_quote drawn from the Mission Context. A verdict
    with no evidence is treated as 'insufficient_information' by the code (§15 step 2).
    """

    control_id: str
    verdict: str  # 'compliant' | 'gap' | 'insufficient_information'
    evidence_quote: str = ""  # a precise fact cited from the Mission Context
    weakness: str = ""        # the gap statement, when verdict == 'gap'
    confidence: str = "low"   # 'high' | 'medium' | 'low'


class CadrageProposal(BaseModel):
    """What the Workshop 1 agent proposes from the Mission Context (conception §15)."""

    biens_essentiels: list[EssentialAsset] = Field(default_factory=list)
    biens_supports: list[SupportAsset] = Field(default_factory=list)
    evenements_redoutes: list[FearedEvent] = Field(default_factory=list)


# --- Validated output models ---

class BaselineScopeDecision(BaseModel):
    """Explicit coverage decision — every category covered or explicitly excluded (conception §15 step 6)."""

    category: str
    decision: str  # 'covered' | 'excluded'
    justification: str  # non-empty (§8); mandatory when 'excluded'


class BaselineGap(BaseModel):
    """A baseline gap with full provenance — kept in baseline_gaps_full (conception §15, §20.3)."""

    gap_id: str
    framework: str
    control_id: str
    weakness: str
    risk_categories: list[str] = Field(default_factory=list)  # from covers_risk_category (§12.3)
    origin: Origin = Origin.ASSESSMENT
    evidence_quote: str = ""

    @staticmethod
    def make_gap_id(framework: str, control_id: str, weakness: str) -> str:
        """Stable id derived by hashing content, not a sequential counter (conception §15 step 5).

        Stable across reruns so the audit annex and workshop-4 handoff line up.
        """
        digest = hashlib.sha256(f"{framework}|{control_id}|{weakness}".encode("utf-8")).hexdigest()
        return f"BG-{digest[:8]}"


class BaselineGapForW4(BaseModel):
    """A gap stripped of its regulatory origin for Workshop 4 (conception §12.3, §15, §18).

    Workshop 4 never learns framework or control_id — only the raw weakness and
    its risk categories.
    """

    gap_id: str
    weakness: str
    risk_categories: list[str] = Field(default_factory=list)


class Workshop1Output(BaseModel):
    """w1_output (conception §15). baseline_scope_decisions is never empty."""

    biens_essentiels: list[EssentialAsset] = Field(default_factory=list)
    biens_supports: list[SupportAsset] = Field(default_factory=list)
    evenements_redoutes: list[FearedEvent] = Field(default_factory=list)
    baseline_scope_decisions: list[BaselineScopeDecision] = Field(default_factory=list)
    baseline_gaps_full: list[BaselineGap] = Field(default_factory=list)
    # Controls whose verdict was insufficient / unproven — stay 'unverified' until the
    # auditor answers, never silently reclassified (conception §15 step 2).
    unverified_controls: list[str] = Field(default_factory=list)
    # Corrections the auditor made directly on this output, each with its
    # justification and provenance (conception §2, §8) — read by the report agent.
    human_edits: list[dict] = Field(default_factory=list)

    def baseline_gaps_for_w4(self) -> list[BaselineGapForW4]:
        """Gaps handed to Workshop 4: framework/control_id stripped, and entries with an
        empty risk-category set (e.g. RGPD legal-only provisions) excluded (conception §12.3, §15 step 3)."""
        return [
            BaselineGapForW4(gap_id=g.gap_id, weakness=g.weakness, risk_categories=g.risk_categories)
            for g in self.baseline_gaps_full
            if g.risk_categories  # empty covers_risk_category -> never proposed to the W4 filter
        ]
