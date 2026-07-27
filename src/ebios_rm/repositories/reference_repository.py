"""Read access to the reference database — no business logic here (conception §10.1, §12.1).

All access is relational and by identifier; there is no vector store anywhere (§12).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineControl:
    """One row of baseline_controls (conception §12.1, §12.3)."""

    control_id: str
    framework: str
    description: str
    category: str
    covers_risk_category: list[str]
    framework_version: str
    legal_impact_type: str | None
    legal_impact_details: str | None

    @property
    def is_legal_provision(self) -> bool:
        """A purely-legal provision (e.g. RGPD Art. 83) — excluded from the workshop 4 filter (§12.3)."""
        return self.legal_impact_type is not None


def _row_to_control(row: sqlite3.Row) -> BaselineControl:
    return BaselineControl(
        control_id=row["control_id"],
        framework=row["framework"],
        description=row["description"],
        category=row["category"],
        covers_risk_category=json.loads(row["covers_risk_category"] or "[]"),
        framework_version=row["framework_version"],
        legal_impact_type=row["legal_impact_type"],
        legal_impact_details=row["legal_impact_details"],
    )


class ReferenceRepository:
    """Queries the read-only reference DB (baseline_controls, ATT&CK tables)."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._conn.row_factory = sqlite3.Row

    def get_baseline_controls(self, framework: str) -> list[BaselineControl]:
        """All control rows for a declared framework (conception §15 step 1)."""
        # Case-insensitive: the framework name comes from a human-filled questionnaire,
        # so "rgpd" and "RGPD" must reach the same controls rather than silently
        # matching nothing (which would read as an unloaded framework).
        cur = self._conn.execute(
            "SELECT * FROM baseline_controls WHERE framework = ? COLLATE NOCASE ORDER BY control_id",
            (framework,),
        )
        return [_row_to_control(r) for r in cur.fetchall()]

    def get_legal_impact_provisions(self, applicable_frameworks: list[str]) -> list[BaselineControl]:
        """Provisions with a non-null legal_impact_type across all declared frameworks (conception §12.3, §15.1).

        Never limited to a hardcoded framework — a new dual-nature referential
        (another national law, a sector regulation) is picked up automatically.
        """
        if not applicable_frameworks:
            return []
        placeholders = ",".join("? COLLATE NOCASE" for _ in applicable_frameworks)
        cur = self._conn.execute(
            f"SELECT * FROM baseline_controls "
            f"WHERE legal_impact_type IS NOT NULL AND framework IN ({placeholders}) "
            f"ORDER BY control_id",
            tuple(applicable_frameworks),
        )
        return [_row_to_control(r) for r in cur.fetchall()]
