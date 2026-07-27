"""Token usage per mission (conception §12.6, cost_calibration_log).

    python scripts/mission_tokens.py                 # every mission
    python scripts/mission_tokens.py <mission_id>    # one mission, with its LLM calls
    python scripts/mission_tokens.py --prune         # delete missions with no work in them

Counts tokens only. Money is deliberately reported as 0: pricing depends on the
model and changes over time, so no price table is baked in here — plug one into
estimated_cost_usd / actual_cost_usd when a rate is actually needed.
"""

from __future__ import annotations

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


def _print_one(repo: MissionRepository, mission_id: str) -> int:
    mission = repo.get_mission(mission_id)
    if mission is None:
        print(f"Mission introuvable : {mission_id}")
        return 2
    totals = repo.token_totals(mission_id)
    print(f"Mission   : {mission.name} ({mission_id})")
    print(f"Statut    : {mission.status}")
    print(f"Appels LLM: {totals['llm_calls']}")
    print(f"Tokens    : {totals['input_tokens']} entrée + {totals['output_tokens']} sortie "
          f"= {totals['input_tokens'] + totals['output_tokens']} au total")
    print("Coût      : 0 (aucune tarification configurée)")

    rows = repo._conn.execute(  # noqa: SLF001 — read-only report over the same schema
        "SELECT model_used, COUNT(*) n, SUM(input_tokens) i, SUM(output_tokens) o "
        "FROM cost_calibration_log WHERE mission_id = ? GROUP BY model_used",
        (mission_id,),
    ).fetchall()
    if rows:
        print("\nPar modèle :")
        for r in rows:
            print(f"   {r['model_used']:45}  {r['n']:4} appels  {r['i']:8} in  {r['o']:8} out")
    return 0


def _print_all(repo: MissionRepository) -> int:
    missions = repo.list_missions()
    if not missions:
        print("Aucune mission enregistrée.")
        return 0
    print(f"{'MISSION':34}  {'APPELS':>6}  {'IN':>9}  {'OUT':>9}  {'COÛT':>5}  NOM")
    grand_in = grand_out = grand_calls = 0
    for m in missions:
        t = repo.token_totals(m.mission_id)
        grand_in += t["input_tokens"]
        grand_out += t["output_tokens"]
        grand_calls += t["llm_calls"]
        print(f"{m.mission_id:34}  {t['llm_calls']:6}  {t['input_tokens']:9}  "
              f"{t['output_tokens']:9}  {0:5}  {m.name}")
    print(f"{'TOTAL':34}  {grand_calls:6}  {grand_in:9}  {grand_out:9}  {0:5}")
    return 0


def _prune(repo: MissionRepository) -> int:
    """Delete missions that hold no work at all (mistyped path, aborted before anything ran)."""
    removed = 0
    for m in repo.list_missions():
        has_output = repo.latest_output(m.mission_id, 0) or repo.latest_output(m.mission_id, 1)
        if has_output or repo.token_totals(m.mission_id)["llm_calls"]:
            continue
        repo._conn.execute("DELETE FROM decision_log WHERE mission_id = ?", (m.mission_id,))
        repo._conn.execute("DELETE FROM missions WHERE mission_id = ?", (m.mission_id,))
        removed += 1
        print(f"Supprimée : {m.mission_id}  {m.name}")
    repo._conn.commit()
    print(f"{removed} mission(s) vide(s) supprimée(s).")
    return 0


def main(argv: list[str]) -> int:
    repo = MissionRepository(connect(load_settings().mission_db_path))
    if len(argv) > 1 and argv[1] == "--prune":
        return _prune(repo)
    return _print_one(repo, argv[1]) if len(argv) > 1 else _print_all(repo)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
