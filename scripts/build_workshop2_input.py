"""Build the atelier 2 input from a saved mission, and report what is still missing.

    python scripts/build_workshop2_input.py <mission_id> [--out FILE] [--json]

Reads the Mission Context and the approved w1_output from the mission DB
(data/mission/mission.db by default), applies the atelier 2 input contract
(build_workshop2_input), and writes the resulting Workshop2Input as JSON.

No LLM call, no network: this is the pure step. It prints what atelier 2 will
actually see, the atelier 1 defects it found, and the session questions still to
put to the client — so you know what a real run has to work with before spending
any request on it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ebios_rm.config import load_settings  # noqa: E402
from ebios_rm.orchestrator import mission_state  # noqa: E402
from ebios_rm.repositories.mission_repository import MissionRepository, connect  # noqa: E402
from ebios_rm.workshops.workshop2_sources_risque import (  # noqa: E402
    build_workshop2_input,
    session_questions,
)

DEFAULT_OUT = Path("data/mission/w2_input_{mission_id}.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the atelier 2 input from a saved mission.")
    parser.add_argument("mission_id")
    parser.add_argument("--out", help="where to write the JSON (default: data/mission/w2_input_<id>.json)")
    parser.add_argument("--json", action="store_true", help="print the input to stdout as well")
    args = parser.parse_args()

    settings = load_settings()
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

# AJOUTEZ ce contrôle de statut juste en dessous :
    if mission.status != "w1_approved":
        print(
            f"Erreur : Impossible de préparer l'Atelier 2 car l'Atelier 1 n'est pas approuvé "
            f"(Statut actuel de la mission : {mission.status})."
        )
        return 1
    w2_input = build_workshop2_input(mission_context, w1_output)

    out_path = Path(args.out) if args.out else Path(
        str(DEFAULT_OUT).format(mission_id=args.mission_id)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(w2_input.model_dump_json(indent=2), encoding="utf-8")

    print(f"Mission {mission.mission_id} — {mission.name} (statut : {mission.status})")
    print(f"Entrée atelier 2 écrite : {out_path}")
    print(
        f"  {len(w2_input.biens_essentiels)} biens essentiels, "
        f"{len(w2_input.biens_supports)} biens supports, "
        f"{len(w2_input.evenements_redoutes)} événements redoutés"
    )
    print(f"  {len(w2_input.contexte)} champs de contexte retenus sur {len(mission_context.facts)} faits")
    for field in sorted(w2_input.contexte):
        value = str(w2_input.contexte[field]).replace("\n", " ")
        print(f"    - {field}: {value[:100]}{'…' if len(value) > 100 else ''}")

    if w2_input.alertes_atelier1:
        print("\n  Anomalies relevées dans l'atelier 1 (white-box §4) :")
        for alert in w2_input.alertes_atelier1:
            tag = "BLOQUANT" if alert.bloquant else "avertissement"
            print(f"    [{tag}] {alert.reference} — {alert.probleme}")
        if w2_input.alertes_bloquantes:
            print("    L'atelier 2 refusera de tourner tant que ces anomalies ne sont pas corrigées.")
    else:
        print("\n  Atelier 1 validé : identifiants et relations cohérents.")

    pending = session_questions(w2_input)
    if pending:
        print(f"\n  Questions de séance restant à poser au client ({len(pending)}) :")
        for question in pending:
            print(f"    - {question.field_name} : {question.question}")
    else:
        print("\n  Aucune question de séance en attente.")

    if args.json:
        print()
        print(json.dumps(json.loads(w2_input.model_dump_json()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
