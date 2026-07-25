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
from ebios_rm.domain.fact import Fact  # noqa: E402
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


def _check_controls_available(repo, mission_id, mission_context, reference_repo):
    """Refuse to run the workshop while a declared framework has no controls (conception §2, §12.5).

    The AI cannot invent referential text, so an unloaded framework can only be
    resolved by a human: load its controls, or withdraw it explicitly with a reason.
    Returns the mission context to use, or None to stop.
    """
    from ebios_rm.mission_context.mission_context import assemble_from_facts  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.assessment import frameworks_without_controls  # noqa: PLC0415

    missing = frameworks_without_controls(mission_context.applicable_frameworks, reference_repo)
    if not missing:
        return mission_context

    print("\n=== ARRÊT : référentiels sans contrôles chargés ===")
    for framework in missing:
        print(f"   - {framework}")
    print("Ces référentiels ne peuvent pas être évalués : aucun contrôle n'est chargé.")
    print("L'agent n'invente jamais un texte de référentiel (§2).")
    print("\nDeux options :")
    print(f"  1. Remplir src/ebios_rm/plugins/frameworks/<...>/controls.json, recharger la base")
    print(f"     de référence, puis reprendre : --resume {mission_id}")
    print("  2. Retirer explicitement ces référentiels de la mission (décision tracée).")

    if not _ask_yes("Retirer ces référentiels et continuer sans eux ?"):
        repo.set_status(mission_id, "blocked_missing_controls")
        print(f"Mission arrêtée. Reprise après chargement des contrôles : --resume {mission_id}")
        return None

    reason = ""
    while not reason:
        reason = input("Motif du retrait (obligatoire, §8) : ").strip()
    kept = [f for f in mission_context.applicable_frameworks if f not in missing]
    if not kept:
        print("Aucun référentiel ne resterait déclaré — l'atelier 1 ne peut pas être évalué.")
        repo.set_status(mission_id, "blocked_missing_controls")
        return None

    facts = [f for f in mission_context.facts if f.field_name != "applicable_frameworks"]
    facts.append(Fact.declaration("applicable_frameworks", kept))
    updated = assemble_from_facts(facts)
    mission_state.save_mission_context(repo, mission_id, updated)
    repo.log_decision(mission_id, stage="workshop_1", action="frameworks_withdrawn",
                      justification=f"{', '.join(missing)} retirés : {reason}")
    print(f"Référentiels retirés. Restants : {kept}")
    return updated


def _prior_rejection_reasons(repo: MissionRepository, mission_id: str) -> list[str]:
    """Reject reasons already logged, so a redo (even after --resume) carries full feedback."""
    return [d.justification_given for d in repo.decisions(mission_id)
            if d.stage == "workshop_1" and d.action_taken == "rejected"]


def _run_workshop(repo, mission_id, mission_context, reference_repo, revision_notes=None,
                  blocks=None, previous=None):
    """Run the workshop and save its output. Not complete yet — no auditor decision recorded.

    ``blocks`` limits a redo to the parts the auditor rejected; the rest is reused
    from ``previous`` verbatim (conception §12.6).
    """
    from ebios_rm.workshops.workshop1_cadrage.agent import AgnoWorkshop1Runner  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.workshop import run_workshop1  # noqa: PLC0415

    print("\n=== Phase 2 : atelier 1 ===")
    if revision_notes:
        print("Reprise en tenant compte des remarques de l'auditeur :")
        for note in revision_notes:
            print(f"   - {note}")
    if blocks:
        print(f"Parties régénérées : {', '.join(sorted(blocks))} (le reste est conservé).")
    output = run_workshop1(mission_context, AgnoWorkshop1Runner(), reference_repo,
                           revision_notes, blocks, previous)
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
        totals = repo.token_totals(mission_id)
        print(f"Atelier 1 approuvé. Mission {mission_id} sauvegardée.")
        print(f"Tokens consommés : {totals['input_tokens']} entrée / "
              f"{totals['output_tokens']} sortie sur {totals['llm_calls']} appels.")
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


def _ask_blocks(io_in=input, io_out=print) -> set[str]:
    """Which parts of the output to regenerate — the rest is kept verbatim (§12.6)."""
    from ebios_rm.workshops.workshop1_cadrage.workshop import (  # noqa: PLC0415
        ALL_BLOCKS, BLOCK_BASELINE, BLOCK_CADRAGE, BLOCK_LEGAL,
    )

    labels = {
        "1": (BLOCK_CADRAGE, "biens essentiels / supports et événements redoutés"),
        "2": (BLOCK_BASELINE, "écarts du socle de sécurité"),
        "3": (BLOCK_LEGAL, "impacts juridiques"),
    }
    io_out("\nQuelles parties faut-il refaire ? (numéros séparés par des virgules, vide = tout)")
    for key, (_, label) in labels.items():
        io_out(f"   [{key}] {label}")
    while True:
        answer = io_in("> ").strip()
        if not answer:
            return set(ALL_BLOCKS)
        keys = [k.strip() for k in answer.split(",") if k.strip()]
        if keys and all(k in labels for k in keys):
            return {labels[k][0] for k in keys}
        io_out(f"    Réponse attendue : {', '.join(labels)} (ou vide pour tout refaire).")


def _ask_choice(question: str, options: dict[str, str], io_in=input, io_out=print) -> str:
    while True:
        io_out(f"\n{question}")
        for key, label in options.items():
            io_out(f"   [{key}] {label}")
        answer = io_in("> ").strip().casefold()
        if answer in options:
            return answer
        io_out(f"    Réponse attendue : {', '.join(options)}.")


def _ask_yes(question: str, io_in=input, io_out=print) -> bool:
    while True:
        answer = io_in(f"{question} [oui/non] : ").strip().casefold()
        if answer in {"oui", "o", "yes", "y"}:
            return True
        if answer in {"non", "n", "no"}:
            return False
        io_out("    Répondez 'oui' ou 'non'.")


def _edit_output(repo, mission_id, output):
    """Let the auditor correct values directly, each with a mandatory justification (§2, §8).

    Saved as a new version carrying the edit trail, so nothing is overwritten and the
    report agent can show what the auditor overrode.
    """
    from ebios_rm.workshops.workshop1_cadrage.human_edit import EditError, apply_edit, get_value  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output  # noqa: PLC0415

    data = output.model_dump(mode="json")
    changed = False
    print("\n=== Correction manuelle ===")
    print("Indiquez le chemin du champ à corriger, par exemple :")
    print("   evenements_redoutes.0.gravite        baseline_gaps_full.1.weakness")
    print("Entrée vide pour terminer.")

    while True:
        path = input("Chemin : ").strip()
        if not path:
            break
        try:
            current = get_value(data, path)
        except EditError as exc:
            print(f"   {exc}")
            continue
        print(f"   Valeur actuelle : {current!r}")
        new_value = input("Nouvelle valeur : ").strip()
        if not new_value:
            print("   Annulé.")
            continue
        reason = ""
        while not reason:
            reason = input("Justification (obligatoire, §8) : ").strip()
        try:
            data = apply_edit(data, path, new_value, justification=reason)
        except EditError as exc:
            print(f"   {exc}")
            continue
        repo.log_decision(mission_id, stage="workshop_1", action=f"edited:{path}", justification=reason)
        print("   Modification enregistrée.")
        changed = True

    if not changed:
        return output
    edited = Workshop1Output.model_validate(data)
    mission_state.save_w1_output(repo, mission_id, edited)
    repo.set_status(mission_id, "w1_awaiting_approval")
    print("Version corrigée sauvegardée.")
    return edited


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

        choice = _ask_choice(
            "Que voulez-vous faire ?",
            {"c": "corriger vous-même un ou plusieurs champs",
             "r": "relancer l'agent en tenant compte du motif",
             "q": "en rester là (dernière version conservée, non approuvée)"},
        )
        if choice == "q":
            print("Dernière version conservée (non approuvée).")
            return 1
        if choice == "c":
            output = _edit_output(repo, mission_id, output)
            continue

        if not mission_state.can_redo(repo, mission_id, mission_state.WORKSHOP_1) and not _reinforced_confirm():
            print("Dernière version conservée (non approuvée).")
            return 1

        blocks = _ask_blocks()
        notes = _prior_rejection_reasons(repo, mission_id)  # includes the reason just logged
        output = _run_workshop(repo, mission_id, mission_context, reference_repo, notes,
                               blocks, output)


def _run_workshop_and_finish(
    repo: MissionRepository, mission_id: str, mission_context, reference_repo: ReferenceRepository
) -> int:
    checked = _check_controls_available(repo, mission_id, mission_context, reference_repo)
    if checked is None:
        return 2
    mission_context = checked
    notes = _prior_rejection_reasons(repo, mission_id)
    output = _run_workshop(repo, mission_id, mission_context, reference_repo, notes)
    return _approval_loop(repo, mission_id, mission_context, reference_repo, output)


def _install_token_sink(repo: MissionRepository, mission_id: str) -> None:
    """Record every LLM call's tokens against this mission (money stays 0 — no price table)."""
    from ebios_rm.agent_runtime import set_token_sink  # noqa: PLC0415

    set_token_sink(lambda inp, out, model: repo.log_tokens(
        mission_id, input_tokens=inp, output_tokens=out, model_used=model))


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
    _install_token_sink(repo, mission_id)
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
    _install_token_sink(repo, mission_id)

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
    if mission.status == "blocked_missing_controls":
        # Controls were missing last time — re-check now that a human may have loaded them.
        print("Mission bloquée précédemment (référentiels sans contrôles) — nouvelle vérification.")
        return _run_workshop_and_finish(repo, mission_id, mission_context, reference_repo)

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
