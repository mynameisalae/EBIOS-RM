"""Dev runner for Workshop 2 — sources de risque et objectifs visés (white-box atelier 2).

    # run atelier 2 on a mission whose atelier 1 is approved
    python scripts/run_workshop2.py <mission_id>

    # redo after a rejection, with the auditor's reasons
    python scripts/run_workshop2.py <mission_id> --revision "Trop de sources retenues"

    # redo one part only, keeping the rest verbatim
    python scripts/run_workshop2.py <mission_id> --blocks couples --revision "Priorités à revoir"

    # skip the client session (use the context as-is)
    python scripts/run_workshop2.py <mission_id> --no-session

Reads the Mission Context and the approved w1_output from the mission DB, runs the
session questions, runs the workshop, saves the w2_output as a new version, and
asks the auditor to approve it.

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

from ebios_rm.agent_runtime import set_token_sink  # noqa: E402
from ebios_rm.config import load_settings  # noqa: E402
from ebios_rm.orchestrator import mission_state  # noqa: E402
from ebios_rm.plugins.registry import load_ebios_base  # noqa: E402
from ebios_rm.repositories.mission_repository import MissionRepository, connect  # noqa: E402
from ebios_rm.workshops.workshop1_cadrage.human_edit import EditError, apply_edit, get_value  # noqa: E402
from ebios_rm.workshops.workshop1_cadrage.human_interface import (  # noqa: E402
    CLIHumanInterface,
    approve_workshop,
)
from ebios_rm.workshops.workshop2_sources_risque import (  # noqa: E402
    ALL_BLOCKS,
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


def _persist_session_answers(repo, mission_id, mission_context, w2_input, enriched) -> None:
    """Session answers are facts about the organisation — they belong to the mission.

    Written back to the Mission Context so a rerun does not ask them again, and so
    the report agent sees them with their provenance intact.
    """
    known = {f.field_name for f in w2_input.faits_contexte}
    new_facts = [f for f in enriched.faits_contexte if f.field_name not in known]
    if not new_facts:
        return
    updated = mission_context.model_copy(update={"facts": [*mission_context.facts, *new_facts]})
    mission_state.save_mission_context(repo, mission_id, updated)
    repo.log_decision(
        mission_id, stage=STAGE, action=f"session_answers:{len(new_facts)}",
        justification="; ".join(f.field_name for f in new_facts),
    )
    print(f"  {len(new_facts)} réponse(s) de séance enregistrée(s) dans le contexte de la mission.")


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


# --- Reject -> redo loop, bounded by the rollback cap (mirrors run_workshop1_from_docs.py) ---

def _prior_rejection_reasons(repo: MissionRepository, mission_id: str) -> list[str]:
    """Reject reasons already logged, so a redo (even after --resume) carries full feedback."""
    return [d.justification_given for d in repo.decisions(mission_id)
            if d.stage == STAGE and d.action_taken == "rejected"]


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


def _review_and_approve(repo, mission_id, output) -> tuple[bool, str]:
    _print_output(output)
    version = repo.latest_output(mission_id, mission_state.WORKSHOP_2)
    approved, reason = approve_workshop("l'atelier 2")
    if approved:
        repo.log_decision(mission_id, stage=STAGE, action="approved", justification="Approuvé par l'auditeur")
        repo.set_status(mission_id, "w2_approved")
        if version:
            repo.set_version_status(mission_id, mission_state.WORKSHOP_2, version.version_number, "approved")
        totals = repo.token_totals(mission_id)
        print(f"Atelier 2 approuvé. Mission {mission_id} sauvegardée.")
        print(f"Tokens consommés : {totals['input_tokens']} entrée / "
              f"{totals['output_tokens']} sortie sur {totals['llm_calls']} appels.")
    else:
        repo.log_decision(mission_id, stage=STAGE, action="rejected", justification=reason)
        repo.set_status(mission_id, "w2_rejected")
        if version:
            repo.set_version_status(mission_id, mission_state.WORKSHOP_2, version.version_number, "rejected")
        print(f"Atelier 2 non approuvé : {reason}")
    return approved, reason


def _reinforced_confirm(io_in=input, io_out=print) -> bool:
    """Rollback cap reached (conception §12.6) — require an explicit typed confirmation to go further."""
    io_out(f"\nPlafond de {mission_state.ROLLBACK_CAP} versions atteint pour l'atelier 2 (§12.6).")
    io_out("Une nouvelle reprise est inhabituelle. Tapez CONFIRMER pour relancer malgré tout,")
    io_out("ou toute autre saisie pour arrêter et conserver la dernière version.")
    return io_in("> ").strip() == "CONFIRMER"


def _ask_blocks(io_in=input, io_out=print) -> set[str]:
    """Which parts of the output to regenerate — the rest is kept verbatim (§12.6)."""
    labels = {
        "1": (BLOCK_SOURCES, "sources de risque"),
        "2": (BLOCK_OBJECTIFS, "objectifs visés"),
        "3": (BLOCK_COUPLES, "couples SR/OV"),
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


def _edit_output(repo, mission_id, output: Workshop2Output) -> Workshop2Output:
    """Let the auditor correct values directly, each with a mandatory justification (§2, §8)."""
    data = output.model_dump(mode="json")
    changed = False
    print("\n=== Correction manuelle ===")
    print("Indiquez le chemin du champ à corriger, par exemple :")
    print("   couples.0.pertinence        sources_risque.1.justification")
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
        new_raw = input("   Nouvelle valeur : ").strip()
        if not new_raw:
            continue
        reason = input("   Justification (obligatoire, §8) : ").strip()
        try:
            data = apply_edit(data, path, new_raw, justification=reason)
        except EditError as exc:
            print(f"   {exc}")
            continue
        repo.log_decision(mission_id, stage=STAGE, action=f"edited:{path}", justification=reason)
        print("   Modification enregistrée.")
        changed = True

    if not changed:
        return output
    edited = Workshop2Output.model_validate(data)
    mission_state.save_w2_output(repo, mission_id, edited)
    repo.set_status(mission_id, "w2_awaiting_approval")
    print("Version corrigée sauvegardée.")
    return edited


def _approval_loop(repo, mission_id, w2_input, base, output) -> int:
    """Review the given output, and on rejection loop into redo (conception §12.6).

    Runs entirely within this process invocation, exactly like atelier 1's
    _approval_loop: reject -> choose (correct / relaunch / stop) -> redo -> review
    again, bounded by the rollback cap.
    """
    while True:
        approved, _reason = _review_and_approve(repo, mission_id, output)
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

        if not mission_state.can_redo(repo, mission_id, mission_state.WORKSHOP_2) and not _reinforced_confirm():
            print("Dernière version conservée (non approuvée).")
            return 1

        blocks = _ask_blocks()
        notes = _prior_rejection_reasons(repo, mission_id)  # includes the reason just logged
        output = _run_workshop(repo, mission_id, w2_input, base, notes, blocks, output)


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
    if mission.status != "w1_approved":
        # The auditor has the last word (§2): atelier 2 built on an unapproved atelier 1
        # would have to be redone entirely once the atelier 1 result changes.
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

    if not args.no_session:
        enriched = ask_session_questions(w2_input, CLIHumanInterface())
        _persist_session_answers(repo, args.mission_id, mission_context, w2_input, enriched)
        w2_input = enriched

    set_token_sink(lambda inp, out, model: repo.log_tokens(
        args.mission_id, input_tokens=inp, output_tokens=out, model_used=model))

    base = load_ebios_base()
    notes = _prior_rejection_reasons(repo, args.mission_id)  # carries feedback across a rerun
    try:
        output = _run_workshop(repo, args.mission_id, w2_input, base, notes)
    except Atelier1DataError as exc:
        print(f"\n{exc}")
        print("Corrigez l'atelier 1 avant de relancer — l'atelier 2 ne répare rien de lui-même (§4).")
        return 1
    except Workshop2AgentError as exc:
        # A failed LLM call is never reinterpreted as a methodology outcome.
        print(f"\nAppel au modèle en échec : {exc}")
        return 1

    return _approval_loop(repo, args.mission_id, w2_input, base, output)


if __name__ == "__main__":
    raise SystemExit(main())
