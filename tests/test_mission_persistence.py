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


def test_saved_output_is_not_approved_by_default(repo):
    # A workshop that ran but has no auditor decision yet must never read as complete.
    mid = repo.create_mission("M", ["RGPD"])
    repo.save_output(mid, 1, {"x": 1}, status="current")
    latest = repo.latest_output(mid, 1)
    assert latest.status != "approved"


def test_set_version_status_marks_completion_explicitly(repo):
    mid = repo.create_mission("M", ["RGPD"])
    repo.save_output(mid, 1, {"x": 1}, status="current")
    version = repo.latest_output(mid, 1)
    repo.set_version_status(mid, 1, version.version_number, "approved")
    assert repo.latest_output(mid, 1).status == "approved"


def test_rejected_version_is_distinguishable_from_approved(repo):
    mid = repo.create_mission("M", ["RGPD"])
    repo.save_output(mid, 1, {"x": 1}, status="current")
    version = repo.latest_output(mid, 1)
    repo.set_version_status(mid, 1, version.version_number, "rejected")
    latest = repo.latest_output(mid, 1)
    assert latest.status == "rejected"
    assert latest.status != "approved"


def test_token_sink_records_calls_against_the_mission(repo):
    # The sink installed by the CLI routes every LLM call's tokens to the mission.
    from ebios_rm.agent_runtime import set_token_sink

    mid = repo.create_mission("M", ["RGPD"])
    set_token_sink(lambda i, o, model: repo.log_tokens(
        mid, input_tokens=i, output_tokens=o, model_used=model))
    try:
        from ebios_rm import agent_runtime

        class _Metrics:
            input_tokens, output_tokens = 120, 45

        class _Response:
            metrics = _Metrics()
            model = "gemma-test"

        agent_runtime._record_tokens(_Response())
        agent_runtime._record_tokens(_Response())
    finally:
        set_token_sink(None)

    assert repo.token_totals(mid) == {"input_tokens": 240, "output_tokens": 90, "llm_calls": 2}


def test_token_accounting_never_breaks_a_run(repo):
    from ebios_rm import agent_runtime
    from ebios_rm.agent_runtime import set_token_sink

    mid = repo.create_mission("M", ["RGPD"])
    set_token_sink(lambda i, o, m: repo.log_tokens(mid, input_tokens=i, output_tokens=o, model_used=m))
    try:
        agent_runtime._record_tokens(object())        # no metrics attribute
        agent_runtime._record_tokens(None)            # nothing at all
    finally:
        set_token_sink(None)
    assert repo.token_totals(mid)["llm_calls"] == 0   # ignored, no exception
