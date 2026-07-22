"""reference-db-loader — builds the reference database (conception §13.3, §12.5).

Applies reference_schema.sql, then discovers every framework plugin
(plugins.registry) and inserts its controls.json into baseline_controls. Adding
a law or standard means adding a plugin folder — this loader never hardcodes a
framework name.

ATT&CK loading (attack_techniques/mitigations/groups) is a separate concern used
by workshops 2/4/5 and is out of scope for Workshop 1; it plugs in here later.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ebios_rm.config import load_settings
from ebios_rm.plugins.registry import discover_frameworks

SCHEMA_PATH = Path(__file__).parent / "reference_schema.sql"

_CONTROL_COLUMNS = (
    "control_id",
    "framework",
    "description",
    "category",
    "covers_risk_category",
    "framework_version",
    "legal_impact_type",
    "legal_impact_details",
)


def _insert_controls(conn: sqlite3.Connection, controls: list[dict], source: str) -> int:
    inserted = 0
    for c in controls:
        row = (
            c["control_id"],
            c["framework"],
            c["description"],
            c["category"],
            json.dumps(c.get("covers_risk_category", [])),
            c["framework_version"],
            c.get("legal_impact_type"),
            c.get("legal_impact_details"),
        )
        try:
            conn.execute(
                f"INSERT INTO baseline_controls ({', '.join(_CONTROL_COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in _CONTROL_COLUMNS)})",
                row,
            )
            inserted += 1
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Duplicate control_id '{c['control_id']}' while loading {source}"
            ) from exc
    return inserted


def build_reference_db(
    db_path: str | Path,
    *,
    extra_controls: list[dict] | None = None,
) -> sqlite3.Connection:
    """Create (or rebuild) the reference DB and return an open connection.

    ``extra_controls`` lets local dev inject a clearly-labelled sample control
    set (see data/dev_seed/) without touching the real plugin folders, which stay
    empty until verified/licensed referential text is added.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    for plugin in discover_frameworks():
        _insert_controls(conn, plugin.controls, source=f"plugin:{plugin.id}")
    if extra_controls:
        _insert_controls(conn, extra_controls, source="extra_controls")

    conn.commit()
    return conn


def main() -> None:
    settings = load_settings()
    conn = build_reference_db(settings.reference_db_path)
    count = conn.execute("SELECT COUNT(*) FROM baseline_controls").fetchone()[0]
    conn.close()
    print(f"Reference DB built at {settings.reference_db_path} — {count} baseline controls loaded.")


if __name__ == "__main__":
    main()
