"""Workshop 3 execution (conception §17) — the deterministic conductor.

Validates the atelier 2 output, builds the working input, runs the two agent
passes (propose, then critique), and assembles w3_output with its count-gate
decision and quality report.

The agent only proposes; every acceptance, rejection, rating and count decision is
enforced in assessment.py, which has no LLM.

What is *not* here, on purpose: the approval loop, versioning, pause/resume and
the decision log — same seams as ateliers 1 and 2 (a runner Protocol,
``revision_notes``, ``previous``, and a pure function over typed input), with the
orchestrator supplying the machinery. The count gate itself is interactive by
nature, so this module computes the decision's *options* and leaves the choice to
the caller, then re-assembles through ``assemble_output``.
"""

from __future__ import annotations

from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.services.cost_estimation_service import estimate_cost_and_time
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Output
from ebios_rm.workshops.workshop3_scenarios_strategiques.agent_runner import Workshop3AgentRunner
from ebios_rm.workshops.workshop3_scenarios_strategiques.assessment import (
    apply_critique,
    build_scenarios,
    run_quality_checks,
    validate_atelier2,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import (
    CONTEXT_FIELDS,
    REASON_NON_TRAITE,
    ElementEcarte,
    GateDecision,
    Workshop3Input,
    Workshop3Output,
)


class Atelier2DataError(RuntimeError):
    """The atelier 2 output cannot be reasoned on (§17, white-box §4).

    Raised, never worked around: « erreur de donnée n'est pas erreur de
    raisonnement ». The auditor fixes atelier 2; atelier 3 must not build a
    scenario on a couple whose source de risque does not exist, because the defect
    would reach atelier 4 wearing an atelier 3 id.
    """

    def __init__(self, alerts) -> None:
        super().__init__(
            "L'atelier 2 comporte des anomalies bloquantes :\n"
            + "\n".join(f"  - [{a.reference}] {a.probleme}" for a in alerts)
        )
        self.alerts = list(alerts)


# --- Mission Context + w1_output + w2_output -> the narrow atelier 3 input ---

def build_workshop3_input(
    mission_context: MissionContext,
    w1_output: Workshop1Output,
    w2_output: Workshop2Output,
) -> Workshop3Input:
    """Assemble the only input atelier 3 is allowed to see (§17).

    This function is the input contract. It reads exactly ``CONTEXT_FIELDS`` from
    the Mission Context, the retained couples from atelier 2 with the sources and
    objectives they reference, and atelier 1's assets and feared events — which is
    also how the rest is kept out: the baseline gaps, the écartés, the quality
    reports, the human edits and every superseded version are never read, rather
    than read and then filtered.

    ``couples_secondaires`` stay out too: atelier 2 kept them in reserve rather
    than in the study, and turning them into scenarios here would put back the
    volume the count gate exists to control.
    """
    facts = [f for f in mission_context.facts if f.field_name in CONTEXT_FIELDS]
    referenced_sources = {c.source_risque_id for c in w2_output.couples}
    referenced_objectifs = {c.objectif_vise_id for c in w2_output.couples}
    return Workshop3Input(
        organisation_nom=mission_context.organisation_nom,
        secteur_activite=mission_context.secteur_activite,
        contexte={f.field_name: f.value for f in facts if f.value not in (None, "")},
        couples=[c.model_copy(deep=True) for c in w2_output.couples],
        sources_risque=[s.model_copy(deep=True) for s in w2_output.sources_risque
                        if s.id in referenced_sources],
        objectifs_vises=[o.model_copy(deep=True) for o in w2_output.objectifs_vises
                         if o.id in referenced_objectifs],
        biens_essentiels=[a.model_copy(deep=True) for a in w1_output.biens_essentiels],
        evenements_redoutes=[e.model_copy(deep=True) for e in w1_output.evenements_redoutes],
        faits_contexte=[f.model_copy(deep=True) for f in facts],
        alertes_atelier2=validate_atelier2(w2_output, w1_output),
    )


# --- Workshop3Input -> w3_output ---

def gate_for(scenarios: list[StrategicScenario], n_initial: int | None = None) -> GateDecision:
    """The count gate as it stands for this list (§17 steps 19-20).

    Fills in the count, the estimate atelier 4 would cost and the options the
    auditor may choose from. ``action`` is left blank: the count gate is a
    validation point, and even below the soft threshold §17 offers two answers —
    running is the likely one, not the automatic one. The caller fills it from
    ``options_offertes``.
    """
    estimate = estimate_cost_and_time(len(scenarios))
    return GateDecision(
        n=estimate.n,
        n_initial=estimate.n if n_initial is None else n_initial,
        action="",
        options_offertes=list(estimate.options),
        estimation_appels_llm=estimate.llm_calls,
        estimation_secondes=estimate.seconds,
    )


def assemble_output(
    w3_input: Workshop3Input,
    scenarios: list[StrategicScenario],
    gate: GateDecision,
    ecartes: list[ElementEcarte],
    *,
    human_edits: list[dict] | None = None,
) -> Workshop3Output:
    """Build w3_output and re-run the quality checker over it.

    Called again after every count-gate operation: a merge or a subset changes the
    list the checks are about, and a report describing the list as it was before is
    worse than none.
    """
    return Workshop3Output(
        scenarios=scenarios,
        gate_decision=gate,
        elements_ecartes=list(ecartes),
        quality_report=run_quality_checks(w3_input, scenarios, gate),
        alertes_atelier2=list(w3_input.alertes_atelier2),
        human_edits=list(human_edits or []),
    )


def run_workshop3(
    w3_input: Workshop3Input,
    runner: Workshop3AgentRunner,
    revision_notes: list[str] | None = None,
    previous: Workshop3Output | None = None,
) -> Workshop3Output:
    """Run atelier 3 over a validated input and emit w3_output (§17).

    ``revision_notes`` are the auditor's rejection reasons, passed to the propose
    pass so the redo addresses them.

    There is no partial redo here, unlike ateliers 1 and 2: atelier 3 produces one
    artifact, and regenerating "part of" a scenario list means regenerating it.
    """
    # Étape 0 — the atelier 2 output must hold up before anything is built on it.
    if w3_input.alertes_bloquantes:
        raise Atelier2DataError(w3_input.alertes_bloquantes)

    ecartes: list[ElementEcarte] = []

    # Passe 1 — propose, then keep only what the methodology allows.
    proposals = runner.propose_scenarios(w3_input, revision_notes)
    scenarios, discarded = build_scenarios(proposals, w3_input)
    ecartes.extend(discarded)

    # Passe 2 — the same agent criticises its own list.
    verdicts = runner.critique_scenarios(w3_input, scenarios)
    scenarios, pruned = apply_critique(scenarios, verdicts)
    ecartes.extend(pruned)

    # A couple the agent simply never wrote about leaves a trace too. The quality
    # checker warns about the gap, but a warning is a count; the auditor also needs
    # to see *which* couple went unanswered, in the same list as everything else
    # that did not make it (§19).
    covered = {s.couple_id for s in scenarios} | {e.reference for e in ecartes}
    ecartes.extend(
        ElementEcarte(
            reference=couple.id,
            libelle=f"{couple.source_risque_id} -> {couple.objectif_vise_id}",
            raison=REASON_NON_TRAITE,
        )
        for couple in w3_input.couples if couple.id not in covered
    )

    return assemble_output(
        w3_input, scenarios, gate_for(scenarios), ecartes,
        human_edits=list(previous.human_edits) if previous is not None else [],
    )
