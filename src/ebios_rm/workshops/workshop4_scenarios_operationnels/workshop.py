"""Workshop 4 execution (conception §18) — the deterministic conductor, fan-out / fan-in.

Builds the narrow input from the approved ateliers 1 to 3, dispatches one
independent sub-agent per strategic scenario, checks every answer as it returns,
runs the coherence call once the set is stable, and assembles w4_output.

The sub-agents only propose; every check and rating is in assessment.py. What is
not here, on purpose, is anything interactive — the batch review, the coherence
decision, the approval gate, pause and resume. The orchestrator drives those
(orchestrator/workshop4_flow.py), over the same functions, the way the shared
approval loop drives ateliers 2 and 3.

Deviation from §18, deliberate: the redo loop is not an Agno ``Loop`` and the
sub-agents do not call an ATT&CK Toolkit. Same reasons as ateliers 1 to 3 (no
reliable tool calling on the free models; human decisions testable without a
terminal) — the cap of three iterations and the ID check are enforced in code.
"""

from __future__ import annotations

import asyncio
from typing import Callable

from ebios_rm.domain.operational_scenario import STATUTS_EN_ATTENTE, OperationalScenario
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.attack_repository import AttackCatalogue
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Output
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import Workshop3Output
from ebios_rm.workshops.workshop4_scenarios_operationnels.agent_runner import Workshop4AgentRunner
from ebios_rm.workshops.workshop4_scenarios_operationnels.assessment import (
    build_analysis,
    build_coherence,
    finalize,
    run_quality_checks,
    validate_atelier3,
)
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import (
    COHERENCE_SANS_CONSTAT,
    CONTEXT_FIELDS,
    EXPERT_QUESTION_PREFIX,
    CoherenceReview,
    Workshop4Input,
    Workshop4Output,
)

# Sub-agents running at once. ponytail: a flat cap sized for free-tier rate limits;
# raise it for a paid model. Every result is saved as it returns, so a throttled
# call costs a retry, not the run.
MAX_PARALLEL_ANALYSES = 4


class Atelier3DataError(RuntimeError):
    """The approved atelier 3 output cannot be analysed (§2).

    Raised, never worked around: « erreur de donnée n'est pas erreur de
    raisonnement ». N sub-agents building on a scenario whose source de risque no
    longer exists would multiply the defect instead of surfacing it.
    """

    def __init__(self, alerts) -> None:
        super().__init__(
            "L'atelier 3 comporte des anomalies bloquantes :\n"
            + "\n".join(f"  - [{a.reference}] {a.probleme}" for a in alerts)
        )
        self.alerts = list(alerts)


# --- Mission Context + w1..w3 -> the narrow atelier 4 input -----------------

def build_workshop4_input(
    mission_context: MissionContext,
    w1_output: Workshop1Output,
    w2_output: Workshop2Output,
    w3_output: Workshop3Output,
) -> Workshop4Input:
    """Assemble the only input a sub-agent is allowed to see (§9, §18).

    This function is the input contract. The gaps are read through
    ``baseline_gaps_for_w4`` — framework and control id stripped, legal-only rows
    excluded (§12.3) — and nothing else of atelier 1's assessment is read: not the
    unverified controls, not the evidence quotes, not the human edits. Neither are
    the écartés, quality reports and superseded versions of any atelier.
    """
    facts = [
        f for f in mission_context.facts
        if f.field_name in CONTEXT_FIELDS or f.field_name.startswith(EXPERT_QUESTION_PREFIX)
    ]
    sources = {s.source_risque_id for s in w3_output.scenarios}
    objectifs = {s.objectif_vise_id for s in w3_output.scenarios}
    return Workshop4Input(
        organisation_nom=mission_context.organisation_nom,
        secteur_activite=mission_context.secteur_activite,
        contexte={f.field_name: f.value for f in facts if f.value not in (None, "")},
        faits_contexte=[f.model_copy(deep=True) for f in facts],
        scenarios=[s.model_copy(deep=True) for s in w3_output.scenarios],
        sources_risque=[s.model_copy(deep=True) for s in w2_output.sources_risque if s.id in sources],
        objectifs_vises=[o.model_copy(deep=True) for o in w2_output.objectifs_vises if o.id in objectifs],
        biens_essentiels=[a.model_copy(deep=True) for a in w1_output.biens_essentiels],
        biens_supports=[s.model_copy(deep=True) for s in w1_output.biens_supports],
        evenements_redoutes=[e.model_copy(deep=True) for e in w1_output.evenements_redoutes],
        baseline_gaps=w1_output.baseline_gaps_for_w4(),
        alertes_atelier3=validate_atelier3(w3_output, w2_output, w1_output),
    )


def initial_output(w4_input: Workshop4Input, attck_version: str) -> Workshop4Output:
    """One scenario to analyse per strategic scenario, in atelier 3's order (worst first)."""
    if w4_input.alertes_bloquantes:
        raise Atelier3DataError(w4_input.alertes_bloquantes)
    return Workshop4Output(
        scenarios=[
            OperationalScenario(
                id=f"SO-{n:02d}",
                scenario_strategique_id=s.id,
                source_risque_id=s.source_risque_id,
                objectif_vise_id=s.objectif_vise_id,
                biens_essentiels_ids=list(s.biens_essentiels_ids),
                evenements_redoutes_ids=list(s.evenements_redoutes_ids),
                gravite=s.gravite,
                vraisemblance_initiale=s.vraisemblance_initiale,
            )
            for n, s in enumerate(w4_input.scenarios, 1)
        ],
        alertes_atelier3=list(w4_input.alertes_atelier3),
        attck_version=attck_version,
    )


def pending_scenarios(output: Workshop4Output) -> list[OperationalScenario]:
    return [s for s in output.scenarios if s.statut in STATUTS_EN_ATTENTE]


# --- Fan-out / fan-in (§18 steps 22-24) --------------------------------------

def run_analyses(
    w4_input: Workshop4Input,
    output: Workshop4Output,
    runner: Workshop4AgentRunner,
    catalogue: AttackCatalogue,
    *,
    checkpoint: Callable[[Workshop4Output], None] | None = None,
    max_parallel: int = MAX_PARALLEL_ANALYSES,
) -> Workshop4Output:
    """Analyse every pending scenario, one independent sub-agent each (§18 step 22).

    Each answer is checked the moment it returns and handed to ``checkpoint``, so
    an interrupted run resumes with only the scenarios still pending. When some
    calls fail, the others are kept and the first failure is raised afterwards: a
    failed call is never turned into an analysis, and never costs the ones that
    succeeded.
    """
    return asyncio.run(_fan_out(w4_input, output, runner, catalogue, checkpoint, max_parallel))


async def _fan_out(w4_input, output, runner, catalogue, checkpoint, max_parallel) -> Workshop4Output:
    slots = asyncio.Semaphore(max_parallel)
    current = output

    async def analyse(pending: OperationalScenario) -> None:
        nonlocal current
        async with slots:
            proposal = await runner.analyse_scenario(w4_input, pending, catalogue)
        analysed, ecartes = build_analysis(proposal, pending, w4_input, catalogue)
        # No await between reading and writing ``current``: the event loop cannot
        # interleave two results here.
        current = current.model_copy(update={
            "scenarios": [analysed if s.id == analysed.id else s for s in current.scenarios],
            "elements_ecartes": [*current.elements_ecartes, *ecartes],
        })
        if checkpoint is not None:
            checkpoint(current)

    results = await asyncio.gather(
        *(analyse(s) for s in pending_scenarios(output)), return_exceptions=True)
    failures = [r for r in results if isinstance(r, BaseException)]
    if failures:
        raise failures[0]
    return current


# --- The coherence call (§18 step 28) ----------------------------------------

def run_coherence(
    w4_input: Workshop4Input, output: Workshop4Output, runner: Workshop4AgentRunner
) -> Workshop4Output:
    """One call over the stable, confirmed set. Nothing to decide when nothing is found.

    Under two scenarios there is nothing to compare, so no call is paid for.
    """
    if len(output.scenarios) < 2:
        return output.model_copy(update={"coherence": CoherenceReview(decision=COHERENCE_SANS_CONSTAT)})
    findings, ecartes = build_coherence(runner.check_coherence(w4_input, output.scenarios), output.scenarios)
    return output.model_copy(update={
        "coherence": CoherenceReview(constats=findings, decision="" if findings else COHERENCE_SANS_CONSTAT),
        "elements_ecartes": [*output.elements_ecartes, *ecartes],
    })


# --- Fan-in: w4_output as it will be judged (§18 step 29) --------------------

def assemble_output(
    w4_input: Workshop4Input, output: Workshop4Output, catalogue: AttackCatalogue
) -> Workshop4Output:
    """Re-derive phases, names and risk levels, then re-run the quality checker."""
    final = finalize(output, catalogue)
    return final.model_copy(update={"quality_report": run_quality_checks(w4_input, final, catalogue)})
