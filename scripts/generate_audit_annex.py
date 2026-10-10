"""Generate the audit annex of a mission (conception §20.1, §20.3) — no model call, no cost.

    python scripts/generate_audit_annex.py <mission_id>                   # data/reports/annexe_audit_<id>.docx
    python scripts/generate_audit_annex.py <mission_id> chemin/sortie.docx

List the missions and their ids with:  python scripts/run_workshop1_from_docs.py --list
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
from ebios_rm.reporting.audit_annex import collect_audit_annex_data, write_audit_annex  # noqa: E402

REPORTS_DIR = Path("data/reports")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    mission_id = argv[1]
    repo = MissionRepository(connect(load_settings().mission_db_path))
    if repo.get_mission(mission_id) is None:
        print(f"Mission introuvable : {mission_id}")
        return 2

    data = collect_audit_annex_data(repo, mission_id)
    target = Path(argv[2]) if len(argv) > 2 else REPORTS_DIR / f"annexe_audit_{mission_id[:8]}.docx"
    path = write_audit_annex(data, target)

    print(f"Annexe d'audit écrite : {path}")
    print(f"  {len(data.versions)} version(s) d'atelier · {len(data.decisions)} décision(s) · "
          f"{len(data.gaps)} lien(s) écart/contrôle · {len(data.abnormal_events)} événement(s) anormal(aux)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(130) from None
