"""Deterministic baseline-assessment methodology for Workshop 1 (conception §15).

Pure functions, no LLM and no I/O — this is where the evidence discipline, the
RGPD security/legal split, the stable gap-id hashing, and the scope-decision
completeness rule are enforced in code, so an LLM can never talk its way past them.
"""

from __future__ import annotations

from dataclasses import dataclass

from ebios_rm.repositories.reference_repository import BaselineControl
from ebios_rm.workshops.workshop1_cadrage.models import (
    BaselineGap,
    BaselineScopeDecision,
    ControlAssessmentProposal,
)

_GAP_VERDICT = "gap"
_COMPLIANT_VERDICT = "compliant"
_INSUFFICIENT_VERDICT = "insufficient_information"


def has_evidence(proposal: ControlAssessmentProposal) -> bool:
    """A compliant/gap verdict is only accepted with a non-empty cited evidence quote (conception §15)."""
    return bool(proposal.evidence_quote and proposal.evidence_quote.strip())


@dataclass
class FrameworkAssessment:
    """The result of assessing one framework's controls against the Mission Context."""

    gaps: list[BaselineGap]
    # control_ids whose verdict is insufficient, or a gap/compliant claimed without evidence:
    # these become follow-up questions and stay 'unverified' until answered (conception §15 step 2).
    insufficient: list[str]


def assess_framework(
    framework: str,
    controls: list[BaselineControl],
    proposals: list[ControlAssessmentProposal],
) -> FrameworkAssessment:
    """Turn the LLM's per-control verdicts into validated gaps, enforcing evidence (conception §15).

    A 'gap' or 'compliant' verdict with no evidence is downgraded to insufficient —
    never silently accepted. Only evidence-backed gaps produce a BaselineGap.
    """
    controls_by_id = {c.control_id: c for c in controls}
    gaps: list[BaselineGap] = []
    insufficient: list[str] = []

    for proposal in proposals:
        control = controls_by_id.get(proposal.control_id)
        if control is None:
            # A verdict citing a control the tools never returned — never invented into a gap.
            insufficient.append(proposal.control_id)
            continue

        verdict = proposal.verdict.strip().lower()
        if verdict == _INSUFFICIENT_VERDICT or not has_evidence(proposal):
            insufficient.append(proposal.control_id)
            continue
        if verdict == _COMPLIANT_VERDICT:
            continue  # nothing to record — compliant with evidence
        if verdict == _GAP_VERDICT:
            weakness = proposal.weakness.strip() or control.description
            gaps.append(
                BaselineGap(
                    gap_id=BaselineGap.make_gap_id(framework, control.control_id, weakness),
                    framework=framework,
                    control_id=control.control_id,
                    weakness=weakness,
                    risk_categories=list(control.covers_risk_category),  # empty for legal-only rows (§12.3)
                    evidence_quote=proposal.evidence_quote.strip(),
                )
            )
        else:
            insufficient.append(proposal.control_id)  # unrecognized verdict — never assumed

    return FrameworkAssessment(gaps=gaps, insufficient=insufficient)


def scope_decisions(
    declared_frameworks: list[str],
    controls_by_framework: dict[str, list[BaselineControl]],
) -> list[BaselineScopeDecision]:
    """Every declared framework is explicitly covered or excluded — never omitted (conception §15 step 6).

    Guarantees a non-empty list (fiche de test §15): a framework with no controls
    loaded is explicitly excluded with a justification rather than silently dropped.
    """
    decisions: list[BaselineScopeDecision] = []
    for framework in declared_frameworks:
        controls = controls_by_framework.get(framework, [])
        if controls:
            decisions.append(
                BaselineScopeDecision(
                    category=framework,
                    decision="covered",
                    justification=f"Référentiel déclaré et évalué ({len(controls)} contrôles).",
                )
            )
        else:
            decisions.append(
                BaselineScopeDecision(
                    category=framework,
                    decision="excluded",
                    justification=(
                        "Aucun contrôle chargé pour ce référentiel — à compléter via le plugin "
                        "correspondant avant exploitation (conception §12.5)."
                    ),
                )
            )
    return decisions
