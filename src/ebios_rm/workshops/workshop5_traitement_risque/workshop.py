"""Workshop 5 execution (conception §19) — one call, one agent, no fan-out.

Builds the narrow input from the approved Mission Context, atelier 1 and the
finalized atelier 4, builds the MitigationCatalogue for exactly the techniques
those scenarios cite, calls the single agent (real tool calls happen inside
that one call), and checks every proposed measure against it.

What is not here, on purpose: anything interactive — the review, the approval
gate. The orchestrator drives those, the way the shared approval loop drives
every other atelier.
"""

from __future__ import annotations

from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.attack_repository import AttackRepository, MitigationCatalogue
from ebios_rm.workshops.common import AtelierDataError
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import Workshop4Output
from ebios_rm.workshops.workshop5_traitement_risque.agent_runner import Workshop5AgentRunner
from ebios_rm.workshops.workshop5_traitement_risque.assessment import (
    build_mesure,
    run_quality_checks,
    validate_atelier4,
)
from ebios_rm.workshops.workshop5_traitement_risque.models import Workshop5Input, Workshop5Output


def build_workshop5_input(
    mission_context: MissionContext, w1_output: Workshop1Output, w4_output: Workshop4Output
) -> Workshop5Input:
    """Assemble the only input the atelier 5 agent is allowed to see (§9, §19).

    ``baseline_gaps`` keeps the *full* BaselineGap (framework, control_id) —
    the opposite of atelier 4's stripped baseline_gaps_for_w4() — because
    atelier 5 must name a gap's regulatory origin to treat RGPD Article 32
    specifically (conception §19). The filter is the same one atelier 1
    already applies before handing gaps to atelier 4 (kept only where
    risk_categories is non-empty): RGPD-Art32 already carries real risk
    categories in the reference data (credential_access, exfiltration,
    data_destruction, impact), so it passes through on the same condition
    that excludes purely-administrative rows — no RGPD-specific filtering
    code is needed here, the source data already encodes the distinction.
    """
    return Workshop5Input(
        organisation_nom=mission_context.organisation_nom,
        secteur_activite=mission_context.secteur_activite,
        scenarios=[s.model_copy(deep=True) for s in w4_output.scenarios],
        baseline_gaps=[g.model_copy(deep=True) for g in w1_output.baseline_gaps_full if g.risk_categories],
    )


def cited_technique_ids(w5_input: Workshop5Input) -> set[str]:
    """Every technique id atelier 4 actually cited — the catalogue's scope (§19)."""
    return {
        step.technique_id
        for scenario in w5_input.scenarios
        for step in scenario.attack_path
        if step.technique_id
    }


def run_workshop5(
    w5_input: Workshop5Input,
    runner: Workshop5AgentRunner,
    attack_repo: AttackRepository,
    w4_output: Workshop4Output,
    w1_output: Workshop1Output,
) -> Workshop5Output:
    """Run atelier 5 over a validated input and emit w5_output (§19).

    Étape 0 (§2): the finalized atelier 4 output must hold up before anything
    is built on it — a scenario citing a gap atelier 5 was never given would
    reach the agent as if it had been, producing a measure grounded in
    nothing the auditor can verify.
    """
    alerts = validate_atelier4(w4_output.scenarios, w1_output.baseline_gaps_full)
    blocking = [a for a in alerts if a.bloquant]
    if blocking:
        raise AtelierDataError(4, blocking)

    mitigations = attack_repo.mitigation_catalogue(cited_technique_ids(w5_input))
    batch = runner.propose_mesures(w5_input, mitigations)

    mesures = []
    elements_ecartes = []
    for n, proposal in enumerate(batch.mesures, 1):
        mesure, ecartes = build_mesure(n, proposal, w5_input, mitigations)
        elements_ecartes.extend(ecartes)
        if mesure is not None:
            mesures.append(mesure)

    return Workshop5Output(
        mesures=mesures,
        elements_ecartes=elements_ecartes,
        quality_report=run_quality_checks(w5_input, mesures, mitigations),
    )
