"""Test doubles for the Orchestrator — a scripted WorkshopRunner and a scripted
approval callback, so the full run_mission() loop runs deterministically without
any LLM, any real workshop, or stdin."""

from __future__ import annotations

from pydantic import BaseModel

from ebios_rm.orchestrator.signals import WorkshopBlocked, WorkshopHalted


class FakeOutput(BaseModel):
    """A minimal stand-in output for whichever atelier is under test."""

    note: str = "ok"


class FakeWorkshopRunner:
    """A WorkshopRunner that returns a canned output — no LLM, no agents.

    Set halt_on_run / block_reason before calling run_mission() to make the
    next run() call raise WorkshopHalted / WorkshopBlocked instead of succeeding,
    to exercise the Orchestrator's pause and blocked paths.
    """

    def __init__(self, workshop_number: int, *, output: BaseModel | None = None) -> None:
        self.workshop_number = workshop_number
        self._output = output or FakeOutput(note=f"atelier {workshop_number} output")
        self.halt_on_run = False
        self.block_reason: str | None = None
        self.stop_requested = False
        self.run_calls: list[tuple[object, str]] = []
        self.resume_calls: list[str] = []

    async def run(self, input: object, mission_id: str) -> BaseModel:
        self.run_calls.append((input, mission_id))
        if self.block_reason is not None:
            raise WorkshopBlocked(self.block_reason)
        if self.halt_on_run:
            self.halt_on_run = False  # one-shot: resume() should succeed afterwards
            raise WorkshopHalted()
        return self._output

    def stop(self) -> None:
        self.stop_requested = True

    async def resume(self, mission_id: str) -> BaseModel:
        self.resume_calls.append(mission_id)
        return self._output

    def summarize_output(self, output: BaseModel) -> str:
        return f"Résumé factice atelier {self.workshop_number} : {output!r}"


class ScriptedApproval:
    """A scripted stand-in for approve_workshop: pops (approved, reason) pairs
    in order. Raises if the script runs out, so a test can't silently pass
    on more approval calls than it expected."""

    def __init__(self, decisions: list[tuple[bool, str]]) -> None:
        self._decisions = list(decisions)
        self.calls: list[str] = []

    def __call__(self, label: str) -> tuple[bool, str]:
        self.calls.append(label)
        if not self._decisions:
            raise AssertionError(f"ScriptedApproval ran out of decisions (label={label!r})")
        return self._decisions.pop(0)


def always_approve(label: str) -> tuple[bool, str]:
    return True, ""


class ScriptedReinforcedConfirm:
    """A scripted stand-in for the rollback-cap confirmation prompt."""

    def __init__(self, decisions: list[bool]) -> None:
        self._decisions = list(decisions)
        self.calls: list[str] = []

    def __call__(self, label: str) -> bool:
        self.calls.append(label)
        if not self._decisions:
            raise AssertionError(f"ScriptedReinforcedConfirm ran out of decisions (label={label!r})")
        return self._decisions.pop(0)
