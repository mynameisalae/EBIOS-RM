"""Orchestrator (conception section 10.2, section 17): atelier 1 -> 2 -> 3 handoffs.

Absolute rule: Workshop N -> Mission State -> Orchestrator -> Workshop N+1.
Never a direct call from one workshop to the next.

Both handoffs below share the same shape: check the previous workshop is really
approved (via is_approved, not the mission status string - see mission_state.py's
docstring on why), build the next workshop's narrow input, run it, and hand the
result to the shared ApprovalLoop from approval_cli.py.

Scope: the straightforward paths. Atelier 3's count gate supports run / run
anyway / cancel here; merge and choose-subset stay on scripts/run_workshop3.py
for now, and this code says so explicitly rather than guessing at them.
"""

from __future__ import annotations

from ebios_rm.orchestrator import mission_state
from ebios_rm.orchestrator.approval_cli import ApprovalLoop, ask_choice
from ebios_rm.plugins.registry import load_ebios_base
from ebios_rm.repositories.mission_repository import MissionRepository
from ebios_rm.workshops.workshop1_cadrage.human_interface import ask_justification
from ebios_rm.workshops.workshop2_sources_risque import (
    ALL_BLOCKS,
    BLOCK_COUPLES,
    BLOCK_OBJECTIFS,
    BLOCK_SOURCES,
    Atelier1DataError,
    Workshop2Output,
    build_workshop2_input,
    run_workshop2,
)
from ebios_rm.workshops.workshop2_sources_risque.agent import (
    AgnoWorkshop2Runner,
    Workshop2AgentError,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques import (
    Atelier2DataError,
    Workshop3Output,
    assemble_output,
    build_workshop3_input,
    gate_for,
    run_workshop3,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.agent import (
    AgnoWorkshop3Runner,
    Workshop3AgentError,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import (
    ACTION_CANCEL,
    ACTION_RUN,
    ACTION_RUN_ANYWAY,
)


class OrchestratorError(RuntimeError):
    """Raised when the mission cannot advance from its current status."""


# ============================================================================
# Atelier 1 -> Atelier 2
# ============================================================================

STAGE_W2 = "workshop_2"

_W2_BLOCK_LABELS = {
    "1": (BLOCK_SOURCES, "sources de risque"),
    "2": (BLOCK_OBJECTIFS, "objectifs vises"),
    "3": (BLOCK_COUPLES, "couples SR/OV"),
}


def _print_w2_output(output: Workshop2Output) -> None:
    print(f"\n=== Atelier 2 - {len(output.sources_risque)} source(s), "
          f"{len(output.objectifs_vises)} objectif(s), {len(output.couples)} couple(s) ===")
    for couple in output.couples:
        print(f"  [{couple.id}] {couple.source_risque_id} -> {couple.objectif_vise_id}")
    print(f"Controle qualite : {output.quality_report.statut}")


def _run_w2(repo, mission_id, w2_input, base, notes=None, blocks=None, previous=None):
    output = run_workshop2(w2_input, AgnoWorkshop2Runner(), base, notes, blocks, previous)
    mission_state.save_w2_output(repo, mission_id, output)
    repo.set_status(mission_id, "w2_awaiting_approval")
    return output


def advance_to_workshop2(repo: MissionRepository, mission_id: str) -> str:
    """Build atelier 2's input from an approved atelier 1, run it, save it, get a decision.

    Requires atelier 1's latest version to be approved. Returns "w2_approved" or
    "w2_rejected".
    """
    mission = repo.get_mission(mission_id)
    if mission is None:
        raise OrchestratorError(f"Mission introuvable : {mission_id}")
    if not mission_state.is_approved(repo, mission_id, mission_state.WORKSHOP_1):
        raise OrchestratorError(
            f"Impossible de demarrer l'atelier 2 : l'atelier 1 n'est pas approuve "
            f"(statut mission : {mission.status})."
        )

    mission_context = mission_state.load_mission_context(repo, mission_id)
    w1_output = mission_state.load_w1_output(repo, mission_id)
    if mission_context is None or w1_output is None:
        raise OrchestratorError("Mission Context ou atelier 1 introuvable en base.")

    w2_input = build_workshop2_input(mission_context, w1_output)
    base = load_ebios_base()

    repo.set_status(mission_id, "w2_running")
    try:
        output = _run_w2(repo, mission_id, w2_input, base)
    except Atelier1DataError as exc:
        repo.set_status(mission_id, "blocked")
        repo.log_decision(mission_id, stage=STAGE_W2, action="blocked", justification=str(exc))
        raise OrchestratorError(f"Atelier 1 comporte des anomalies bloquantes : {exc}") from exc
    except Workshop2AgentError as exc:
        raise OrchestratorError(f"Appel au modele en echec : {exc}") from exc

    exit_code = ApprovalLoop(
        repo=repo,
        mission_id=mission_id,
        stage=STAGE_W2,
        workshop_number=mission_state.WORKSHOP_2,
        label="l'atelier 2",
        print_output=_print_w2_output,
        rerun=lambda notes, blocks, previous: _run_w2(repo, mission_id, w2_input, base, notes, blocks, previous),
        save=lambda corrected: mission_state.save_w2_output(repo, mission_id, corrected),
        model_cls=Workshop2Output,
        edit_examples="couples.0.pertinence        sources_risque.1.justification",
        block_labels=_W2_BLOCK_LABELS,
    ).run(output)

    return "w2_approved" if exit_code == 0 else "w2_rejected"


# ============================================================================
# Atelier 2 -> Atelier 3
# ============================================================================

STAGE_W3 = "workshop_3"

_W3_GATE_LABELS = {
    ACTION_RUN: "valider cette liste et la transmettre a l'atelier 4",
    ACTION_RUN_ANYWAY: "lancer tout de meme, malgre le nombre",
    ACTION_CANCEL: "en rester la (liste conservee, non approuvee)",
}


def _print_w3_output(output: Workshop3Output) -> None:
    print(f"\n=== Atelier 3 - {len(output.scenarios)} scenario(s) strategique(s) ===")
    for scenario in output.scenarios:
        print(f"  [{scenario.id}] {scenario.resume}")
    gate = output.gate_decision
    print(f"\nPoint de comptage - N = {gate.n}, decision : {gate.action or 'en attente'}")
    print(f"Controle qualite : {output.quality_report.statut}")


def _run_w3(repo, mission_id, w3_input, notes=None, blocks=None, previous=None):
    output = run_workshop3(w3_input, AgnoWorkshop3Runner(), notes, previous)
    mission_state.save_w3_output(repo, mission_id, output)
    repo.set_status(mission_id, "w3_awaiting_approval")
    return output


def _handle_w3_gate(repo, mission_id, w3_input, output: Workshop3Output) -> Workshop3Output | None:
    """Run/run-anyway/cancel only (see module docstring). Returns None on cancel."""
    gate = gate_for(output.scenarios, n_initial=output.gate_decision.n_initial or len(output.scenarios))
    if not gate.options_offertes:
        return output

    unsupported = [a for a in gate.options_offertes if a not in _W3_GATE_LABELS]
    if unsupported:
        raise OrchestratorError(
            f"Le point de comptage propose {unsupported}, non gere par cette version de "
            f"l'orchestrateur. Utilisez python scripts/run_workshop3.py {mission_id} pour "
            "fusionner ou choisir un sous-ensemble."
        )

    keys = {str(i): action for i, action in enumerate(gate.options_offertes, 1)}
    choice = ask_choice("Que faire de cette liste ?", {k: _W3_GATE_LABELS[a] for k, a in keys.items()})
    action = keys[choice]

    if action == ACTION_CANCEL:
        repo.log_decision(mission_id, stage=STAGE_W3, action="gate_cancelled",
                           justification=f"{gate.n} scenario(s), liste non transmise")
        return None

    justification = (
        ask_justification("Motif pour lancer malgre le nombre (obligatoire) : ")
        if action == ACTION_RUN_ANYWAY else ""
    )
    decided = gate.model_copy(update={"action": action, "justification": justification})
    final = assemble_output(w3_input, output.scenarios, decided, output.elements_ecartes,
                             human_edits=output.human_edits)
    mission_state.save_w3_output(repo, mission_id, final)
    repo.set_status(mission_id, "w3_awaiting_approval")
    return final


def advance_to_workshop3(repo: MissionRepository, mission_id: str) -> str:
    """Build atelier 3's input from an approved atelier 2, run it, gate it, get a decision.

    Requires atelier 2's latest version to be approved. Returns "w3_approved",
    "w3_rejected", or "w3_cancelled".
    """
    mission = repo.get_mission(mission_id)
    if mission is None:
        raise OrchestratorError(f"Mission introuvable : {mission_id}")
    if not mission_state.is_approved(repo, mission_id, mission_state.WORKSHOP_2):
        raise OrchestratorError(
            f"Impossible de demarrer l'atelier 3 : l'atelier 2 n'est pas approuve "
            f"(statut mission : {mission.status})."
        )

    mission_context = mission_state.load_mission_context(repo, mission_id)
    w1_output = mission_state.load_w1_output(repo, mission_id)
    w2_output = mission_state.load_w2_output(repo, mission_id)
    if mission_context is None or w1_output is None or w2_output is None:
        raise OrchestratorError("Mission Context, atelier 1 ou atelier 2 introuvable en base.")

    w3_input = build_workshop3_input(mission_context, w1_output, w2_output)

    try:
        output = _run_w3(repo, mission_id, w3_input)
    except Atelier2DataError as exc:
        repo.set_status(mission_id, "blocked")
        repo.log_decision(mission_id, stage=STAGE_W3, action="blocked", justification=str(exc))
        raise OrchestratorError(f"Atelier 2 comporte des anomalies bloquantes : {exc}") from exc
    except Workshop3AgentError as exc:
        raise OrchestratorError(f"Appel au modele en echec : {exc}") from exc

    gated = _handle_w3_gate(repo, mission_id, w3_input, output)
    if gated is None:
        return "w3_cancelled"

    exit_code = ApprovalLoop(
        repo=repo,
        mission_id=mission_id,
        stage=STAGE_W3,
        workshop_number=mission_state.WORKSHOP_3,
        label="l'atelier 3",
        print_output=_print_w3_output,
        rerun=lambda notes, blocks, previous: _run_w3(repo, mission_id, w3_input, notes, blocks, previous),
        save=lambda corrected: mission_state.save_w3_output(repo, mission_id, corrected),
        model_cls=Workshop3Output,
        edit_examples="scenarios.0.resume",
    ).run(gated)

    return "w3_approved" if exit_code == 0 else "w3_rejected"