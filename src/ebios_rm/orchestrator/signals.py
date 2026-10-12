"""Orchestrator-level interruption signals (conception §10.2).

A workshop raises one of these to hand control back to the Orchestrator instead
of deciding for itself what happens to the mission. Neither is an error in the
usual sense: WorkshopHalted means "asked to stop, stopped cleanly"; WorkshopBlocked
means "cannot proceed without something outside the workshop's control."
"""

from __future__ import annotations


class WorkshopHalted(Exception):
    """Raised by a workshop after it has honored a stop() signal and saved its state.

    The Orchestrator catches this, marks the mission 'paused', and returns —
    it is not a failure, it is confirmation that the graceful shutdown happened.
    """


class WorkshopBlocked(Exception):
    """Raised by a workshop when it cannot continue for a reason outside its control
    (e.g. a declared framework has no controls loaded). Carries the reason so the
    Orchestrator can journal it and the auditor can act on it (conception §8: no
    silent stop without a reason)."""

    def __init__(self, reason: str) -> None:
        if not reason:
            raise ValueError("WorkshopBlocked requires a non-empty reason (§8)")
        super().__init__(reason)
        self.reason = reason
