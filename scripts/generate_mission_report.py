"""Generate the mission report of a mission (conception §20.1, §20.2) — one model call per section.

    python scripts/generate_mission_report.py <mission_id>                   # data/reports/rapport_mission_<id>.docx
    python scripts/generate_mission_report.py <mission_id> chemin/sortie.docx

Reads approved atelier outputs only. Every statement the model writes must cite the
mission fields it rests on; those that do not hold up are left out of the document and
listed here with the reason. Needs OPENROUTER_API_KEY (.env) and costs a few model calls.
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

from ebios_rm.agent_runtime import StructuredCallFailed, set_token_sink  # noqa: E402
from ebios_rm.config import load_settings  # noqa: E402
from ebios_rm.repositories.mission_repository import MissionRepository, connect  # noqa: E402
from ebios_rm.reporting.mission_report import (  # noqa: E402
    build_snapshot, write_mission_report, write_mission_report_file,
)
from ebios_rm.reporting.report_agent import AgnoReportRunner  # noqa: E402

REPORTS_DIR = Path("data/reports")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    settings = load_settings()
    if not settings.openrouter_api_key:
        print("OPENROUTER_API_KEY is not set — put it in .env before running.")
        return 2

    mission_id = argv[1]
    repo = MissionRepository(connect(settings.mission_db_path))
    if repo.get_mission(mission_id) is None:
        print(f"Mission introuvable : {mission_id}")
        return 2
    set_token_sink(lambda inp, out, model: repo.log_tokens(
        mission_id, input_tokens=inp, output_tokens=out, model_used=model))

    snapshot = build_snapshot(repo, mission_id)
    print(f"Modèle : {settings.model_id}  (OpenRouter)")
    print(f"Ateliers approuvés lus : {', '.join(map(str, snapshot.approved)) or 'aucun'}")
    for n, reason in snapshot.not_approved.items():
        print(f"   atelier {n} non lu — {reason}")

    try:
        report = write_mission_report(snapshot, AgnoReportRunner())
    except StructuredCallFailed as exc:
        print(f"\nLe modèle n'a pas pu rédiger une section : {exc}")
        return 1

    target = Path(argv[2]) if len(argv) > 2 else REPORTS_DIR / f"rapport_mission_{mission_id[:8]}.docx"
    path = write_mission_report_file(report, target)

    kept = sum(len(s.statements) for s in report.sections)
    print(f"\nRapport de mission écrit : {path}")
    print(f"  {len(report.sections)} section(s) · {kept} affirmation(s) retenue(s) "
          f"(dont {report.corrected} après correction) · {len(report.rejected)} écartée(s) · "
          f"{len(report.skipped)} section(s) non incluse(s)")
    for skipped in report.skipped:
        print(f"  non incluse : {skipped.title} — {skipped.reason}")
    for item in report.rejected:
        print(f"  écartée [{item.section}] {item.text[:90]!r}\n      -> {item.reason}")
    totals = repo.token_totals(mission_id)
    print(f"Tokens (cumul mission) : {totals['input_tokens']} entrée / {totals['output_tokens']} sortie "
          f"sur {totals['llm_calls']} appel(s).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(130) from None
