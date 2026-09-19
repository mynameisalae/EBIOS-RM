"""Read access to the MITRE ATT&CK database — no business logic here (conception §10.1, §12.1, §18, §19).

The base is ``mitre_attack_complete.db`` (ATTACK_DB_PATH), a full ingestion of the
enterprise matrix with its own relational schema. Atelier 4 only needs what a
technique id is checked against: the active techniques, their names and their
tactics, and the version they belong to. Atelier 5 needs one more thing: the real
mitigations a technique has, via the ``mitigates`` relationship — what
``get_mitigations_for_technique`` (toolkits/attack_toolkit.py) returns to the agent,
and what assessment.py checks a proposed ``mitigation_ids_attck`` against afterwards
(same id, same relation, so a tool call and its later verification can never disagree).
Opened read-only — the reference data is never written during a mission (§12) — so a
wrong path fails loudly instead of silently creating an empty database next to the
right one.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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


@dataclass(frozen=True)
class Mitigation:
    """One active mitigation of the base (course-of-action), as it mitigates
    one specific technique — the same pairing get_mitigations_for_technique
    returns to the agent and MitigationCatalogue.ids_for checks against."""

    mitigation_id: str  # M1032, never a T-prefixed legacy id (those are deprecated, excluded)
    name: str


@dataclass(frozen=True)
class MitigationCatalogue:
    """Real mitigations for a fixed set of techniques — built once per mission from
    every technique atelier 4 actually cited, so the tool call an atelier 5 sub-agent
    makes and the check assessment.py runs afterwards read the exact same data (§19)."""

    by_technique: dict[str, tuple[Mitigation, ...]]

    def ids_for(self, technique_id: str) -> frozenset[str]:
        return frozenset(m.mitigation_id for m in self.by_technique.get(technique_id, ()))

    @property
    def all_ids(self) -> frozenset[str]:
        return frozenset(m.mitigation_id for ms in self.by_technique.values() for m in ms)


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

    def mitigations_for(self, technique_id: str) -> tuple[Mitigation, ...]:
        """Real, active (neither revoked nor deprecated) mitigations of one technique,
        via the base's own ``mitigates`` relationship — the single source both the
        live tool call and the later check read from (conception §19)."""
        try:
            rows = self._conn.execute(
                "SELECT m.id, m.name FROM relationships r "
                "JOIN mitigations m ON m.stix_id = r.source_ref "
                "JOIN techniques t ON t.stix_id = r.target_ref "
                "WHERE r.relationship_type = 'mitigates' AND t.id = ? "
                "AND m.revoked = 0 AND m.deprecated = 0 ORDER BY m.id",
                (technique_id,),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise AttackRepositoryError(f"Base ATT&CK illisible : {exc}") from exc
        return tuple(Mitigation(mid, name) for mid, name in rows)

    def mitigation_catalogue(self, technique_ids: Iterable[str]) -> MitigationCatalogue:
        """Real mitigations for exactly the techniques given — built once from
        every technique atelier 4 cited, reused by the tool and by assessment.py."""
        ids = sorted({tid for tid in technique_ids if tid})
        return MitigationCatalogue({tid: self.mitigations_for(tid) for tid in ids})
