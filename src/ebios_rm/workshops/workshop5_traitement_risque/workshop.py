"""Workshop 5 execution (conception §19; méthode atelier 5) — the deterministic conductor.

Builds the narrow input from the approved ateliers 1 to 4, then runs the method's five
activities in order, each as a pure function over typed input:

  5-1  build the risks (gravité from atelier 1, vraisemblance from atelier 4), have the
       agent word them for a decision-maker, and check atelier 1's feared events are covered;
  5-2  the acceptability of each level, and the option the auditor decides (interactive,
       so the caller drives it);
  5-3  the measures, checked against the risks, the modes, the gaps and the ATT&CK
       mitigations the base returned;
  5-4  the residual likelihood, bounded by what the plan claims;
  5-5  the monitoring framework.

What is not here, on purpose: the auditor's decisions, the approval gate, pause and
resume. The orchestrator drives those (orchestrator/workshop5_flow.py).
"""

from __future__ import annotations

from ebios_rm.domain.risk_scenario import CadreSuivi, RiskScenario
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.attack_repository import AttackMitigation
from ebios_rm.workshops.common import AtelierDataError
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Output
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import Workshop3Output
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import Workshop4Output
from ebios_rm.workshops.workshop5_traitement_risque.agent_runner import Workshop5AgentRunner
from ebios_rm.workshops.workshop5_traitement_risque.assessment import (
    apply_formulations,
    apply_residuel,
    build_cadre,
    build_mesures,
    build_risques,
    couverture_er,
    keep_initial_residuel,
    link_mesures,
    rederive,
    run_quality_checks,
    validate_atelier4,
)
from ebios_rm.workshops.workshop5_traitement_risque.models import (
    ACTIVITE_FORMULATION,
    ACTIVITE_MESURES,
    CONTEXT_FIELDS,
    EXPERT_QUESTION_PREFIX,
    Workshop5Input,
    Workshop5Output,
)


# --- Mission Context + w1..w4 -> the narrow atelier 5 input ------------------

def build_workshop5_input(
    mission_context: MissionContext,
    w1_output: Workshop1Output,
    w2_output: Workshop2Output,
    w3_output: Workshop3Output,
    w4_output: Workshop4Output,
) -> Workshop5Input:
    """Assemble what atelier 5 is allowed to see (méthode atelier 5 « éléments en entrée »).

    The method's inputs, and the one difference from atelier 4: the baseline gaps arrive
    whole, framework and control id included, because the plan has to say which
    requirement each corrective measure satisfies.
    """
    facts = [
        f for f in mission_context.facts
        if f.field_name in CONTEXT_FIELDS or f.field_name.startswith(EXPERT_QUESTION_PREFIX)
    ]
    sources = {m.source_risque_id for m in w4_output.scenarios}
    objectifs = {m.objectif_vise_id for m in w4_output.scenarios}
    return Workshop5Input(
        organisation_nom=mission_context.organisation_nom,
        secteur_activite=mission_context.secteur_activite,
        contexte={f.field_name: f.value for f in facts if f.value not in (None, "")},
        faits_contexte=[f.model_copy(deep=True) for f in facts],
        modes_operatoires=[m.model_copy(deep=True) for m in w4_output.scenarios],
        scenarios_strategiques=[s.model_copy(deep=True) for s in w3_output.scenarios],
        sources_risque=[s.model_copy(deep=True) for s in w2_output.sources_risque if s.id in sources],
        objectifs_vises=[o.model_copy(deep=True) for o in w2_output.objectifs_vises if o.id in objectifs],
        biens_essentiels=[a.model_copy(deep=True) for a in w1_output.biens_essentiels],
        biens_supports=[s.model_copy(deep=True) for s in w1_output.biens_supports],
        evenements_redoutes=[e.model_copy(deep=True) for e in w1_output.evenements_redoutes],
        baseline_gaps=[g.model_copy(deep=True) for g in w1_output.baseline_gaps_full],
        alertes_atelier4=validate_atelier4(w4_output.scenarios, [s.id for s in w3_output.scenarios]),
    )


def _done(output: Workshop5Output, activite: str) -> Workshop5Output:
    """Mark an activity as paid for, so a resume does not buy the same answer twice."""
    if activite in output.activites_faites:
        return output
    return output.model_copy(update={"activites_faites": [*output.activites_faites, activite]})


def techniques_citees(w5_input: Workshop5Input) -> list[str]:
    """Every ATT&CK technique the retained and alternative modes cite — what mitigations are fetched for."""
    return list(dict.fromkeys(
        step.technique_id
        for mode in w5_input.modes_operatoires
        for step in mode.attack_path
        if step.technique_id
    ))


# --- Activité 5-1 -----------------------------------------------------------

def initial_output(w5_input: Workshop5Input, attck_version: str) -> Workshop5Output:
    """The risks, placed and graded, before anyone decides anything (atelier 5-1)."""
    if w5_input.alertes_bloquantes:
        raise AtelierDataError(4, w5_input.alertes_bloquantes)
    risques = build_risques(w5_input)
    return Workshop5Output(
        risques=risques,
        couverture_er=couverture_er(w5_input, risques),
        alertes_atelier4=list(w5_input.alertes_atelier4),
        attck_version=attck_version,
    )


def formulate(
    w5_input: Workshop5Input, output: Workshop5Output, runner: Workshop5AgentRunner,
    revision_notes: list[str] | None = None,
) -> Workshop5Output:
    """Ask the agent for the business wording of each risk, and keep only that (atelier 5-1)."""
    unwritten = [r for r in output.risques if not r.libelle.strip()]
    if not unwritten:
        return _done(output, ACTIVITE_FORMULATION)
    formulated = apply_formulations(
        output.risques, runner.formulate_risques(w5_input, unwritten, revision_notes))
    return _done(output.model_copy(update={"risques": formulated}), ACTIVITE_FORMULATION)


# --- Activité 5-3 -----------------------------------------------------------

def run_mesures(
    w5_input: Workshop5Input,
    output: Workshop5Output,
    runner: Workshop5AgentRunner,
    mitigations: dict[str, list[AttackMitigation]],
    risques: list[RiskScenario],
    revision_notes: list[str] | None = None,
) -> Workshop5Output:
    """One call for the whole plan, so a measure can serve several risks (atelier 5-3)."""
    proposals = runner.propose_mesures(w5_input, output, risques, mitigations, revision_notes)
    mesures, ecartes = build_mesures(proposals, output, w5_input, mitigations,
                                     start=len(output.mesures) + 1)
    return link_mesures(_done(output.model_copy(update={
        "mesures": [*output.mesures, *mesures],
        "elements_ecartes": [*output.elements_ecartes, *ecartes],
    }), ACTIVITE_MESURES))


# --- Activité 5-4 -----------------------------------------------------------

def run_residuel(
    w5_input: Workshop5Input,
    output: Workshop5Output,
    runner: Workshop5AgentRunner,
    risques: list[RiskScenario],
) -> Workshop5Output:
    """The residual evaluation, then the untreated risks kept at their initial level (atelier 5-4)."""
    evaluated, _ = apply_residuel(output, runner.evaluate_residuel(w5_input, output, risques))
    return keep_initial_residuel(evaluated)


# --- Activité 5-5 -----------------------------------------------------------

def run_cadre(
    w5_input: Workshop5Input,
    output: Workshop5Output,
    runner: Workshop5AgentRunner,
    *,
    comite: str = "",
    cycles: str = "",
    prochaine_revue: str = "",
    revision_notes: list[str] | None = None,
) -> Workshop5Output:
    """The monitoring framework: the agent proposes indicators, the organisation sets the cadence.

    The instance is set before the call, so the indicators are sized to how often it meets.
    """
    framed = output.model_copy(update={"cadre_suivi": CadreSuivi(
        comite=comite.strip(), cycles=cycles.strip(), prochaine_revue=prochaine_revue.strip())})
    cadre, ecartes = build_cadre(
        runner.propose_indicateurs(w5_input, framed, revision_notes), output,
        comite=comite, cycles=cycles, prochaine_revue=prochaine_revue)
    return output.model_copy(update={
        "cadre_suivi": cadre,
        "elements_ecartes": [*output.elements_ecartes, *ecartes],
    })


# --- Fan-in: w5_output as it will be judged ----------------------------------

def assemble_output(w5_input: Workshop5Input, output: Workshop5Output) -> Workshop5Output:
    """Re-derive what code owns — levels, acceptability, priorities, coverage, links — and re-check.

    Whatever produced the output — the séance, or a hand edit at the approval gate — the
    numbers the scale computes are recomputed here, so an edited input never leaves a
    stale level beside it.
    """
    linked = link_mesures(rederive(output.model_copy(update={
        "couverture_er": couverture_er(w5_input, output.risques),
    })))
    return linked.model_copy(update={"quality_report": run_quality_checks(w5_input, linked)})
