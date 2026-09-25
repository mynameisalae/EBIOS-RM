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
import concurrent.futures
from typing import Callable

from ebios_rm.domain.operational_scenario import STATUTS_EN_ATTENTE, OperationalScenario
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.attack_repository import AttackCatalogue
from ebios_rm.workshops.common import AtelierDataError
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Output
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import Workshop3Output
from ebios_rm.workshops.workshop4_scenarios_operationnels.agent_runner import Workshop4AgentRunner
from ebios_rm.workshops.workshop4_scenarios_operationnels.assessment import (
    MAX_MODES_PER_SCENARIO,
    build_analysis,
    build_coherence,
    build_modes,
    driving_modes,
    finalize,
    number_modes,
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
    """An empty atelier 4: the modes opératoires come from the enumeration (§18).

    Deviation from §18, decided by the project owner: the conception assumes one
    operational scenario per strategic scenario. The method does not fix a count —
    a strategic scenario allows as many modes opératoires as the dossier has ways
    in, they are all developed, and the most likely one drives the risk. So the
    rows are not known here; ``run_enumeration`` creates them.

    Raised, never worked around: sub-agents building on a scenario whose source de
    risque no longer exists would multiply the defect instead of surfacing it.
    """
    if w4_input.alertes_bloquantes:
        raise AtelierDataError(3, w4_input.alertes_bloquantes)
    return Workshop4Output(
        alertes_atelier3=list(w4_input.alertes_atelier3),
        attck_version=attck_version,
    )


def pending_scenarios(output: Workshop4Output) -> list[OperationalScenario]:
    return [s for s in output.scenarios if s.statut in STATUTS_EN_ATTENTE]


def scenarios_without_modes(w4_input: Workshop4Input, output: Workshop4Output) -> list:
    """Strategic scenarios whose modes opératoires have not been enumerated yet.

    Read from the output itself, so a resumed mission enumerates only what is
    missing — and an enumeration that failed for one scenario does not cost the
    others their result.
    """
    known = {s.scenario_strategique_id for s in output.scenarios}
    known |= {e.reference for e in output.elements_ecartes if e.type == "mode_operatoire"}
    return [s for s in w4_input.scenarios if s.id not in known]


# --- Étape 22a: enumerate the modes opératoires (§18, before the fan-out) ----

def run_enumeration(
    w4_input: Workshop4Input,
    output: Workshop4Output,
    runner: Workshop4AgentRunner,
    *,
    checkpoint: Callable[[Workshop4Output], None] | None = None,
    max_parallel: int = MAX_PARALLEL_ANALYSES,
) -> Workshop4Output:
    """Ask, for each strategic scenario, which modes opératoires the dossier allows.

    One cheap call per strategic scenario, no ATT&CK catalogue and no attack path —
    the count comes from the material, not from a constant handed to the model. What
    survives the checks becomes a mode to develop; the rest is écarté with its reason.
    """
    return _run(_enumerate(w4_input, output, runner, checkpoint, max_parallel))


async def _enumerate(w4_input, output, runner, checkpoint, max_parallel) -> Workshop4Output:
    slots = asyncio.Semaphore(max_parallel)
    missing = scenarios_without_modes(w4_input, output)

    async def enumerate_one(scenario):
        async with slots:
            return scenario, await runner.enumerate_modes(w4_input, scenario)

    results = await asyncio.gather(*(enumerate_one(s) for s in missing), return_exceptions=True)
    modes, ecartes = list(output.scenarios), list(output.elements_ecartes)
    for result in results:
        if isinstance(result, BaseException):
            continue
        scenario, candidates = result
        kept, discarded = build_modes(scenario, candidates, w4_input)
        modes.extend(number_modes(kept, start=len(modes) + 1))
        ecartes.extend(discarded)
    current = output.model_copy(update={"scenarios": modes, "elements_ecartes": ecartes})
    if checkpoint is not None and current.scenarios != output.scenarios:
        checkpoint(current)

    failures = [r for r in results if isinstance(r, BaseException)]
    if failures:
        # What was enumerated is already saved: a resume asks only about the
        # scenarios still without modes.
        raise failures[0]
    return current


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

    Opens its own event loop, correct when called from the standalone script's
    synchronous main(). A caller that already runs one (an async Orchestrator,
    say) cannot have this one nest inside it — asyncio.run() refuses that — so
    when one is already running, this one runs instead on a worker thread,
    where it is free to open its own.
    """
    return _run(_fan_out(w4_input, output, runner, catalogue, checkpoint, max_parallel))


def _run(coro) -> Workshop4Output:
    """Await ``coro`` from synchronous code, whether or not a loop is already running.

    Opening a loop is correct when called from the standalone script's synchronous
    main(). A caller that already runs one (the async Orchestrator) cannot have this
    one nest inside it — asyncio.run() refuses that — so the work goes to a worker
    thread, which is free to open its own.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)  # no loop running: the standalone script's case
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


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
    """One call over the driving modes, once the set is stable (§18 step 28).

    Only the retained mode of each strategic scenario: the alternative modes of one
    scenario deliberately share its objective, so comparing them would report a
    duplicate for every scenario. Under two scenarios there is nothing to compare,
    so no call is paid for.
    """
    retained = driving_modes(output)
    if len(retained) < 2:
        return output.model_copy(update={"coherence": CoherenceReview(decision=COHERENCE_SANS_CONSTAT)})
    findings, ecartes = build_coherence(runner.check_coherence(w4_input, retained), retained)
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
