"""Deterministic baseline-assessment methodology for Workshop 1 (conception §15).

Pure functions, no LLM and no I/O — this is where the evidence discipline, the
RGPD security/legal split, the stable gap-id hashing, and the scope-decision
completeness rule are enforced in code, so an LLM can never talk its way past them.
"""

from __future__ import annotations

from dataclasses import dataclass

from ebios_rm.repositories.reference_repository import BaselineControl
from ebios_rm.workshops.workshop1_cadrage.models import (
    REASON_INVALID_VERDICT,
    REASON_NO_EVIDENCE_CITED,
    REASON_NO_INFORMATION,
    REASON_UNKNOWN_CONTROL,
    BaselineGap,
    BaselineScopeDecision,
    ControlAssessmentProposal,
    ControlReference,
    UnverifiedControl,
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
    # Controls that could not be concluded on, each carrying why (conception §15 step 2).
    insufficient: list[UnverifiedControl]


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
    insufficient: list[UnverifiedControl] = []

    def unverified(proposal, reason: str, control=None) -> None:
        insufficient.append(UnverifiedControl(
            control_id=proposal.control_id,
            framework=framework,
            description=control.description if control else "",
            reason=reason,
            model_said=proposal.verdict.strip(),
        ))

    for proposal in proposals:
        control = controls_by_id.get(proposal.control_id)
        if control is None:
            # A verdict citing a control the tools never returned — never invented into a gap.
            unverified(proposal, REASON_UNKNOWN_CONTROL)
            continue

        verdict = proposal.verdict.strip().lower()
        if verdict == _INSUFFICIENT_VERDICT:
            unverified(proposal, REASON_NO_INFORMATION, control)
            continue
        if not has_evidence(proposal):
            # Claimed a verdict but cited nothing: a prompt problem, not missing info.
            unverified(proposal, REASON_NO_EVIDENCE_CITED, control)
            continue
        if verdict == _COMPLIANT_VERDICT:
            continue  # nothing to record — compliant with evidence
        if verdict == _GAP_VERDICT:
            weakness = proposal.weakness.strip() or control.description
            gaps.append(
                BaselineGap(
                    gap_id=BaselineGap.make_gap_id(framework, control.control_id, weakness),
                    controls=[ControlReference(framework=framework, control_id=control.control_id)],
                    weakness=weakness,
                    risk_categories=list(control.covers_risk_category),  # empty for legal-only rows (§12.3)
                    evidence_quote=proposal.evidence_quote.strip(),
                )
            )
        else:
            unverified(proposal, REASON_INVALID_VERDICT, control)  # never assumed

    return FrameworkAssessment(gaps=gaps, insufficient=insufficient)


def frameworks_without_controls(
    declared_frameworks: list[str], reference_repo
) -> list[str]:
    """Declared frameworks that have no baseline control loaded (conception §2, §12.5).

    Such a framework cannot be assessed at all: the AI must never invent referential
    text nor assume coverage. The caller stops the workshop until a human either
    loads the controls or explicitly withdraws the framework — silent continuation
    would produce a report claiming coverage that was never evaluated.
    """
    return [fw for fw in declared_frameworks if not reference_repo.get_baseline_controls(fw)]


def scope_decisions(
    declared_frameworks: list[str],
    controls_by_framework: dict[str, list[BaselineControl]],
) -> list[BaselineScopeDecision]:
    """Every declared framework is explicitly covered or excluded — never omitted (conception §15 step 6).

    Guarantees a non-empty list (fiche de test §15). A framework reaching here with
    no controls was explicitly withdrawn by the auditor (the workshop refuses to run
    otherwise, see frameworks_without_controls), so it is recorded as excluded.
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
                        "Aucun contrôle chargé pour ce référentiel — exclusion validée par "
                        "l'auditeur (conception §12.5)."
                    ),
                )
            )
    return decisions
