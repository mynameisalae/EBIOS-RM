"""Mission persistence — multi-mission save/resume + decision log (conception §12, §12.6)."""

import pytest

from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.orchestrator import mission_state
from ebios_rm.repositories.mission_repository import ROLLBACK_CAP, MissionRepository, connect


@pytest.fixture
def repo():
    conn = connect(":memory:")
    yield MissionRepository(conn)
    conn.close()


def _context(name="Clinique Test"):
    return MissionContext(
        organisation_nom=name, secteur_activite="Santé", applicable_frameworks=["RGPD"],
        facts=[Fact.declaration("hebergement", "hybride")],
    )


def test_create_list_and_get_mission(repo):
    a = repo.create_mission("Mission A", ["RGPD"])
    b = repo.create_mission("Mission B", ["ISO27001", "NIST"])
    ids = {m.mission_id for m in repo.list_missions()}
    assert {a, b} == ids
    assert repo.get_mission(b).frameworks == ["ISO27001", "NIST"]
    assert repo.get_mission("nope") is None


def test_mission_context_roundtrips(repo):
    mid = repo.create_mission("M", ["RGPD"])
    mission_state.save_mission_context(repo, mid, _context())
    loaded = mission_state.load_mission_context(repo, mid)
    assert loaded is not None
    assert loaded.organisation_nom == "Clinique Test"
    assert loaded.value("hebergement") == "hybride"


def test_two_missions_are_isolated(repo):
    a = repo.create_mission("A", ["RGPD"])
    b = repo.create_mission("B", ["RGPD"])
    mission_state.save_mission_context(repo, a, _context("Org A"))
    mission_state.save_mission_context(repo, b, _context("Org B"))
    assert mission_state.load_mission_context(repo, a).organisation_nom == "Org A"
    assert mission_state.load_mission_context(repo, b).organisation_nom == "Org B"


def test_saving_new_version_supersedes_the_previous_current(repo):
    mid = repo.create_mission("M", ["RGPD"])
    repo.save_output(mid, 1, {"v": 1}, status="current")
    repo.save_output(mid, 1, {"v": 2}, status="current")
    latest = repo.latest_output(mid, 1)
    assert latest.version_number == 2 and latest.output == {"v": 2} and latest.status == "current"
    assert repo.version_count(mid, 1) == 2


def test_decision_log_records_reasons(repo):
    mid = repo.create_mission("M", ["RGPD"])
    repo.log_decision(mid, stage="workshop_1", action="rejected", justification="scénarios incomplets")
    rows = repo.decisions(mid)
    assert len(rows) == 1
    assert rows[0].action_taken == "rejected"
    assert rows[0].justification_given == "scénarios incomplets"


def test_rollback_cap(repo):
    mid = repo.create_mission("M", ["RGPD"])
    for _ in range(ROLLBACK_CAP):
        assert mission_state.can_redo(repo, mid, 1)
        repo.save_output(mid, 1, {"x": 1})
    assert not mission_state.can_redo(repo, mid, 1)  # cap reached (§12.6)


def test_token_totals_sum_per_mission(repo):
    mid = repo.create_mission("M", ["RGPD"])
    repo.log_tokens(mid, input_tokens=100, output_tokens=40, model_used="gemma")
    repo.log_tokens(mid, input_tokens=50, output_tokens=10, model_used="gemma")
    totals = repo.token_totals(mid)
    assert totals == {"input_tokens": 150, "output_tokens": 50, "llm_calls": 2}


def test_persists_across_reconnect(tmp_path):
    db = tmp_path / "mission.db"
    conn = connect(db)
    mid = MissionRepository(conn).create_mission("Persisted", ["RGPD"])
    mission_state.save_mission_context(MissionRepository(conn), mid, _context("Survivor"))
    conn.close()

    conn2 = connect(db)  # reopen the file — simulates stop then --resume
    loaded = mission_state.load_mission_context(MissionRepository(conn2), mid)
    assert loaded.organisation_nom == "Survivor"
    conn2.close()
