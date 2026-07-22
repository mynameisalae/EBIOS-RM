"""Two-way clarification — the auditor asks, the agent answers (conception §2).

The system already asks the auditor (follow-ups, flags, contradictions). This
module adds the other direction: the auditor can ask the agent questions about the
mission, and the agent answers **only from the mission context** (and, when
provided, a workshop's output). If the answer is not grounded in the available
facts, the agent says so — it never invents (principe directeur, §2).
"""

from __future__ import annotations

from typing import Callable, Protocol

from pydantic import BaseModel, Field

from ebios_rm.mission_context.mission_context import MissionContext


class ClarificationAnswer(BaseModel):
    """A grounded answer to an auditor's question (conception §2)."""

    answered: bool  # False when the information is not present in the mission context
    answer: str
    based_on_facts: list[str] = Field(default_factory=list)  # field_names / evidence the answer rests on


class ClarificationRunner(Protocol):
    """Answers an auditor question, grounded in the mission context (and optional workshop output)."""

    def answer(
        self,
        question: str,
        mission_context: MissionContext,
        workshop_output: object | None = None,
    ) -> ClarificationAnswer:
        ...


def clarification_repl(
    runner: ClarificationRunner,
    mission_context: MissionContext,
    workshop_output: object | None = None,
    *,
    io_in: Callable[[str], str] = input,
    io_out: Callable[[str], None] = print,
) -> list[tuple[str, ClarificationAnswer]]:
    """Interactive clarification loop. Auditor asks questions until an empty line.

    IO is injectable so the loop is testable without a real terminal. Returns the
    transcript (question, answer) pairs for logging/persistence later (§step 4).
    """
    io_out("\n--- Clarification : posez vos questions à l'agent (Entrée vide pour continuer) ---")
    transcript: list[tuple[str, ClarificationAnswer]] = []
    while True:
        question = io_in("Votre question : ").strip()
        if not question:
            break
        result = runner.answer(question, mission_context, workshop_output)
        transcript.append((question, result))
        if result.answered:
            io_out(f"Réponse : {result.answer}")
            if result.based_on_facts:
                io_out(f"   (fondé sur : {', '.join(result.based_on_facts)})")
        else:
            io_out("L'agent ne peut pas répondre : information absente du contexte de la mission (§2).")
            if result.answer:
                io_out(f"   {result.answer}")
    return transcript
