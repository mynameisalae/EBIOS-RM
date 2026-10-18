"""Put saved atelier results (the resultat_atelierN.json files) into a mission, so the interface and the
two reports can read them.

    python scripts/import_mission_outputs.py --db data/mission/demo.db --name mondial_rempli \\
        --organisation "Mondial-Tickets" --secteur "Billetterie" \\
        --w1 a1.json --w2 a2.json --w3 a3.json --w4 a4.json --w5 a5.json

Only the ateliers you give are imported. Each one is saved as approved: the files are
results the team already validated, and the reports read approved versions only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ebios_rm.repositories.mission_repository import MissionRepository, connect  # noqa: E402


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="mission database to write into (created if needed)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--organisation", default="")
    parser.add_argument("--secteur", default="")
    for n in range(1, 6):
        parser.add_argument(f"--w{n}", help=f"atelier {n} result (JSON)")
    args = parser.parse_args()

    repo = MissionRepository(connect(args.db))
    mission_id = repo.create_mission(args.name, [])
    if args.organisation:
        repo.save_output(mission_id, 0, {"organisation_nom": args.organisation, "secteur_activite": args.secteur,
                                         "applicable_frameworks": [], "facts": []})
    imported = []
    for n in range(1, 6):
        path = getattr(args, f"w{n}")
        if not path:
            continue
        output = _load(path)
        version = repo.save_output(mission_id, n, output)
        repo.set_version_status(mission_id, n, version, "approved")
        if n == 4 and output.get("attck_version"):
            repo.set_attck_version(mission_id, output["attck_version"])
        imported.append(n)
    print(f"Mission {mission_id} ({args.name}) : ateliers importés {imported or 'aucun'} dans {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
