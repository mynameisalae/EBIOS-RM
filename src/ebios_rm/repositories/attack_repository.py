"""Read access to the MITRE ATT&CK database — no business logic here (conception §10.1, §12.1, §18).

The base is ``mitre_attack_complete.db`` (ATTACK_DB_PATH), a full ingestion of the
enterprise matrix with its own relational schema. Atelier 4 only needs what a
technique id is checked against: the active techniques, their names and their
tactics, and the version they belong to. Opened read-only — the reference data is
never written during a mission (§12) — so a wrong path fails loudly instead of
silently creating an empty database next to the right one.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

# The enterprise matrix, left to right. The database stores tactics without an
# order, and a catalogue read in kill-chain order is how an attack path is written.
# Tactics the base holds but this list does not know are kept, after these.
TACTIC_ORDER: tuple[str, ...] = (
    "reconnaissance", "resource-development", "initial-access", "execution",
    "persistence", "privilege-escalation", "stealth", "defense-impairment",
    "credential-access", "discovery", "lateral-movement", "collection",
    "command-and-control", "exfiltration", "impact",
)


@dataclass(frozen=True)
class AttackTechnique:
    """One active technique or sub-technique of the base."""

    technique_id: str            # T1566 or T1566.001
    name: str
    tactics: tuple[str, ...]     # tactic shortnames, e.g. ('initial-access',)

    @property
    def parent_id(self) -> str | None:
        return self.technique_id.split(".")[0] if "." in self.technique_id else None


@dataclass(frozen=True)
class AttackCatalogue:
    """Every technique an atelier 4 analysis may cite — the "tool output" of §18 step 23."""

    version: str
    techniques: dict[str, AttackTechnique]

    @property
    def tactics(self) -> list[str]:
        present = {t for tech in self.techniques.values() for t in tech.tactics}
        return [t for t in TACTIC_ORDER if t in present] + sorted(present - set(TACTIC_ORDER))


class AttackRepositoryError(RuntimeError):
    """The ATT&CK base is missing or unreadable — atelier 4 cannot check a single technique id."""


def connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise AttackRepositoryError(f"Base ATT&CK introuvable : {path}")
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)


class AttackRepository:
    """Queries the read-only ATT&CK base."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def version(self) -> str:
        """The ingested release, pinned by content hash — the tag alone reads « Latest »."""
        row = self._conn.execute(
            "SELECT version_tag, sha256_hash FROM attack_version ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return f"{row[0]} (sha256 {row[1][:12]})" if row else "inconnue"

    def catalogue(self) -> AttackCatalogue:
        """Active (neither revoked nor deprecated) techniques with their tactics."""
        try:
            rows = self._conn.execute(
                "SELECT t.id, t.name, ta.shortname FROM techniques t "
                "JOIN technique_tactics tt ON tt.technique_stix_id = t.stix_id "
                "JOIN tactics ta ON ta.id = tt.tactic_id "
                "WHERE t.revoked = 0 AND t.deprecated = 0 ORDER BY t.id"
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise AttackRepositoryError(f"Base ATT&CK illisible : {exc}") from exc
        names: dict[str, str] = {}
        tactics: dict[str, list[str]] = {}
        for technique_id, name, tactic in rows:
            names[technique_id] = name
            tactics.setdefault(technique_id, []).append(tactic)
        return AttackCatalogue(
            version=self.version(),
            techniques={
                tid: AttackTechnique(tid, names[tid], tuple(sorted(
                    tactics[tid], key=lambda t: TACTIC_ORDER.index(t) if t in TACTIC_ORDER else 99)))
                for tid in names
            },
        )
