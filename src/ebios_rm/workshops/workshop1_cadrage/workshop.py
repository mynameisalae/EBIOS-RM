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

# The three independently-generated blocks of w1_output. A rejection can target
# any subset; the rest is reused verbatim (partial redo, conception §12.6).
BLOCK_CADRAGE = "cadrage"      # biens essentiels/supports + événements redoutés
BLOCK_BASELINE = "baseline"    # écarts du socle par référentiel
BLOCK_LEGAL = "legal"          # impacts juridiques attachés aux événements (§15.1)
ALL_BLOCKS = {BLOCK_CADRAGE, BLOCK_BASELINE, BLOCK_LEGAL}


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
    blocks: set[str] | None = None,
    previous: Workshop1Output | None = None,
) -> Workshop1Output:
    """Run Workshop 1 over a completed Mission Context and emit w1_output (conception §15).

    revision_notes are the auditor's rejection reasons, passed to the regenerated
    blocks so the redo addresses them (conception §12.6).

    ``blocks`` selects what to regenerate (default: everything). On a partial redo
    the untouched blocks are copied verbatim from ``previous`` — rejecting a wrong
    gravité must not silently reshuffle assets the auditor was happy with, and it
    avoids paying for LLM calls that were not asked for.
    """
    todo = blocks or ALL_BLOCKS
    if todo != ALL_BLOCKS and previous is None:
        raise ValueError("A partial redo needs the previous output to reuse the untouched blocks.")

    # --- cadrage: assets + feared events ---
    if BLOCK_CADRAGE in todo:
        proposal = runner.propose_cadrage(mission_context, revision_notes)
        biens_essentiels = proposal.biens_essentiels
        biens_supports = proposal.biens_supports
        events = proposal.evenements_redoutes
    else:
        biens_essentiels = previous.biens_essentiels
        biens_supports = previous.biens_supports
        events = [e.model_copy(deep=True) for e in previous.evenements_redoutes]

    controls_by_framework: dict[str, list[BaselineControl]] = {
        fw: reference_repo.get_baseline_controls(fw) for fw in mission_context.applicable_frameworks
    }

    # --- baseline: gaps per declared framework ---
    if BLOCK_BASELINE in todo:
        gaps_full: list[BaselineGap] = []
        unverified_controls: list[str] = []
        for framework, controls in controls_by_framework.items():
            if not controls:
                continue
            proposals = runner.assess_controls(mission_context, framework, controls, revision_notes)
            fa = assess_framework(framework, controls, proposals)
            gaps_full.extend(fa.gaps)
            unverified_controls.extend(fa.insufficient)
    else:
        gaps_full = list(previous.baseline_gaps_full)
        unverified_controls = list(previous.unverified_controls)

    # --- legal impact: independent of baseline gaps (§15.1) ---
    if BLOCK_LEGAL in todo:
        for event in events:
            event.legal_impacts = []  # regenerating: drop the previous attachments first
        provisions = reference_repo.get_legal_impact_provisions(mission_context.applicable_frameworks)
        assignments = runner.assess_legal_impacts(mission_context, events, provisions, revision_notes)
        events = _attach_legal_impacts(events, assignments, provisions)

    return Workshop1Output(
        biens_essentiels=biens_essentiels,
        biens_supports=biens_supports,
        evenements_redoutes=events,
        baseline_scope_decisions=scope_decisions(mission_context.applicable_frameworks, controls_by_framework),
        baseline_gaps_full=gaps_full,
        unverified_controls=unverified_controls,
        human_edits=list(previous.human_edits) if previous is not None else [],
    )
