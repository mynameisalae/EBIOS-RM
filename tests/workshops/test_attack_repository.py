"""AttackRepository's mitigation lookup, against the real committed database
(conception §19).

Unlike ReferenceRepository's tests, this does not build a small in-memory
fixture: the MITRE enterprise matrix is a large, stable, already-committed
asset (mitre_attack_complete.db at the repo root) rather than referential
text the project authors and edits itself, so there is no fixed dev seed to
build from. These tests pin facts about the real, committed release instead
— if a future re-ingestion changes what mitigates T1078, one of these fails
and says so, rather than a downstream atelier 5 test failing for an
unrelated reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ebios_rm.repositories.attack_repository import AttackRepository, connect_readonly

DB_PATH = Path(__file__).resolve().parents[2] / "mitre_attack_complete.db"


@pytest.fixture
def attack_repo() -> AttackRepository:
    conn = connect_readonly(DB_PATH)
    try:
        yield AttackRepository(conn)
    finally:
        conn.close()


def test_mitigations_for_a_real_technique(attack_repo):
    mitigations = attack_repo.mitigations_for("T1078")
    ids = {m.mitigation_id for m in mitigations}
    assert "M1032" in ids  # Multi-factor Authentication
    assert all(m.mitigation_id.startswith("M") for m in mitigations)  # no legacy T-prefixed ids


def test_mitigations_for_an_unknown_technique_is_empty(attack_repo):
    assert attack_repo.mitigations_for("T9999.999") == ()


def test_mitigation_catalogue_covers_exactly_the_given_techniques(attack_repo):
    catalogue = attack_repo.mitigation_catalogue(["T1078", "T1486"])
    assert set(catalogue.by_technique) == {"T1078", "T1486"}
    assert "M1032" in catalogue.ids_for("T1078")
    assert catalogue.ids_for("T9999.999") == frozenset()


def test_mitigation_catalogue_all_ids_is_the_union(attack_repo):
    catalogue = attack_repo.mitigation_catalogue(["T1078", "T1486"])
    assert catalogue.all_ids == catalogue.ids_for("T1078") | catalogue.ids_for("T1486")


def test_mitigation_catalogue_ignores_empty_and_duplicate_ids(attack_repo):
    catalogue = attack_repo.mitigation_catalogue(["T1078", "T1078", "", None])
    assert set(catalogue.by_technique) == {"T1078"}
