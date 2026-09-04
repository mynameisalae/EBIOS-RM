"""Dev runner for Workshop 2 — sources de risque et objectifs visés (white-box atelier 2).

    # run atelier 2 on a mission whose atelier 1 is approved
    python scripts/run_workshop2.py <mission_id>

    # skip the client session (use the context as-is)
    python scripts/run_workshop2.py <mission_id> --no-session

Reads the Mission Context and the approved w1_output from the mission DB, runs the
session questions, runs the workshop, saves the w2_output as a new version, and
asks the auditor to approve it.

The same command resumes: a mission left at w2_awaiting_approval or w2_rejected
picks up at the approval gate on the saved output — no LLM call is paid for again
up front, and the redo (which parts, with the auditor's reasons) is asked there.

Requires OPENROUTER_API_KEY (.env) and `pip install -r requirements.txt`. Run from
a real terminal so the interactive prompts work. The reference DB is not needed:
atelier 2 reads the approved SR/OV base from the plugins, not from SQLite.
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
from ebios_rm.plugins.registry import load_ebios_base  # noqa: E402
from ebios_rm.repositories.mission_repository import MissionRepository, connect  # noqa: E402
from ebios_rm.orchestrator.approval_cli import (  # noqa: E402
    ApprovalLoop,
    interrupted,
    prior_rejection_reasons,
)
from ebios_rm.workshops.workshop1_cadrage.human_interface import CLIHumanInterface  # noqa: E402
from ebios_rm.workshops.workshop2_sources_risque import (  # noqa: E402
    BLOCK_COUPLES,
    BLOCK_OBJECTIFS,
    BLOCK_SOURCES,
    Atelier1DataError,
    Workshop2Output,
    ask_session_questions,
    build_workshop2_input,
    run_workshop2,
)
from ebios_rm.workshops.workshop2_sources_risque.agent import (  # noqa: E402
    AgnoWorkshop2Runner,
    Workshop2AgentError,
)

STAGE = "workshop_2"


def _print_output(output) -> None:
    print("\n=== Atelier 2 — sources de risque ===")
    for source in output.sources_risque:
        print(f"  [{source.id}] {source.nom}  ({source.categorie_libelle}, {source.statut.value})")
        print(f"        {source.justification}")

    print("\n=== Objectifs visés ===")
    for objectif in output.objectifs_vises:
        print(f"  [{objectif.id}] {objectif.description}  ({objectif.finalite_libelle})")

    print("\n=== Couples SR/OV retenus ===")
    for couple in output.couples:
        print(
            f"  [{couple.id}] {couple.source_risque_id} -> {couple.objectif_vise_id}  "
            f"pertinence {couple.pertinence.value}, vraisemblance {couple.vraisemblance_initiale.value}"
        )
        print(f"        biens essentiels : {', '.join(couple.biens_essentiels_ids) or '—'}")
        print(f"        valeurs métier   : {', '.join(couple.valeurs_metier) or '—'}")
        print(f"        supports associés: {', '.join(couple.biens_supports_associes) or '—'}")
        print(f"        {couple.justification}")

    if output.couples_secondaires:
        print(f"\n=== Couples secondaires ({len(output.couples_secondaires)}) ===")
        for couple in output.couples_secondaires:
            print(f"  [{couple.id}] {couple.source_risque_id} -> {couple.objectif_vise_id}")

    if output.elements_ecartes:
        print(f"\n=== Éléments écartés ({len(output.elements_ecartes)}) — avec leur raison ===")
        for element in output.elements_ecartes:
            print(f"  {element.type} « {element.libelle or element.reference} » : {element.raison_label}")
            if element.detail:
                print(f"        {element.detail}")

    print(f"\n=== Contrôle qualité — statut : {output.quality_report.statut} ===")
    for check in output.quality_report.checks:
        marker = {"ok": "  ", "avertissement": "/!\\", "erreur": "XX "}.get(check.statut, "  ")
        print(f"  {marker} {check.controle} : {check.message}")


def _run_workshop(repo, mission_id, w2_input, base, revision_notes=None, blocks=None, previous=None):
    """Run the workshop and save its output. Not complete yet — no auditor decision recorded."""
    print("\n=== Atelier 2 ===")
    if revision_notes:
        print("Reprise en tenant compte des remarques de l'auditeur :")
        for note in revision_notes:
            print(f"   - {note}")
    if blocks:
        print(f"Parties régénérées : {', '.join(sorted(blocks))} (le reste est conservé).")
    output = run_workshop2(w2_input, AgnoWorkshop2Runner(), base, revision_notes, blocks, previous)
    mission_state.save_w2_output(repo, mission_id, output)
    # Deliberately NOT "approved": the auditor has not ruled on it yet (§2). A crash
    # or quit between here and approval must not read as done on --resume.
    repo.set_status(mission_id, "w2_awaiting_approval")
    return output


def _loop(repo, mission_id, w2_input, base, output) -> int:
    """The auditor's review loop for atelier 2, on the shared implementation."""
    return ApprovalLoop(
        repo=repo,
        mission_id=mission_id,
        stage=STAGE,
        workshop_number=mission_state.WORKSHOP_2,
        label="l'atelier 2",
        print_output=_print_output,
        rerun=lambda notes, blocks, previous: _run_workshop(
            repo, mission_id, w2_input, base, notes, blocks, previous),
        save=lambda corrected: mission_state.save_w2_output(repo, mission_id, corrected),
        model_cls=Workshop2Output,
        edit_examples="couples.0.pertinence        sources_risque.1.justification",
        block_labels={
            "1": (BLOCK_SOURCES, "sources de risque"),
            "2": (BLOCK_OBJECTIFS, "objectifs visés"),
            "3": (BLOCK_COUPLES, "couples SR/OV"),
        },
    ).run(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run atelier 2 on a saved mission.")
    parser.add_argument("mission_id")
    parser.add_argument("--no-session", action="store_true",
                        help="skip the client session questions")
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
    if mission_context is None or w1_output is None:
        print("Mission incomplète : il faut un Mission Context ET un résultat d'atelier 1 enregistrés.")
        return 1
    if not mission_state.is_approved(repo, args.mission_id, mission_state.WORKSHOP_1):
        # The auditor has the last word (§2): atelier 2 built on an unapproved atelier 1
        # would have to be redone entirely once the atelier 1 result changes. Asked of
        # the version, not of mission.status, which has moved on by the time atelier 3
        # runs and would then refuse a legitimate return to atelier 2.
        print(f"Statut de la mission : {mission.status} — l'atelier 1 n'est pas approuvé.")
        print("Approuvez-le d'abord : python scripts/run_workshop1_from_docs.py --resume " + args.mission_id)
        return 1

    print(f"Mission {mission.mission_id} — {mission.name}")
    w2_input = build_workshop2_input(mission_context, w1_output)
    print(f"Entrée atelier 2 : {len(w2_input.contexte)} champs de contexte, "
          f"{len(w2_input.biens_essentiels)} biens essentiels, "
          f"{len(w2_input.evenements_redoutes)} événements redoutés.")

    for alert in w2_input.alertes_atelier1:
        tag = "BLOQUANT" if alert.bloquant else "avertissement"
        print(f"  [{tag}] {alert.reference} — {alert.probleme}")

    set_token_sink(lambda inp, out, model: repo.log_tokens(
        args.mission_id, input_tokens=inp, output_tokens=out, model_used=model))
    base = load_ebios_base()

    saved = mission_state.load_w2_output(repo, args.mission_id)
    if saved is not None and mission_state.is_approved(repo, args.mission_id, mission_state.WORKSHOP_2):
        print("Atelier 2 déjà approuvé. Résultat sauvegardé :")
        _print_output(saved)
        return 0
    if saved is not None:
        # The workshop already ran and is NOT complete: resume at the approval gate on
        # what is saved, and only redo if the auditor rejects. Rerunning it up front
        # would pay for three LLM calls nobody asked for, and the session questions
        # are already answered in the Mission Context.
        print(f"Atelier 2 exécuté mais non finalisé (statut : {mission.status}) — reprise de la validation.")
        return _loop(repo, args.mission_id, w2_input, base, saved)

    if not args.no_session:
        enriched = ask_session_questions(w2_input, CLIHumanInterface())
        saved_answers = mission_state.persist_session_answers(
            repo, args.mission_id, mission_context, w2_input, enriched, stage=STAGE)
        if saved_answers:
            print(f"  {saved_answers} réponse(s) de séance enregistrée(s) dans le contexte de la mission.")
        w2_input = enriched

    notes = prior_rejection_reasons(repo, args.mission_id, STAGE)  # carries feedback across a rerun
    try:
        output = _run_workshop(repo, args.mission_id, w2_input, base, notes)
    except Atelier1DataError as exc:
        print(f"\n{exc}")
        print("Corrigez l'atelier 1 avant de relancer — l'atelier 2 ne répare rien de lui-même (§4).")
        return 1

    return _loop(repo, args.mission_id, w2_input, base, output)


if __name__ == "__main__":
    _resume = f"python scripts/run_workshop2.py {sys.argv[1] if len(sys.argv) > 1 else '<mission_id>'}"
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(interrupted("l'atelier 2", _resume)) from None
    except (Workshop2AgentError, StructuredCallFailed) as exc:
        # A failed LLM call is never reinterpreted as a methodology outcome — and it can
        # come from the redo inside the approval loop, not only from the first run.
        print(f"\nAppel au modèle en échec : {exc}")
        raise SystemExit(interrupted("l'atelier 2", _resume)) from None
