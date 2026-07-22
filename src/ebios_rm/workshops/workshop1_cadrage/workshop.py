"""Workshop 1 orchestration (conception §11, §15) — the deterministic conductor.

Two phases:

1. complete_intake: build the Mission Context from the intake form + optional
   extracted document Facts, driving every human decision through the
   HumanInterface — follow-up questions for missing fields (priority matrix, §7),
   simple confirmation of document-only values, and mandatory human resolution of
   contradictions (§11). Nothing is assumed; nothing auto-resolved.

2. run_workshop1: run the agent to propose assets/feared events, assess the
   security baseline per declared framework (evidence enforced in assessment.py),
   attach legal impacts (§15.1), and emit the validated w1_output.

The agent only proposes; acceptance is code-enforced or auditor-driven (§2).
"""

from __future__ import annotations

from ebios_rm.domain.enums import Confidence, FactStatus, Origin
from ebios_rm.domain.fact import Fact
from ebios_rm.domain.feared_event import FearedEvent, LegalImpactEntry
from ebios_rm.mission_context.intake_form import OrgContextForm
from ebios_rm.mission_context.mission_context import MissionContext, assemble, intake_to_facts
from ebios_rm.mission_context.priority_matrix import follow_up_questions
from ebios_rm.mission_context.validation import validate
from ebios_rm.repositories.reference_repository import BaselineControl, ReferenceRepository
from ebios_rm.workshops.workshop1_cadrage.agent_runner import (
    LegalImpactAssignment,
    Workshop1AgentRunner,
)
from ebios_rm.workshops.workshop1_cadrage.assessment import assess_framework, scope_decisions
from ebios_rm.workshops.workshop1_cadrage.human_interface import HumanInterface, SkipRequested
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap, Workshop1Output


# --- Phase 1: intake -> Mission Context ---

def complete_intake(
    form: OrgContextForm,
    extraction_facts: list[Fact],
    human: HumanInterface,
) -> MissionContext:
    """Turn the form + optional extracted Facts into a validated Mission Context (conception §11)."""
    declaration_facts = intake_to_facts(form)

    # Follow-up questions for still-empty fields (Critical block, Important skippable, §7).
    for question in follow_up_questions(form):
        outcome = human.ask_followup(question)
        if isinstance(outcome, SkipRequested):
            declaration_facts.append(
                Fact(
                    field_name=question.field_name,
                    value=None,
                    origin=Origin.DECLARATION,
                    confidence=Confidence.LOW,
                    status=FactStatus.SKIPPED,
                    justification=outcome.reason,
                )
            )
        else:
            declaration_facts.append(Fact.declaration(question.field_name, outcome))

    # Three-case validation against any extracted document Facts (§11).
    result = validate(declaration_facts, extraction_facts)
    final_facts: list[Fact] = list(result.verified) + list(result.declaration_only)

    # Document-only values: propose for simple confirmation, no needless question (§11).
    for extr in result.document_only:
        if human.confirm_document_only(extr.field_name, extr.value, extr.source_quote or ""):
            final_facts.append(extr.model_copy(update={"status": FactStatus.APPROVED, "validated_by": "auditor"}))

    # Contradictions: mandatory human resolution, never automatic (§11).
    for contradiction in result.contradictions:
        resolved_value = human.resolve_contradiction(contradiction)
        final_facts.append(
            Fact(
                field_name=contradiction.field_name,
                value=resolved_value,
                origin=Origin.DECLARATION,
                confidence=Confidence.HIGH,
                status=FactStatus.APPROVED,
                validated_by="auditor",
                justification="Résolution de contradiction par l'auditeur (§11).",
            )
        )

    return assemble(form, final_facts)


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
) -> Workshop1Output:
    """Run Workshop 1 over a completed Mission Context and emit w1_output (conception §15)."""
    proposal = runner.propose_cadrage(mission_context)

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


def run(
    form: OrgContextForm,
    extraction_facts: list[Fact],
    runner: Workshop1AgentRunner,
    reference_repo: ReferenceRepository,
    human: HumanInterface,
) -> Workshop1Output:
    """Full Workshop 1: complete the intake, then run the workshop (conception §11, §15)."""
    mission_context = complete_intake(form, extraction_facts, human)
    return run_workshop1(mission_context, runner, reference_repo)
