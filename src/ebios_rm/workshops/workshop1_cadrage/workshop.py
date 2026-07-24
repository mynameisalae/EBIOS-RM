"""Workshop 1 execution (conception §15) — the deterministic conductor.

Runs the agent to propose assets/feared events, assesses the security baseline
per declared framework (evidence enforced in assessment.py), attaches legal
impacts (§15.1), and emits the validated w1_output.

The Mission Context it consumes is built beforehand by intake_ingestion.

The agent only proposes; acceptance is code-enforced or auditor-driven (§2).
"""

from __future__ import annotations

from ebios_rm.domain.feared_event import FearedEvent, LegalImpactEntry
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.reference_repository import BaselineControl, ReferenceRepository
from ebios_rm.workshops.workshop1_cadrage.agent_runner import (
    LegalImpactAssignment,
    Workshop1AgentRunner,
)
from ebios_rm.workshops.workshop1_cadrage.assessment import assess_framework, scope_decisions
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap, Workshop1Output


# --- Phase 2: Mission Context -> w1_output ---

def _attach_legal_impacts(
    events: list[FearedEvent],
    assignments: list[LegalImpactAssignment],
    provisions: list[BaselineControl],
) -> list[FearedEvent]:
    """Attach evidence-backed legal impacts to feared events (conception §15.1).

    Both citations required: an assignment with an empty Mission Context evidence
    is dropped, never accepted as a bare legal verdict.
    """
    provisions_by_id = {p.control_id: p for p in provisions}
    events_by_id = {e.id: e for e in events}
    for a in assignments:
        if not a.evidence_mission_context or not a.evidence_mission_context.strip():
            continue
        provision = provisions_by_id.get(a.provision_control_id)
        event = events_by_id.get(a.evenement_id)
        if provision is None or event is None:
            continue
        event.legal_impacts.append(
            LegalImpactEntry(
                provision_citee=provision.legal_impact_details or provision.description,
                evidence_mission_context=a.evidence_mission_context.strip(),
                framework=provision.framework,
            )
        )
    return events


def run_workshop1(
    mission_context: MissionContext,
    runner: Workshop1AgentRunner,
    reference_repo: ReferenceRepository,
    revision_notes: list[str] | None = None,
) -> Workshop1Output:
    """Run Workshop 1 over a completed Mission Context and emit w1_output (conception §15).

    revision_notes, when given, are the auditor's rejection reasons from earlier
    versions, passed to the agent so the redo addresses them (conception §12.6)."""
    proposal = runner.propose_cadrage(mission_context, revision_notes)

    controls_by_framework: dict[str, list[BaselineControl]] = {
        fw: reference_repo.get_baseline_controls(fw) for fw in mission_context.applicable_frameworks
    }

    gaps_full: list[BaselineGap] = []
    unverified_controls: list[str] = []
    for framework, controls in controls_by_framework.items():
        if not controls:
            continue
        proposals = runner.assess_controls(mission_context, framework, controls)
        fa = assess_framework(framework, controls, proposals)
        gaps_full.extend(fa.gaps)
        unverified_controls.extend(fa.insufficient)

    # Legal-impact assessment — independent of baseline gaps (§15.1).
    provisions = reference_repo.get_legal_impact_provisions(mission_context.applicable_frameworks)
    assignments = runner.assess_legal_impacts(mission_context, proposal.evenements_redoutes, provisions)
    events = _attach_legal_impacts(proposal.evenements_redoutes, assignments, provisions)

    return Workshop1Output(
        biens_essentiels=proposal.biens_essentiels,
        biens_supports=proposal.biens_supports,
        evenements_redoutes=events,
        baseline_scope_decisions=scope_decisions(mission_context.applicable_frameworks, controls_by_framework),
        baseline_gaps_full=gaps_full,
        unverified_controls=unverified_controls,
    )
