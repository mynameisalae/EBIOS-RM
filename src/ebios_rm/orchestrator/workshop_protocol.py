"""The contract every workshop must satisfy to be driven by the Orchestrator
(conception §10.2, §11 companion document).

Deliberately four methods only. The Orchestrator knows nothing about a workshop's
internals (its own agents, retries, clarification loops) — only this interface.
Any object satisfying it, real or a test double, can be plugged in.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class WorkshopRunner(Protocol[TInput, TOutput]):
    """One atelier, seen from the Orchestrator's side."""

    workshop_number: int

    async def run(self, input: TInput, mission_id: str) -> TOutput:
        """Do the work and return the output.

        Raises WorkshopHalted if a stop() signal was honored mid-run, or
        WorkshopBlocked if an external condition prevents completion.
        """
        ...

    def stop(self) -> None:
        """Signal a graceful shutdown. The workshop decides how to save its own
        state; the Orchestrator only asks, it never force-kills."""
        ...

    async def resume(self, mission_id: str) -> TOutput:
        """Resume from whatever the workshop last checkpointed for this mission."""
        ...

    def summarize_output(self, output: TOutput) -> str:
        """A short human-readable summary shown at the validation gate."""
        ...
