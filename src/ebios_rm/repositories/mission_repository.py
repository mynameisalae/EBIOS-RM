"""Read-write access to the mission database — no business logic (conception §10.1, §12.6).

Multi-mission: one SQLite file holds every mission (create/list/resume). Stores
each workshop's output as a versioned row (workshop_number 0 = Mission Context,
1..5 = ateliers), the decision trail, and per-mission token/cost. Resume logic and
the rollback cap live in the service layer, not here — this only persists and reads.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "mission_schema.sql"

# Rollback cap (conception §12.6): at most this many versions of one workshop
# before a reinforced confirmation is required. Enforced by the service layer.
ROLLBACK_CAP = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open (creating if needed) the mission DB with the schema applied."""
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    return conn


@dataclass(frozen=True)
class MissionRow:
    mission_id: str
    name: str
    status: str
    created_at: str
    updated_at: str
    frameworks: list[str]


@dataclass(frozen=True)
class WorkshopVersion:
    version_number: int
    output: dict
    status: str
    created_at: str


@dataclass(frozen=True)
class DecisionRow:
    stage: str
    timestamp: str
    decided_by: str
    action_taken: str
    justification_given: str


class MissionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._conn.row_factory = sqlite3.Row

    # --- missions ---

    def create_mission(self, name: str, frameworks: list[str]) -> str:
        mission_id = uuid.uuid4().hex
        now = _now()
        self._conn.execute(
            "INSERT INTO missions (mission_id, name, status, created_at, updated_at, "
            "compliance_frameworks_declared) VALUES (?, ?, ?, ?, ?, ?)",
            (mission_id, name, "in_progress", now, now, json.dumps(frameworks)),
        )
        self._conn.commit()
        return mission_id

    def _to_mission(self, row: sqlite3.Row) -> MissionRow:
        return MissionRow(
            mission_id=row["mission_id"], name=row["name"], status=row["status"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            frameworks=json.loads(row["compliance_frameworks_declared"] or "[]"),
        )

    def get_mission(self, mission_id: str) -> MissionRow | None:
        row = self._conn.execute("SELECT * FROM missions WHERE mission_id = ?", (mission_id,)).fetchone()
        return self._to_mission(row) if row else None

    def list_missions(self) -> list[MissionRow]:
        rows = self._conn.execute("SELECT * FROM missions ORDER BY updated_at DESC").fetchall()
        return [self._to_mission(r) for r in rows]

    def set_status(self, mission_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE missions SET status = ?, updated_at = ? WHERE mission_id = ?",
            (status, _now(), mission_id),
        )
        self._conn.commit()

    # --- workshop versions ---

    def version_count(self, mission_id: str, workshop_number: int) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM workshop_versions WHERE mission_id = ? AND workshop_number = ?",
            (mission_id, workshop_number),
        ).fetchone()[0]

    def save_output(
        self, mission_id: str, workshop_number: int, output: dict, *,
        status: str = "current", overwrite: bool = False,
    ) -> int:
        """Persist a workshop's output; returns its version_number.

        overwrite=True updates the existing current version in place (used by
        mid-intake checkpoints, so a per-answer save does not spawn a new version
        each keystroke). overwrite=False appends a new version and supersedes the
        previous current one, so exactly one current version exists (conception §12.6).
        """
        current = self._conn.execute(
            "SELECT version_number FROM workshop_versions "
            "WHERE mission_id = ? AND workshop_number = ? AND status = 'current' LIMIT 1",
            (mission_id, workshop_number),
        ).fetchone()

        if overwrite and current is not None:
            self._conn.execute(
                "UPDATE workshop_versions SET output = ?, created_at = ? "
                "WHERE mission_id = ? AND workshop_number = ? AND version_number = ?",
                (json.dumps(output), _now(), mission_id, workshop_number, current["version_number"]),
            )
            version_number = current["version_number"]
        else:
            self._conn.execute(
                "UPDATE workshop_versions SET status = 'superseded' "
                "WHERE mission_id = ? AND workshop_number = ? AND status = 'current'",
                (mission_id, workshop_number),
            )
            version_number = self.version_count(mission_id, workshop_number) + 1
            self._conn.execute(
                "INSERT INTO workshop_versions (mission_id, workshop_number, version_number, "
                "output, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (mission_id, workshop_number, version_number, json.dumps(output), status, _now()),
            )
        self._conn.execute("UPDATE missions SET updated_at = ? WHERE mission_id = ?", (_now(), mission_id))
        self._conn.commit()
        return version_number

    def latest_output(self, mission_id: str, workshop_number: int) -> WorkshopVersion | None:
        row = self._conn.execute(
            "SELECT * FROM workshop_versions WHERE mission_id = ? AND workshop_number = ? "
            "ORDER BY version_number DESC LIMIT 1",
            (mission_id, workshop_number),
        ).fetchone()
        if not row:
            return None
        return WorkshopVersion(
            version_number=row["version_number"], output=json.loads(row["output"]),
            status=row["status"], created_at=row["created_at"],
        )

    def set_version_status(self, mission_id: str, workshop_number: int, version_number: int, status: str) -> None:
        self._conn.execute(
            "UPDATE workshop_versions SET status = ? "
            "WHERE mission_id = ? AND workshop_number = ? AND version_number = ?",
            (status, mission_id, workshop_number, version_number),
        )
        self._conn.commit()

    # --- decision log ---

    def log_decision(
        self, mission_id: str, *, stage: str, action: str, justification: str,
        decided_by: str = "auditor", estimated_cost_usd: float | None = None,
        actual_cost_usd: float | None = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO decision_log (mission_id, stage, timestamp, decided_by, action_taken, "
            "justification_given, estimated_cost_usd, actual_cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (mission_id, stage, _now(), decided_by, action, justification,
             estimated_cost_usd, actual_cost_usd),
        )
        self._conn.commit()

    def decisions(self, mission_id: str) -> list[DecisionRow]:
        rows = self._conn.execute(
            "SELECT * FROM decision_log WHERE mission_id = ? ORDER BY id", (mission_id,)
        ).fetchall()
        return [
            DecisionRow(stage=r["stage"], timestamp=r["timestamp"], decided_by=r["decided_by"],
                        action_taken=r["action_taken"], justification_given=r["justification_given"])
            for r in rows
        ]

    # --- token / cost ---

    def log_tokens(
        self, mission_id: str, *, input_tokens: int, output_tokens: int, model_used: str,
        tool_calls: int = 0, wall_clock_seconds: float = 0.0,
    ) -> None:
        self._conn.execute(
            "INSERT INTO cost_calibration_log (mission_id, input_tokens, output_tokens, tool_calls, "
            "wall_clock_seconds, model_used, logged_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (mission_id, input_tokens, output_tokens, tool_calls, wall_clock_seconds, model_used, _now()),
        )
        self._conn.commit()

    def token_totals(self, mission_id: str) -> dict[str, int]:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(input_tokens),0) AS i, COALESCE(SUM(output_tokens),0) AS o, "
            "COUNT(*) AS calls FROM cost_calibration_log WHERE mission_id = ?",
            (mission_id,),
        ).fetchone()
        return {"input_tokens": row["i"], "output_tokens": row["o"], "llm_calls": row["calls"]}
