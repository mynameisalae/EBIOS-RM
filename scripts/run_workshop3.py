"""Dev runner for Workshop 3 — scénarios stratégiques (conception §17).

    # run atelier 3 on a mission whose atelier 2 is approved
    python scripts/run_workshop3.py <mission_id>

Reads the Mission Context and the approved w1/w2 outputs from the mission DB, runs
the two agent passes, holds the count gate on N, saves the w3_output as a new
version, and asks the auditor to approve it.

The same command resumes: a mission whose atelier 3 ran but was never approved
picks up where it stopped — at the count gate if the count was never ruled on,
at the approval gate otherwise. No LLM call is paid for again up front.

Requires OPENROUTER_API_KEY (.env) and `pip install -r requirements.txt`. Run from
a real terminal so the interactive prompts work.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr, sys.stdin):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ebios_rm.agent_runtime import StructuredCallFailed, set_token_sink  # noqa: E402
from ebios_rm.config import load_settings  # noqa: E402
from ebios_rm.orchestrator import mission_state  # noqa: E402
from ebios_rm.orchestrator.approval_cli import (  # noqa: E402
    ApprovalLoop,
    ask_choice,
    ask_ids,
    prior_rejection_reasons,
)
from ebios_rm.repositories.mission_repository import MissionRepository, connect  # noqa: E402
from ebios_rm.workshops.workshop1_cadrage.human_interface import ask_justification  # noqa: E402
from ebios_rm.workshops.workshop3_scenarios_strategiques import (  # noqa: E402
    Atelier2DataError,
    Workshop3Output,
    assemble_output,
    build_workshop3_input,
    gate_for,
    run_workshop3,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.agent import (  # noqa: E402
    AgnoWorkshop3Runner,
    Workshop3AgentError,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.assessment import (  # noqa: E402
    choose_subset,
    merge_scenarios,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import (  # noqa: E402
    ACTION_CANCEL,
    ACTION_CHOOSE_SUBSET,
    ACTION_MERGE,
    ACTION_RUN,
    ACTION_RUN_ANYWAY,
)

STAGE = "workshop_3"

# What each gate action is called at the prompt (§17 step 20).
ACTION_LABELS = {
    ACTION_RUN: "valider cette liste et la transmettre à l'atelier 4",
    ACTION_RUN_ANYWAY: "lancer tout de même, malgré le nombre",
    ACTION_MERGE: "fusionner des scénarios qui se recouvrent",
    ACTION_CHOOSE_SUBSET: "choisir un sous-ensemble à traiter",
    ACTION_CANCEL: "en rester là (liste conservée, non approuvée)",
}


def _print_output(output: Workshop3Output) -> None:
    print(f"\n=== Atelier 3 — scénarios stratégiques ({len(output.scenarios)}) ===")
    for scenario in output.scenarios:
        print(f"  [{scenario.id}] {scenario.resume}")
        print(f"        couple {scenario.couple_id} : {scenario.source_risque_id} "
              f"-> {scenario.objectif_vise_id}")
        print(f"        parties prenantes : {', '.join(scenario.parties_prenantes) or 'aucune (accès direct)'}")
        print(f"        gravité {scenario.gravite.value}, "
              f"pertinence/vraisemblance {scenario.vraisemblance_pertinence}")
        print(f"        biens essentiels  : {', '.join(scenario.biens_essentiels_ids) or '—'}")
        if scenario.issu_de:
            print(f"        issu de           : {', '.join(scenario.issu_de)}")
        print(f"        {scenario.justification}")

    if output.elements_ecartes:
        print(f"\n=== Éléments écartés ({len(output.elements_ecartes)}) — avec leur raison ===")
        for element in output.elements_ecartes:
            print(f"  « {element.libelle or element.reference} » : {element.raison_label}")
            if element.detail:
                print(f"        {element.detail}")

    gate = output.gate_decision
    print(f"\n=== Point de comptage — N = {gate.n} "
          f"(initialement {gate.n_initial}), décision « {gate.action or 'en attente'} » ===")
    if gate.justification:
        print(f"        {gate.justification}")

    print(f"\n=== Contrôle qualité — statut : {output.quality_report.statut} ===")
    for check in output.quality_report.checks:
        marker = {"ok": "  ", "avertissement": "/!\\", "erreur": "XX "}.get(check.statut, "  ")
        print(f"  {marker} {check.controle} : {check.message}")


def _run_workshop(repo, mission_id, w3_input, revision_notes=None, blocks=None, previous=None):
    """Run the workshop and save its output. Not complete yet — no auditor decision recorded.

    ``blocks`` is accepted and ignored: atelier 3 produces one artifact, so there is
    nothing to regenerate partially. The parameter exists because the shared
    approval loop passes it (as None here, since no block labels are declared).
    """
    print("\n=== Atelier 3 ===")
    if revision_notes:
        print("Reprise en tenant compte des remarques de l'auditeur :")
        for note in revision_notes:
            print(f"   - {note}")
    output = run_workshop3(w3_input, AgnoWorkshop3Runner(), revision_notes, previous)
    mission_state.save_w3_output(repo, mission_id, output)
    # Deliberately NOT "approved": the auditor has not ruled on it yet (§2).
    repo.set_status(mission_id, "w3_awaiting_approval")
    return output


# --- The count gate (§17 steps 19-21) --------------------------------------

def _gate(repo, mission_id, w3_input, output: Workshop3Output) -> Workshop3Output | None:
    """Put N in front of the auditor, and apply what they decide. None means cancelled.

    Loops rather than recurses in code, but is the recursion §17 asks for: every
    merge and every subset re-evaluates the new N against the same thresholds, so
    reducing 14 scenarios to 13 offers exactly the options 13 deserves — not the
    ones offered before the reduction.
    """
    scenarios = list(output.scenarios)
    ecartes = list(output.elements_ecartes)
    n_initial = output.gate_decision.n_initial or len(scenarios)
    changed = False

    while True:
        gate = gate_for(scenarios, n_initial=n_initial)
        print(f"\n=== Point de comptage — {gate.n} scénario(s) stratégique(s) ===")
        print(f"L'atelier 4 traite un scénario par appel : environ {gate.estimation_appels_llm} "
              f"appel(s) au modèle, {gate.estimation_secondes / 60:.0f} minute(s).")
        if not gate.options_offertes:
            break

        keys = {str(i): action for i, action in enumerate(gate.options_offertes, 1)}
        choice = ask_choice(
            "Que faire de cette liste ?",
            {key: ACTION_LABELS[action] for key, action in keys.items()},
        )
        action = keys[choice]

        if action == ACTION_CANCEL:
            repo.log_decision(mission_id, stage=STAGE, action="gate_cancelled",
                              justification=f"{gate.n} scénario(s), liste non transmise")
            return None

        if action in {ACTION_RUN, ACTION_RUN_ANYWAY}:
            justification = (
                ask_justification("Motif pour lancer malgré le nombre (obligatoire, §8) : ")
                if action == ACTION_RUN_ANYWAY else ""
            )
            decided = gate.model_copy(update={"action": action, "justification": justification})
            repo.log_decision(mission_id, stage=STAGE, action=f"gate:{action}",
                              justification=justification or f"{gate.n} scénario(s) validés")
            final = assemble_output(w3_input, scenarios, decided, ecartes,
                                    human_edits=output.human_edits)
            if changed or output.gate_decision.action != action:
                mission_state.save_w3_output(repo, mission_id, final)
                repo.set_status(mission_id, "w3_awaiting_approval")
            return final

        known = {s.id for s in scenarios}
        if action == ACTION_MERGE:
            ids = ask_ids("Identifiants des scénarios à fusionner (le premier absorbe les autres) :", known)
            if len(ids) < 2:
                print("    Il en faut au moins deux.")
                continue
            justification = ask_justification("Motif de la fusion (obligatoire, §8) : ")
            scenarios, discarded = merge_scenarios(scenarios, ids, justification)
        else:
            ids = ask_ids("Identifiants des scénarios à CONSERVER :", known)
            if not ids:
                print("    Conserver zéro scénario laisserait l'atelier 4 sans objet.")
                continue
            justification = ask_justification("Motif du sous-ensemble (obligatoire, §8) : ")
            scenarios, discarded = choose_subset(scenarios, ids, justification)

        ecartes.extend(discarded)
        changed = True
        repo.log_decision(mission_id, stage=STAGE, action=f"gate:{action}",
                          justification=f"{justification} ({len(discarded)} scénario(s) retirés)")
        print(f"    {len(discarded)} scénario(s) retiré(s), avec leur raison.")

    return assemble_output(w3_input, scenarios, gate_for(scenarios, n_initial=n_initial),
                           ecartes, human_edits=output.human_edits)


def _loop(repo, mission_id, w3_input, output) -> int:
    """The auditor's review loop for atelier 3, on the shared implementation."""
    return ApprovalLoop(
        repo=repo,
        mission_id=mission_id,
        stage=STAGE,
        workshop_number=mission_state.WORKSHOP_3,
        label="l'atelier 3",
        print_output=_print_output,
        rerun=lambda notes, blocks, previous: _run_workshop(
            repo, mission_id, w3_input, notes, blocks, previous),
        save=lambda corrected: mission_state.save_w3_output(repo, mission_id, corrected),
        model_cls=Workshop3Output,
        edit_examples="scenarios.0.resume        scenarios.1.parties_prenantes.0",
    ).run(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run atelier 3 on a saved mission.")
    parser.add_argument("mission_id")
    args = parser.parse_args()

    settings = load_settings()
    print(f"Model: {settings.model_id}  (OpenRouter)")
    repo = MissionRepository(connect(settings.mission_db_path))

    mission = repo.get_mission(args.mission_id)
    if mission is None:
        print(f"Mission introuvable : {args.mission_id} (base : {settings.mission_db_path})")
        return 1

    mission_context = mission_state.load_mission_context(repo, args.mission_id)
    w1_output = mission_state.load_w1_output(repo, args.mission_id)
    w2_output = mission_state.load_w2_output(repo, args.mission_id)
    if mission_context is None or w1_output is None or w2_output is None:
        print("Mission incomplète : il faut un Mission Context et les résultats des ateliers 1 et 2.")
        return 1
    if not mission_state.is_approved(repo, args.mission_id, mission_state.WORKSHOP_2):
        # Atelier 3 builds on the couples atelier 2 retained. Built on a version the
        # auditor has not ruled on, every scenario would have to be redone the moment
        # that ruling changes a couple (§2).
        print(f"Statut de la mission : {mission.status} — l'atelier 2 n'est pas approuvé.")
        print(f"Approuvez-le d'abord : python scripts/run_workshop2.py {args.mission_id}")
        return 1

    print(f"Mission {mission.mission_id} — {mission.name}")
    w3_input = build_workshop3_input(mission_context, w1_output, w2_output)
    print(f"Entrée atelier 3 : {len(w3_input.contexte)} champs de contexte, "
          f"{len(w3_input.couples)} couples SR/OV retenus, "
          f"{len(w3_input.biens_essentiels)} biens essentiels.")

    for alert in w3_input.alertes_atelier2:
        tag = "BLOQUANT" if alert.bloquant else "avertissement"
        print(f"  [{tag}] {alert.reference} — {alert.probleme}")

    set_token_sink(lambda inp, out, model: repo.log_tokens(
        args.mission_id, input_tokens=inp, output_tokens=out, model_used=model))

    saved = mission_state.load_w3_output(repo, args.mission_id)
    if saved is not None and mission_state.is_approved(repo, args.mission_id, mission_state.WORKSHOP_3):
        print("Atelier 3 déjà approuvé. Résultat sauvegardé :")
        _print_output(saved)
        return 0

    if saved is not None:
        print(f"Atelier 3 exécuté mais non finalisé (statut : {mission.status}) — reprise.")
        output = saved
    else:
        notes = prior_rejection_reasons(repo, args.mission_id, STAGE)
        try:
            output = _run_workshop(repo, args.mission_id, w3_input, notes)
        except Atelier2DataError as exc:
            print(f"\n{exc}")
            print("Corrigez l'atelier 2 avant de relancer — l'atelier 3 ne répare rien de lui-même.")
            return 1

    # The count was never ruled on (fresh run, or a stop in the middle of the gate).
    if not output.gate_decision.action:
        decided = _gate(repo, args.mission_id, w3_input, output)
        if decided is None:
            print("Liste conservée, non transmise. Reprise : "
                  f"python scripts/run_workshop3.py {args.mission_id}")
            return 1
        output = decided

    return _loop(repo, args.mission_id, w3_input, output)


def _interrupted(mission_id: str) -> int:
    """Ctrl+C, or a model that cannot answer: everything saved so far is a version."""
    print("\n\nAtelier 3 mis en pause — la dernière version enregistrée est conservée.")
    print(f"  Pour reprendre :  python scripts/run_workshop3.py {mission_id}")
    return 130  # conventional exit code for SIGINT


if __name__ == "__main__":
    _mission = sys.argv[1] if len(sys.argv) > 1 else "<mission_id>"
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(_interrupted(_mission)) from None
    except (Workshop3AgentError, StructuredCallFailed) as exc:
        # A failed LLM call is never reinterpreted as a methodology outcome.
        print(f"\nAppel au modèle en échec : {exc}")
        raise SystemExit(_interrupted(_mission)) from None
