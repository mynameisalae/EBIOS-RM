"""Orchestrator.run_mission() end to end, against fake workshops — no LLM, no
stdin, no dependency on Workshop 2's real implementation (conception §10.2).

Proves the loop: build input -> run -> save -> validation gate -> next atelier,
plus the reject/redo path, the rollback cap (§12.6), and halt/resume.
"""

from __future__ import annotations

import pytest

from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.orchestrator import mission_state, state_machine
from ebios_rm.orchestrator.orchestrator import Orchestrator
from ebios_rm.orchestrator.signals import WorkshopBlocked
from ebios_rm.repositories.mission_repository import MissionRepository, connect
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from orchestrator_fakes import FakeWorkshopRunner, ScriptedApproval, ScriptedReinforcedConfirm, always_approve


@pytest.fixture
def repo():
    conn = connect(":memory:")
    yield MissionRepository(conn)
    conn.close()


def _context_ready_mission(repo: MissionRepository) -> str:
    mid = repo.create_mission("Mission Test", ["RGPD"])
    ctx = MissionContext(
        organisation_nom="Org Test", secteur_activite="Santé", applicable_frameworks=["RGPD"],
        facts=[Fact.declaration("hebergement", "hybride")],
    )
    mission_state.save_mission_context(repo, mid, ctx)
    repo.set_status(mid, state_machine.MissionStatus.CONTEXT_READY)
    return mid


# --- approve path ---


@pytest.mark.asyncio
async def test_approves_through_both_registered_workshops(repo):
    mid = _context_ready_mission(repo)
    w1 = FakeWorkshopRunner(1, output=Workshop1Output())
    w2 = FakeWorkshopRunner(2)
    orch = Orchestrator(repo, {1: w1, 2: w2}, approve=always_approve)

    await orch.run_mission(mid)

    assert repo.get_mission(mid).status == state_machine.approved(2)
    assert len(w1.run_calls) == 1
    assert len(w2.run_calls) == 1


async def test_stops_cleanly_when_next_workshop_is_not_registered(repo):
    mid = _context_ready_mission(repo)
    w1 = FakeWorkshopRunner(1, output=Workshop1Output())
    # Only atelier 1 registered — matches today's real situation.
    orch = Orchestrator(repo, {1: w1}, approve=always_approve)

    await orch.run_mission(mid)

    assert repo.get_mission(mid).status == state_machine.approved(1)


async def test_workshop2_receives_the_narrow_input_built_from_workshop1_output(repo):
    mid = _context_ready_mission(repo)
    w1_output = Workshop1Output()
    w1 = FakeWorkshopRunner(1, output=w1_output)
    w2 = FakeWorkshopRunner(2)
    orch = Orchestrator(repo, {1: w1, 2: w2}, approve=always_approve)

    await orch.run_mission(mid)

    from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Input

    assert len(w2.run_calls) == 1
    received_input, received_mission_id = w2.run_calls[0]
    assert isinstance(received_input, Workshop2Input)
    assert received_mission_id == mid


async def test_approval_and_rejection_are_journaled(repo):
    mid = _context_ready_mission(repo)
    w1 = FakeWorkshopRunner(1, output=Workshop1Output())
    orch = Orchestrator(repo, {1: w1}, approve=always_approve)

    await orch.run_mission(mid)

    decisions = repo.decisions(mid)
    approved_decisions = [d for d in decisions if d.stage == "w1" and d.action_taken == "approved"]
    assert len(approved_decisions) == 1


# --- reject then redo ---


async def test_rejected_workshop_is_redone_and_then_approved(repo):
    mid = _context_ready_mission(repo)
    w1 = FakeWorkshopRunner(1, output=Workshop1Output())
    w2 = FakeWorkshopRunner(2)
    approval = ScriptedApproval([(True, ""), (False, "Pertinence mal évaluée"), (True, "")])
    orch = Orchestrator(repo, {1: w1, 2: w2}, approve=approval)

    await orch.run_mission(mid)

    assert repo.get_mission(mid).status == state_machine.approved(2)
    assert len(w2.run_calls) == 2  # first attempt + redo
    assert repo.version_count(mid, mission_state.WORKSHOP_2) == 2

    decisions = [d for d in repo.decisions(mid) if d.stage == "w2"]
    assert decisions[0].action_taken == "rejected"
    assert decisions[0].justification_given == "Pertinence mal évaluée"
    assert decisions[1].action_taken == "approved"


async def test_rejection_requires_a_reason_to_be_journaled(repo):
    """A rejection with an empty reason is nonsensical (§8) — the scripted
    approve callback here always supplies one, exercising that the Orchestrator
    passes it through to the decision log rather than dropping it."""
    mid = _context_ready_mission(repo)
    w1 = FakeWorkshopRunner(1, output=Workshop1Output())
    approval = ScriptedApproval([(False, "motif de test"), (True, "")])
    orch = Orchestrator(repo, {1: w1}, approve=approval)

    await orch.run_mission(mid)

    rejected = [d for d in repo.decisions(mid) if d.action_taken == "rejected"]
    assert rejected[0].justification_given == "motif de test"


# --- rollback cap (§12.6) ---


async def test_rollback_cap_reached_and_declined_force_accepts_last_version(repo):
    mid = _context_ready_mission(repo)
    w1 = FakeWorkshopRunner(1, output=Workshop1Output())
    w2 = FakeWorkshopRunner(2)
    # approve w1, then reject w2 three times (fills the cap), no fourth run.
    approval = ScriptedApproval([(True, ""), (False, "r1"), (False, "r2"), (False, "r3")])
    reinforced = ScriptedReinforcedConfirm([False])
    orch = Orchestrator(repo, {1: w1, 2: w2}, approve=approval, reinforced_confirm=reinforced)

    await orch.run_mission(mid)

    assert len(w2.run_calls) == 3  # capped at ROLLBACK_CAP, no 4th run
    assert repo.get_mission(mid).status == state_machine.approved(2)
    forced = [d for d in repo.decisions(mid) if d.action_taken == "force_accepted"]
    assert len(forced) == 1


async def test_rollback_cap_reached_and_confirmed_allows_one_more_redo(repo):
    mid = _context_ready_mission(repo)
    w1 = FakeWorkshopRunner(1, output=Workshop1Output())
    w2 = FakeWorkshopRunner(2)
    approval = ScriptedApproval([(True, ""), (False, "r1"), (False, "r2"), (False, "r3"), (True, "")])
    reinforced = ScriptedReinforcedConfirm([True])
    orch = Orchestrator(repo, {1: w1, 2: w2}, approve=approval, reinforced_confirm=reinforced)

    await orch.run_mission(mid)

    assert len(w2.run_calls) == 4  # the confirmed extra redo actually ran
    assert repo.get_mission(mid).status == state_machine.approved(2)
    assert reinforced.calls == ["Atelier 2"]


# --- halt / resume ---


async def test_workshop_halted_pauses_the_mission(repo):
    mid = _context_ready_mission(repo)
    w1 = FakeWorkshopRunner(1, output=Workshop1Output())
    w2 = FakeWorkshopRunner(2)
    w2.halt_on_run = True
    orch = Orchestrator(repo, {1: w1, 2: w2}, approve=always_approve)

    await orch.run_mission(mid)

    assert repo.get_mission(mid).status == state_machine.paused(2)
    paused_decisions = [d for d in repo.decisions(mid) if d.action_taken == "paused"]
    assert len(paused_decisions) == 1


async def test_resuming_a_paused_mission_calls_resume_not_run(repo):
    mid = _context_ready_mission(repo)
    w1 = FakeWorkshopRunner(1, output=Workshop1Output())
    w2 = FakeWorkshopRunner(2)
    w2.halt_on_run = True
    orch = Orchestrator(repo, {1: w1, 2: w2}, approve=always_approve)

    await orch.run_mission(mid)  # pauses mid-atelier-2
    assert repo.get_mission(mid).status == state_machine.paused(2)

    await orch.run_mission(mid)  # simulates the CLI relaunched with --resume

    assert repo.get_mission(mid).status == state_machine.approved(2)
    assert w2.resume_calls == [mid]
    assert len(w2.run_calls) == 1  # the halted attempt only; resume() took over from there


async def test_halt_before_any_workshop_starts_pauses_the_first_one(repo):
    mid = _context_ready_mission(repo)
    w1 = FakeWorkshopRunner(1, output=Workshop1Output())
    w2 = FakeWorkshopRunner(2)
    orch = Orchestrator(repo, {1: w1, 2: w2}, approve=always_approve)
    orch.halt()  # signaled before run_mission is even called — stops at the very next atelier

    await orch.run_mission(mid)

    assert repo.get_mission(mid).status == state_machine.paused(1)
    assert w1.run_calls == []  # never started
    assert w2.run_calls == []  # never reached


def test_halt_calls_stop_on_the_active_workshop(repo):
    mid = _context_ready_mission(repo)
    w2 = FakeWorkshopRunner(2)
    orch = Orchestrator(repo, {2: w2}, approve=always_approve)
    orch._active_workshop_number = 2  # simulates "atelier 2 is mid-run"

    orch.halt()

    assert w2.stop_requested is True
    assert orch._halt_requested is True


# --- blocked ---


async def test_workshop_blocked_stops_the_mission_with_a_reason(repo):
    mid = _context_ready_mission(repo)
    w1 = FakeWorkshopRunner(1, output=Workshop1Output())
    w1.block_reason = "Référentiel RGPD non chargé"
    orch = Orchestrator(repo, {1: w1}, approve=always_approve)

    await orch.run_mission(mid)

    assert repo.get_mission(mid).status == state_machine.MissionStatus.BLOCKED
    blocked = [d for d in repo.decisions(mid) if d.action_taken == "blocked"]
    assert blocked[0].justification_given == "Référentiel RGPD non chargé"


def test_workshop_blocked_requires_a_non_empty_reason():
    with pytest.raises(ValueError):
        WorkshopBlocked("")
