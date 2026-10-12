"""Demo runner: real Workshop 1 + the Orchestrator, together, on one mission.

    # new mission from a filled questionnaire (+ optional supporting docs)
    python scripts/run_mission_via_orchestrator.py <filled_questionnaire> [supporting_doc ...]

    # list saved missions
    python scripts/run_mission_via_orchestrator.py --list

    # resume a saved mission by id (skips intake if already done)
    python scripts/run_mission_via_orchestrator.py --resume <mission_id>

Requires OPENROUTER_API_KEY (.env) and a real terminal — the intake phase and
Workshop 1's own agent-facing prompts need real stdin, exactly like
scripts/run_workshop1_from_docs.py.

Intake (document ingestion, follow-up questions, contradiction resolution) is
untouched — same functions, same behavior as the existing script. The only
difference starts once the mission reaches 'context_ready': from there on,
Orchestrator.run_mission() drives the atelier instead of the CLI script's own
_run_workshop_and_finish/_approval_loop. This is the actual thing being
demonstrated — everything up to that point is the same proven intake flow.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr, sys.stdin):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ebios_rm.config import load_settings  # noqa: E402
from ebios_rm.db.loader import build_reference_db  # noqa: E402
from ebios_rm.orchestrator import mission_state  # noqa: E402
from ebios_rm.orchestrator.orchestrator import Orchestrator  # noqa: E402
from ebios_rm.orchestrator.workshop1_runner import Workshop1Runner  # noqa: E402
from ebios_rm.repositories.mission_repository import MissionRepository, connect  # noqa: E402
from ebios_rm.repositories.reference_repository import ReferenceRepository  # noqa: E402

DEV_SEED = Path(__file__).resolve().parents[1] / "data" / "dev_seed" / "baseline_controls.dev.json"


def _reference_repo() -> ReferenceRepository:
    conn = build_reference_db(":memory:")
    if conn.execute("SELECT COUNT(*) FROM baseline_controls").fetchone()[0] == 0:
        print("Aucun contrôle dans les plugins — chargement du jeu d'exemple [SAMPLE].")
        conn = build_reference_db(":memory:", extra_controls=json.loads(DEV_SEED.read_text(encoding="utf-8")))
    return ReferenceRepository(conn)


def _print_missions(repo: MissionRepository) -> None:
    missions = repo.list_missions()
    if not missions:
        print("Aucune mission enregistrée.")
        return
    print(f"{'MISSION_ID':34}  {'STATUT':22}  {'MAJ':20}  NOM")
    for m in missions:
        print(f"{m.mission_id:34}  {m.status:22}  {m.updated_at[:19]:20}  {m.name}")


def _run_orchestrator_phase(repo: MissionRepository, reference_repo: ReferenceRepository, mission_id: str) -> int:
    """Shared by both new-mission and --resume: everything from 'context_ready' onward."""
    mission_context = mission_state.load_mission_context(repo, mission_id)
    if mission_context is None:
        print("Aucun Mission Context sauvegardé pour cette mission.")
        return 2

    print("\n=== À partir d'ici, l'Orchestrateur prend le relais ===")
    workshop1 = Workshop1Runner(reference_repo, repo)

    checked_context = workshop1.check_controls_available(mission_context, mission_id)
    if checked_context is None:
        print("Mission arrêtée : référentiels sans contrôles chargés.")
        return 2
    if checked_context is not mission_context:
        mission_state.save_mission_context(repo, mission_id, checked_context)

    orchestrator = Orchestrator(repo, {1: workshop1})
    asyncio.run(orchestrator.run_mission(mission_id))

    final = repo.get_mission(mission_id)
    print(f"\n=== Statut final de la mission : {final.status} ===")
    output = mission_state.load_w1_output(repo, mission_id)
    if output is not None:
        print(f"Biens essentiels     : {len(output.biens_essentiels)}")
        print(f"Biens supports       : {len(output.biens_supports)}")
        print(f"Événements redoutés  : {len(output.evenements_redoutes)}")
        print(f"Écarts du socle      : {len(output.baseline_gaps_full)}")
        print(f"Non vérifiables      : {len(output.unverified_controls)}")
    totals = repo.token_totals(mission_id)
    print(f"\nTokens utilisés : {totals['input_tokens']} in / {totals['output_tokens']} out sur {totals['llm_calls']} appel(s).")

    if final.status not in ("blocked_missing_controls",) and not final.status.startswith("w1_approved"):
        print(f"\nMission non terminée (statut : {final.status}). Reprise possible :")
        print(f"  python scripts/run_mission_via_orchestrator.py --resume {mission_id}")
    return 0


def _new_mission(repo: MissionRepository, reference_repo: ReferenceRepository, argv: list[str]) -> int:
    from ebios_rm.agent_runtime import set_token_sink  # noqa: PLC0415
    from ebios_rm.mission_context.conversation import AgnoConversationRunner  # noqa: PLC0415
    from ebios_rm.mission_context.ingestion_agent import AgnoIngestionRunner  # noqa: PLC0415
    from ebios_rm.mission_context.mission_context import assemble_from_facts  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.auditor_review import AgnoAuditorReviewRunner  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.human_interface import ConversationalHumanInterface  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.intake_ingestion import complete_intake_from_documents  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.intake_review import AgnoIntakeReviewRunner  # noqa: PLC0415

    intake_doc, *supporting = argv
    for path in [intake_doc, *supporting]:
        if not Path(path).exists():
            print(f"Document introuvable : {path}")
            return 2

    mission_id = repo.create_mission(name=Path(intake_doc).stem, frameworks=[])
    print(f"Nouvelle mission : {mission_id}")
    print(f"(reprise possible à tout moment : --resume {mission_id})")
    set_token_sink(lambda inp, out, model: repo.log_tokens(
        mission_id, input_tokens=inp, output_tokens=out, model_used=model))

    human = ConversationalHumanInterface(AgnoConversationRunner())

    print("\n=== Phase 1 : intake (identique au script existant) ===")

    def checkpoint(facts):
        mission_state.checkpoint_mission_context(repo, mission_id, assemble_from_facts(facts))

    mission_context = complete_intake_from_documents(
        intake_doc, supporting, AgnoIngestionRunner(), human, AgnoAuditorReviewRunner(),
        checkpoint=checkpoint, intake_reviewer=AgnoIntakeReviewRunner(),
    )
    mission_state.save_mission_context(repo, mission_id, mission_context)
    repo.set_status(mission_id, "context_ready")
    print(f"\nMission Context prêt : {len(mission_context.facts)} faits validés.")

    return _run_orchestrator_phase(repo, reference_repo, mission_id)


def _resume_mission(repo: MissionRepository, reference_repo: ReferenceRepository, mission_id: str) -> int:
    from ebios_rm.agent_runtime import set_token_sink  # noqa: PLC0415

    mission = repo.get_mission(mission_id)
    if mission is None:
        print(f"Mission introuvable : {mission_id}")
        return 2
    print(f"Reprise de la mission {mission_id} — statut : {mission.status}")
    set_token_sink(lambda inp, out, model: repo.log_tokens(
        mission_id, input_tokens=inp, output_tokens=out, model_used=model))

    if mission.status.startswith("w1_approved"):
        output = mission_state.load_w1_output(repo, mission_id)
        print("Atelier 1 déjà approuvé.")
        if output is not None:
            print(f"Biens essentiels : {len(output.biens_essentiels)}")
            print(f"Événements redoutés : {len(output.evenements_redoutes)}")
        return 0

    # Any other status: hand straight to the orchestrator phase. Intake is not
    # re-driven here — this script only resumes past context_ready. A crash
    # mid-atelier (not a graceful WorkshopHalted) leaves status stuck at
    # 'wN_running'; next_action() maps that to resume_workshop, which calls
    # workshop.resume() — not implemented for atelier 1 yet (see
    # Workshop1Runner.resume()). If that happens, reset the status back to
    # 'context_ready' before retrying (a fresh run() attempt, not a resume).
    if mission.status == "w1_running":
        print("Statut bloqué sur 'w1_running' (probablement une erreur modèle en cours de run).")
        print("Réinitialisation à 'context_ready' pour relancer proprement l'atelier 1.")
        repo.set_status(mission_id, "context_ready")

    return _run_orchestrator_phase(repo, reference_repo, mission_id)


def main(argv: list[str]) -> int:
    settings = load_settings()
    if not settings.openrouter_api_key:
        print("OPENROUTER_API_KEY is not set — put it in .env before running.")
        return 2
    print(f"Model: {settings.model_id}  (OpenRouter)")

    repo = MissionRepository(connect("data/mission/mission.db"))

    if argv and argv[0] == "--list":
        _print_missions(repo)
        return 0

    if argv and argv[0] == "--resume":
        if len(argv) < 2:
            print("usage: run_mission_via_orchestrator.py --resume <mission_id>")
            return 2
        return _resume_mission(repo, _reference_repo(), argv[1])

    if not argv:
        print(__doc__)
        return 2

    return _new_mission(repo, _reference_repo(), argv)


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (KeyboardInterrupt, EOFError):
        print("\nInterrompu.")
        raise SystemExit(130) from None
