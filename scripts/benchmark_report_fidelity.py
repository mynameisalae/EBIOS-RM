"""Measure what the report's anti-hallucination check catches, on a mission's approved data. No model, no cost.

    python scripts/benchmark_report_fidelity.py                      # first mission of MISSION_DB_PATH
    python scripts/benchmark_report_fidelity.py --db autre.db --mission <id> --out data/reports/fidelite.md

Builds sentences whose truth is known (exact ones the check must accept, corrupted ones it must refuse),
runs them through the same check as the report, and prints the rates. One category is a known limit on
purpose: swapping before/after inside a single cited object, which the check cannot see.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ebios_rm.config import load_settings  # noqa: E402
from ebios_rm.repositories.mission_repository import MissionRepository, connect  # noqa: E402
from ebios_rm.reporting import fidelity  # noqa: E402
from ebios_rm.reporting.mission_report import build_snapshot  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", help="mission database (default: MISSION_DB_PATH)")
    parser.add_argument("--mission", help="mission id (default: the most recent)")
    parser.add_argument("--out", help="also write the table (Markdown) to this file")
    args = parser.parse_args()

    repo = MissionRepository(connect(args.db or load_settings().mission_db_path))
    mission_id = args.mission or (repo.list_missions()[0].mission_id if repo.list_missions() else None)
    if mission_id is None:
        print("Aucune mission dans cette base.")
        return 2
    snapshot = build_snapshot(repo, mission_id)
    if not snapshot.approved:
        print("Aucun atelier approuvé : rien à mesurer.")
        return 2
    rows = fidelity.run(snapshot.state)
    table = fidelity.to_markdown(rows)
    print(f"Mission {mission_id} — ateliers approuvés : {', '.join(map(str, snapshot.approved))}\n")
    print(table)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(table + "\n", encoding="utf-8")
        print(f"\nTable écrite : {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
