"""Reject -> redo loop control flow, bounded by the rollback cap (phase B, conception §12.6).

Loads the CLI module and stubs the two LLM-backed steps (_run_workshop,
_review_and_approve) so the loop's branching — redo on reject, cap then reinforced
confirmation — is exercised without any model call.
"""

import importlib.util
from pathlib import Path

import pytest

from ebios_rm.orchestrator import mission_state
from ebios_rm.repositories.mission_repository import ROLLBACK_CAP, MissionRepository, connect

_CLI_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_workshop1_from_docs.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("cli_docs", _CLI_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cli():
    return _load_cli()


@pytest.fixture
def repo():
    conn = connect(":memory:")
    yield MissionRepository(conn)
    conn.close()


def _stub_run_workshop(cli, repo, mission_id):
    """Mimic a real run: save a new version (so the cap counter grows), return a marker output."""
    def run(_repo, _mid, _mc, _ref, revision_notes=None, blocks=None, previous=None):
        repo.save_output(mission_id, mission_state.WORKSHOP_1, {"note_count": len(revision_notes or [])})
        return object()
    cli._run_workshop = run


def test_reject_twice_then_approve_runs_three_times(cli, repo, monkeypatch):
    mid = repo.create_mission("M", ["RGPD"])
    runs = {"n": 0}

    def run(_repo, _mid, _mc, _ref, revision_notes=None, blocks=None, previous=None):
        runs["n"] += 1
        repo.save_output(mid, mission_state.WORKSHOP_1, {})
        return object()

    verdicts = iter([(False, "trop vague"), (False, "gravité"), (True, "")])
    monkeypatch.setattr(cli, "_run_workshop", run)
    monkeypatch.setattr(cli, "_review_and_approve", lambda *a: next(verdicts))
    monkeypatch.setattr(cli, "_ask_choice", lambda *a, **k: "r")  # always choose: rerun the agent
    monkeypatch.setattr(cli, "_ask_blocks", lambda *a, **k: None)  # redo everything
    monkeypatch.setattr(cli, "_consolidate_gaps", lambda _r, _m, out, **k: out)
    monkeypatch.setattr(cli, "_review_unverified", lambda *a, **k: None)

    first = cli._run_workshop(repo, mid, None, None)
    rc = cli._approval_loop(repo, mid, None, None, first)
    assert rc == 0
    assert runs["n"] == 3  # initial + 2 redos


def test_cap_then_declining_reinforced_confirm_stops(cli, repo, monkeypatch):
    mid = repo.create_mission("M", ["RGPD"])
    runs = {"n": 0}

    def run(_repo, _mid, _mc, _ref, revision_notes=None, blocks=None, previous=None):
        runs["n"] += 1
        repo.save_output(mid, mission_state.WORKSHOP_1, {})
        return object()

    monkeypatch.setattr(cli, "_run_workshop", run)
    monkeypatch.setattr(cli, "_review_and_approve", lambda *a: (False, "toujours rejeté"))
    monkeypatch.setattr(cli, "_ask_choice", lambda *a, **k: "r")  # always choose: rerun the agent
    monkeypatch.setattr(cli, "_ask_blocks", lambda *a, **k: None)  # redo everything
    monkeypatch.setattr(cli, "_consolidate_gaps", lambda _r, _m, out, **k: out)
    monkeypatch.setattr(cli, "_review_unverified", lambda *a, **k: None)          # always wants another redo
    monkeypatch.setattr(cli, "_reinforced_confirm", lambda *a, **k: False)  # but declines past the cap

    first = cli._run_workshop(repo, mid, None, None)
    rc = cli._approval_loop(repo, mid, None, None, first)
    assert rc == 1
    assert runs["n"] == ROLLBACK_CAP  # never exceeds the cap without reinforced confirmation


def test_reinforced_confirm_allows_going_past_the_cap(cli, repo, monkeypatch):
    mid = repo.create_mission("M", ["RGPD"])
    runs = {"n": 0}

    def run(_repo, _mid, _mc, _ref, revision_notes=None, blocks=None, previous=None):
        runs["n"] += 1
        repo.save_output(mid, mission_state.WORKSHOP_1, {})
        return object()

    # reject until run 5, then approve
    verdicts = iter([(False, "x")] * 4 + [(True, "")])
    monkeypatch.setattr(cli, "_run_workshop", run)
    monkeypatch.setattr(cli, "_review_and_approve", lambda *a: next(verdicts))
    monkeypatch.setattr(cli, "_ask_choice", lambda *a, **k: "r")  # always choose: rerun the agent
    monkeypatch.setattr(cli, "_ask_blocks", lambda *a, **k: None)  # redo everything
    monkeypatch.setattr(cli, "_consolidate_gaps", lambda _r, _m, out, **k: out)
    monkeypatch.setattr(cli, "_review_unverified", lambda *a, **k: None)
    monkeypatch.setattr(cli, "_reinforced_confirm", lambda *a, **k: True)  # confirm past the cap

    first = cli._run_workshop(repo, mid, None, None)
    rc = cli._approval_loop(repo, mid, None, None, first)
    assert rc == 0
    assert runs["n"] == 5  # cap did not block once reinforced confirmation was given


def test_redo_notes_accumulate_from_the_decision_log(cli, repo, monkeypatch):
    # Reasons are reloaded from the log, so a redo carries them even after --resume.
    mid = repo.create_mission("M", ["RGPD"])
    seen: list[list[str]] = []

    def run(_repo, _mid, _mc, _ref, revision_notes=None, blocks=None, previous=None):
        seen.append(list(revision_notes or []))
        repo.save_output(mid, mission_state.WORKSHOP_1, {})
        return object()

    def review(_repo, _mid, _mc, _out):
        reasons = ["motif A", "motif B"]
        idx = len(seen) - 1
        if idx < len(reasons):
            repo.log_decision(mid, stage="workshop_1", action="rejected", justification=reasons[idx])
            return False, reasons[idx]
        return True, ""

    monkeypatch.setattr(cli, "_run_workshop", run)
    monkeypatch.setattr(cli, "_review_and_approve", review)
    monkeypatch.setattr(cli, "_ask_choice", lambda *a, **k: "r")  # always choose: rerun the agent
    monkeypatch.setattr(cli, "_ask_blocks", lambda *a, **k: None)  # redo everything
    monkeypatch.setattr(cli, "_consolidate_gaps", lambda _r, _m, out, **k: out)
    monkeypatch.setattr(cli, "_review_unverified", lambda *a, **k: None)

    first = cli._run_workshop(repo, mid, None, None, cli._prior_rejection_reasons(repo, mid))
    assert cli._approval_loop(repo, mid, None, None, first) == 0
    assert seen[0] == []                          # first run: no prior feedback
    assert seen[1] == ["motif A"]                 # redo 1 carries the first rejection
    assert seen[2] == ["motif A", "motif B"]      # redo 2 carries both
