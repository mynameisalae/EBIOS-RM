"""Mission state machine (conception §10.2).

A mission's status (missions.status in the mission DB) is always exactly one of
the values named here. next_action() is the whole "brain" of the sequencing: it
reads a status and says what the Orchestrator should do about it. Nothing here
touches the database — this module is pure so it can be unit-tested without a
repository at all.
"""

from __future__ import annotations

from dataclasses import dataclass

WORKSHOP_COUNT = 5


class MissionStatus:
    """Statuses that are not workshop-numbered."""

    CREATED = "created"
    INTAKE = "intake"
    CONTEXT_READY = "context_ready"
    ALL_APPROVED = "all_approved"
    BLOCKED = "blocked"
    COMPLETE = "complete"


def running(n: int) -> str:
    return f"w{n}_running"


def awaiting_approval(n: int) -> str:
    return f"w{n}_awaiting_approval"


def rejected(n: int) -> str:
    return f"w{n}_rejected"


def approved(n: int) -> str:
    return f"w{n}_approved"


def paused(n: int) -> str:
    """A halt (Ctrl+C, external stop) while atelier n was running. Carries the
    workshop number in the status itself, so resuming knows which workshop's
    resume() to call without needing a separate 'restart_from' lookup."""
    return f"w{n}_paused"


def is_paused(status: str) -> bool:
    return status.endswith("_paused")


@dataclass(frozen=True)
class NextAction:
    """What the Orchestrator should do next, and which workshop it concerns (if any)."""

    action: str
    workshop_number: int | None = None


def next_action(status: str) -> NextAction:
    """Dispatch table: mission status -> the single next thing to do.

    Raises ValueError on an unrecognized status rather than guessing — an
    unknown status means something wrote to the mission row outside this
    module's contract, and silently picking a default would hide that bug.
    """
    if status == MissionStatus.CREATED:
        return NextAction("start_intake")
    if status == MissionStatus.INTAKE:
        return NextAction("resume_intake")
    if status == MissionStatus.CONTEXT_READY:
        return NextAction("start_workshop", 1)
    if status == MissionStatus.BLOCKED:
        return NextAction("blocked")
    if status == MissionStatus.ALL_APPROVED:
        return NextAction("generate_report")
    if status == MissionStatus.COMPLETE:
        return NextAction("done")

    for n in range(1, WORKSHOP_COUNT + 1):
        if status == running(n) or status == paused(n):
            return NextAction("resume_workshop", n)
        if status == awaiting_approval(n):
            return NextAction("await_approval", n)
        if status == rejected(n):
            return NextAction("redo_workshop", n)
        if status == approved(n):
            following = n + 1
            if following > WORKSHOP_COUNT:
                return NextAction("generate_report")
            return NextAction("start_workshop", following)

    raise ValueError(f"Unknown mission status: {status!r}")
