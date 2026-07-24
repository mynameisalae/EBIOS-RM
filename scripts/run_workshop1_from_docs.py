"""Dev runner for Workshop 1 via DOCUMENT INGESTION, with mission persistence (conception §11, §12, §15).

    # new mission from a filled questionnaire (+ optional supporting docs)
    python scripts/run_workshop1_from_docs.py <filled_questionnaire> [supporting_doc ...]

    # list saved missions
    python scripts/run_workshop1_from_docs.py --list

    # resume a saved mission by id (skips phases already done)
    python scripts/run_workshop1_from_docs.py --resume <mission_id>

Everything is saved to the mission SQLite DB (data/mission/mission.db by default):
the Mission Context after intake, the w1_output after the workshop, and every
decision (approval / rejection) in the decision log. Stopping and re-running
--resume continues where you left off.

Requires OPENROUTER_API_KEY (.env) and `pip install -r requirements.txt`. Run from
a real terminal so the interactive prompts work.
"""

from __future__ import annotations

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
from ebios_rm.repositories.mission_repository import MissionRepository, connect  # noqa: E402
from ebios_rm.repositories.reference_repository import ReferenceRepository  # noqa: E402

DEV_SEED = Path(__file__).resolve().parents[1] / "data" / "dev_seed" / "baseline_controls.dev.json"


def _reference_repo() -> ReferenceRepository:
    return ReferenceRepository(
        build_reference_db(":memory:", extra_controls=json.loads(DEV_SEED.read_text(encoding="utf-8")))
    )


def _print_missions(repo: MissionRepository) -> None:
    missions = repo.list_missions()
    if not missions:
        print("Aucune mission enregistrée.")
        return
    print(f"{'MISSION_ID':34}  {'STATUT':14}  {'MAJ':20}  NOM")
    for m in missions:
        print(f"{m.mission_id:34}  {m.status:14}  {m.updated_at[:19]:20}  {m.name}")


def _prior_rejection_reasons(repo: MissionRepository, mission_id: str) -> list[str]:
    """Reject reasons already logged, so a redo (even after --resume) carries full feedback."""
    return [d.justification_given for d in repo.decisions(mission_id)
            if d.stage == "workshop_1" and d.action_taken == "rejected"]


def _run_workshop(repo, mission_id, mission_context, reference_repo, revision_notes=None):
    """Run the workshop and save its output. Not complete yet — no auditor decision recorded."""
    from ebios_rm.workshops.workshop1_cadrage.agent import AgnoWorkshop1Runner  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.workshop import run_workshop1  # noqa: PLC0415

    print("\n=== Phase 2 : atelier 1 ===")
    if revision_notes:
        print("Reprise en tenant compte des remarques de l'auditeur :")
        for note in revision_notes:
            print(f"   - {note}")
    output = run_workshop1(mission_context, AgnoWorkshop1Runner(), reference_repo, revision_notes)
    mission_state.save_w1_output(repo, mission_id, output)
    # Deliberately NOT "completed": the auditor has not ruled on it yet (§2). A crash
    # or quit between here and approval must not read as done on --resume.
    repo.set_status(mission_id, "w1_awaiting_approval")
    return output


def _review_and_approve(repo, mission_id, mission_context, output):
    """Clarification + the final approval gate. Returns (approved, reason)."""
    from ebios_rm.mission_context.clarification import clarification_repl  # noqa: PLC0415
    from ebios_rm.mission_context.clarification_agent import AgnoClarificationRunner  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.human_interface import approve_workshop  # noqa: PLC0415

    print("\n=== w1_output ===")
    print(json.dumps(output.model_dump(mode="json"), ensure_ascii=False, indent=2))

    clarification_repl(AgnoClarificationRunner(), mission_context, output)

    version = repo.latest_output(mission_id, mission_state.WORKSHOP_1)
    approved, reason = approve_workshop("l'atelier 1")
    if approved:
        repo.log_decision(mission_id, stage="workshop_1", action="approved", justification="Approuvé par l'auditeur")
        repo.set_status(mission_id, "w1_approved")
        if version:
            repo.set_version_status(mission_id, mission_state.WORKSHOP_1, version.version_number, "approved")
        print(f"Atelier 1 approuvé. Mission {mission_id} sauvegardée.")
    else:
        repo.log_decision(mission_id, stage="workshop_1", action="rejected", justification=reason)
        repo.set_status(mission_id, "w1_rejected")
        if version:
            repo.set_version_status(mission_id, mission_state.WORKSHOP_1, version.version_number, "rejected")
        print(f"Atelier 1 non approuvé : {reason}")
    return approved, reason


def _reinforced_confirm(io_in=input, io_out=print) -> bool:
    """Rollback cap reached (conception §12.6) — require an explicit typed confirmation to go further."""
    io_out(f"\nPlafond de {mission_state.ROLLBACK_CAP} versions atteint pour l'atelier 1 (§12.6).")
    io_out("Une nouvelle reprise est inhabituelle. Tapez CONFIRMER pour relancer malgré tout,")
    io_out("ou toute autre saisie pour arrêter et conserver la dernière version.")
    return io_in("> ").strip() == "CONFIRMER"


def _ask_yes(question: str, io_in=input, io_out=print) -> bool:
    while True:
        answer = io_in(f"{question} [oui/non] : ").strip().casefold()
        if answer in {"oui", "o", "yes", "y"}:
            return True
        if answer in {"non", "n", "no"}:
            return False
        io_out("    Répondez 'oui' ou 'non'.")


def _approval_loop(repo, mission_id, mission_context, reference_repo, output) -> int:
    """Review the given output, and on rejection loop into redo (conception §12.6).

    Each rejection's reason is fed into the agent's next attempt so the redo
    addresses it; prior reasons are reloaded from the decision log so this stays
    correct across a --resume. Bounded by the rollback cap — going past it needs a
    reinforced confirmation.
    """
    while True:
        approved, _reason = _review_and_approve(repo, mission_id, mission_context, output)
        if approved:
            return 0

        if not mission_state.can_redo(repo, mission_id, mission_state.WORKSHOP_1):
            if not _reinforced_confirm():
                print("Dernière version conservée (non approuvée).")
                return 1
        elif not _ask_yes("Relancer l'atelier 1 en tenant compte de ce motif ?"):
            print("Dernière version conservée (non approuvée).")
            return 1

        notes = _prior_rejection_reasons(repo, mission_id)  # includes the reason just logged
        output = _run_workshop(repo, mission_id, mission_context, reference_repo, notes)


def _run_workshop_and_finish(
    repo: MissionRepository, mission_id: str, mission_context, reference_repo: ReferenceRepository
) -> int:
    notes = _prior_rejection_reasons(repo, mission_id)
    output = _run_workshop(repo, mission_id, mission_context, reference_repo, notes)
    return _approval_loop(repo, mission_id, mission_context, reference_repo, output)


def _checkpoint(repo: MissionRepository, mission_id: str):
    """Persist intake progress after every answer, so a mid-Q&A crash resumes at the next gap."""
    from ebios_rm.mission_context.mission_context import assemble_from_facts  # noqa: PLC0415

    def save(facts):
        mission_state.checkpoint_mission_context(repo, mission_id, assemble_from_facts(facts))

    return save


def _finish_intake(repo: MissionRepository, mission_id: str, mission_context) -> None:
    mission_state.save_mission_context(repo, mission_id, mission_context)
    repo.set_status(mission_id, "context_ready")
    repo.log_decision(mission_id, stage="intake", action="context_validated",
                      justification=f"{len(mission_context.facts)} faits validés")
    print(f"\nMission Context : {len(mission_context.facts)} faits validés (sauvegardé).")


def _new_mission(repo: MissionRepository, reference_repo: ReferenceRepository, argv: list[str]) -> int:
    from ebios_rm.mission_context.conversation import AgnoConversationRunner  # noqa: PLC0415
    from ebios_rm.mission_context.ingestion_agent import AgnoIngestionRunner  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.auditor_review import AgnoAuditorReviewRunner  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.human_interface import ConversationalHumanInterface  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.intake_ingestion import complete_intake_from_documents  # noqa: PLC0415

    intake_doc = argv[0]
    supporting = argv[1:]
    mission_id = repo.create_mission(name=Path(intake_doc).stem, frameworks=[])
    print(f"Nouvelle mission : {mission_id}\n(reprise possible à tout moment : --resume {mission_id})")

    human = ConversationalHumanInterface(AgnoConversationRunner())
    print("\n=== Phase 1 : ingestion des documents (l'agent lit, vous décidez) ===")
    mission_context = complete_intake_from_documents(
        intake_doc, supporting, AgnoIngestionRunner(), human, AgnoAuditorReviewRunner(),
        checkpoint=_checkpoint(repo, mission_id),
    )
    _finish_intake(repo, mission_id, mission_context)
    return _run_workshop_and_finish(repo, mission_id, mission_context, reference_repo)


def _resume_mission(repo: MissionRepository, reference_repo: ReferenceRepository, mission_id: str) -> int:
    mission = repo.get_mission(mission_id)
    if mission is None:
        print(f"Mission introuvable : {mission_id}")
        return 2
    print(f"Reprise de la mission {mission_id} — statut : {mission.status}")

    saved = mission_state.load_mission_context(repo, mission_id)
    if saved is None:
        print("Aucune progression sauvegardée — relancez la mission depuis le document.")
        return 2
    print(f"Contexte rechargé : {len(saved.facts)} faits déjà saisis.")

    if mission.status == "w1_approved":
        # The only status that means genuinely complete (§2 — auditor had the last word).
        existing = mission_state.load_w1_output(repo, mission_id)
        print("Atelier 1 déjà approuvé. Résultat sauvegardé :")
        print(json.dumps(existing.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0

    mission_context = saved
    if mission.status == "in_progress":
        # Intake was interrupted mid-Q&A — continue asking from the first unanswered question.
        from ebios_rm.mission_context.conversation import AgnoConversationRunner  # noqa: PLC0415
        from ebios_rm.workshops.workshop1_cadrage.auditor_review import AgnoAuditorReviewRunner  # noqa: PLC0415
        from ebios_rm.workshops.workshop1_cadrage.human_interface import ConversationalHumanInterface  # noqa: PLC0415
        from ebios_rm.workshops.workshop1_cadrage.intake_ingestion import resume_intake  # noqa: PLC0415

        print("Intake incomplet — reprise du questionnaire là où il s'est arrêté.")
        human = ConversationalHumanInterface(AgnoConversationRunner())
        mission_context = resume_intake(
            saved.facts, human, AgnoAuditorReviewRunner(), checkpoint=_checkpoint(repo, mission_id)
        )
        _finish_intake(repo, mission_id, mission_context)

    if mission.status in {"w1_awaiting_approval", "w1_rejected"}:
        # The workshop already ran (output exists) but is NOT complete — no LLM rerun
        # up front; resume at the approval gate, then redo only if the auditor rejects.
        existing = mission_state.load_w1_output(repo, mission_id)
        print(f"Atelier 1 exécuté mais non finalisé (statut : {mission.status}) — reprise de la validation.")
        return _approval_loop(repo, mission_id, mission_context, reference_repo, existing)

    return _run_workshop_and_finish(repo, mission_id, mission_context, reference_repo)


def main(argv: list[str]) -> int:
    settings = load_settings()
    repo = MissionRepository(connect(settings.mission_db_path))

    if len(argv) >= 2 and argv[1] == "--list":
        _print_missions(repo)
        return 0

    if len(argv) >= 3 and argv[1] == "--resume":
        if not settings.openrouter_api_key:
            print("OPENROUTER_API_KEY is not set — put it in .env before running.")
            return 2
        print(f"Model: {settings.model_id}  (OpenRouter)")
        return _resume_mission(repo, _reference_repo(), argv[2])

    if len(argv) < 2:
        print("usage: run_workshop1_from_docs.py <filled_questionnaire> [supporting_doc ...]")
        print("       run_workshop1_from_docs.py --list")
        print("       run_workshop1_from_docs.py --resume <mission_id>")
        return 2

    if not settings.openrouter_api_key:
        print("OPENROUTER_API_KEY is not set — put it in .env before running.")
        return 2
    print(f"Model: {settings.model_id}  (OpenRouter)")
    return _new_mission(repo, _reference_repo(), argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
