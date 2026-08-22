"""next_action() for every mission status (conception §10.2)."""

import pytest

from ebios_rm.orchestrator import state_machine as sm


def test_created_starts_intake():
    assert sm.next_action(sm.MissionStatus.CREATED) == sm.NextAction("start_intake")


def test_intake_resumes_intake():
    assert sm.next_action(sm.MissionStatus.INTAKE) == sm.NextAction("resume_intake")


def test_context_ready_starts_atelier_1():
    assert sm.next_action(sm.MissionStatus.CONTEXT_READY) == sm.NextAction("start_workshop", 1)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_running_resumes_that_workshop(n):
    assert sm.next_action(sm.running(n)) == sm.NextAction("resume_workshop", n)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_paused_resumes_that_workshop(n):
    assert sm.next_action(sm.paused(n)) == sm.NextAction("resume_workshop", n)
    assert sm.is_paused(sm.paused(n))


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_awaiting_approval_opens_gate(n):
    assert sm.next_action(sm.awaiting_approval(n)) == sm.NextAction("await_approval", n)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_rejected_redoes_that_workshop(n):
    assert sm.next_action(sm.rejected(n)) == sm.NextAction("redo_workshop", n)


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_approved_starts_next_workshop(n):
    assert sm.next_action(sm.approved(n)) == sm.NextAction("start_workshop", n + 1)


def test_atelier_5_approved_triggers_reporting():
    assert sm.next_action(sm.approved(5)) == sm.NextAction("generate_report")


def test_all_approved_triggers_reporting():
    assert sm.next_action(sm.MissionStatus.ALL_APPROVED) == sm.NextAction("generate_report")


def test_blocked_stops():
    assert sm.next_action(sm.MissionStatus.BLOCKED) == sm.NextAction("blocked")


def test_complete_is_done():
    assert sm.next_action(sm.MissionStatus.COMPLETE) == sm.NextAction("done")


def test_unknown_status_raises():
    with pytest.raises(ValueError, match="Unknown mission status"):
        sm.next_action("some_typo_status")


def test_status_helpers_are_workshop_numbered():
    assert sm.running(2) == "w2_running"
    assert sm.awaiting_approval(3) == "w3_awaiting_approval"
    assert sm.rejected(4) == "w4_rejected"
    assert sm.approved(5) == "w5_approved"
    assert sm.paused(1) == "w1_paused"


def test_is_paused_false_for_non_paused_status():
    assert not sm.is_paused(sm.running(2))
    assert not sm.is_paused(sm.MissionStatus.BLOCKED)
