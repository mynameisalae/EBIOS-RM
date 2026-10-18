"""Every version of an atelier, oldest first — what the audit annex and the interface show (§20.3).

The mission repository only hands out the *latest* version of an atelier. The history is read here,
from the same table, so the shared repository module stays exactly as the rest of the team wrote it.
"""

from __future__ import annotations

import json

from ebios_rm.repositories.mission_repository import MissionRepository, WorkshopVersion


def all_versions(repo: MissionRepository, mission_id: str, workshop_number: int) -> list[WorkshopVersion]:
    rows = repo._conn.execute(  # noqa: SLF001 — read-only query on the repository's own connection
        "SELECT * FROM workshop_versions WHERE mission_id = ? AND workshop_number = ? ORDER BY version_number",
        (mission_id, workshop_number),
    ).fetchall()
    return [
        WorkshopVersion(version_number=r["version_number"], output=json.loads(r["output"]),
                        status=r["status"], created_at=r["created_at"])
        for r in rows
    ]
