"""Where the auditor decides — every human decision point routes through here.

The AI proposes; the auditor disposes (principe directeur, §2). Follow-up
questions (§7), simple confirmations of document-only facts (§11), and
contradiction resolutions (§11) are never delegated to the LLM — they are asked
through this interface so the last word is always human, and so the whole
orchestration is testable with a scripted implementation.

A Skip/Reject always requires a non-empty justification (§8); the CLI
implementation re-prompts until it gets one.
"""

from __future__ import annotations

from typing import Callable, Protocol

from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.conversation import ConversationRunner
from ebios_rm.mission_context.ingestion import AnswerFlag
from ebios_rm.mission_context.priority_matrix import FollowUpQuestion
from ebios_rm.mission_context.validation import Contradiction


class SkipRequested(Exception):
    """Raised/returned when the auditor skips an Important question, carrying the mandatory reason (§8)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class HumanInterface(Protocol):
    """The auditor-decision boundary (conception §2, §7, §8, §11)."""

    def ask_followup(self, question: FollowUpQuestion) -> str | SkipRequested:
        """Ask a missing-field question. Critical questions cannot be skipped; Important ones
        may be skipped only with a non-empty justification (returns SkipRequested)."""
        ...

    def confirm_document_only(self, field_name: str, value: object, source_quote: str) -> bool:
        """Confirm a value found only in a supplied document (simple yes/no, §11)."""
        ...

    def resolve_contradiction(self, contradiction: Contradiction) -> object:
        """Resolve a contradiction by choosing/entering the authoritative value (§11).
        Never resolved automatically — this call is the resolution."""
        ...

    def review_flag(self, flag: AnswerFlag) -> object | None:
        """Rule on an answer the agent flagged as implausible/unclear (conception §2).
        Return the value to keep (the original, or a correction), or None to discard it."""
        ...


class CLIHumanInterface:
    """Terminal implementation for dev testing — the auditor answers on stdin.

    Run this from a real terminal (`python -m ...` / the dev runner); it reads
    from stdin, which is unavailable in non-interactive automation.
    """

    def _prompt(self, text: str) -> str:
        return input(text).strip()

    def ask_followup(self, question: FollowUpQuestion) -> str | SkipRequested:
        tag = "CRITIQUE (bloquant)" if question.blocking else "IMPORTANT"
        print(f"\n[{tag}] {question.question}")
        if question.help_text:
            print(f"    ↳ {question.help_text}")
        while True:
            if question.blocking:
                answer = self._prompt("Réponse (obligatoire) : ")
                if answer:
                    return answer
                print("    Cette information est bloquante — une réponse est requise (§7).")
            else:
                answer = self._prompt("Réponse (ou tapez 'skip') : ")
                if answer.lower() != "skip":
                    return answer
                reason = self._prompt("Motif du skip (obligatoire, §8) : ")
                if reason:
                    return SkipRequested(reason)
                print("    Un motif non vide est obligatoire pour passer (§8).")

    def confirm_document_only(self, field_name: str, value: object, source_quote: str) -> bool:
        print(f"\n[CONFIRMATION] Le document indique pour « {field_name} » : {value!r}")
        print(f'    Extrait source : "{source_quote}"')
        return self._prompt("Confirmer cette valeur ? [o/N] : ").lower() in {"o", "oui", "y", "yes"}

    def resolve_contradiction(self, contradiction: Contradiction) -> object:
        print(f"\n[CONTRADICTION] Champ « {contradiction.field_name} » — résolution humaine obligatoire (§11)")
        print(f"    [1] Formulaire (déclaration) : {contradiction.declaration.value!r}")
        extr = contradiction.extraction
        print(f"    [2] Document ({extr.source_document}) : {extr.value!r}")
        print(f'        Extrait source : "{extr.source_quote}"')
        while True:
            choice = self._prompt("Choix [1] / [2] / (saisir une autre valeur) : ")
            if choice == "1":
                return contradiction.declaration.value
            if choice == "2":
                return contradiction.extraction.value
            if choice:
                return choice
            print("    Une décision explicite est requise — la mission ne peut avancer sans elle (§11).")

    def review_flag(self, flag: AnswerFlag) -> object | None:
        label = "INCOHÉRENTE" if flag.kind == "implausible" else "À CLARIFIER"
        print(f"\n[RÉPONSE {label}] Question : {flag.question}")
        print(f"    Réponse fournie : {flag.answer!r}")
        print(f"    Signalement de l'agent : {flag.reason}")
        answer = self._prompt("Conserver telle quelle [Entrée], corriger (saisir), ou 'skip' pour écarter : ")
        if not answer:
            return flag.answer
        if answer.lower() == "skip":
            return None
        return answer


class ConversationalHumanInterface(CLIHumanInterface):
    """Follow-ups become a real conversation: the auditor can answer, ask, or push
    back in free text, and an agent decides what they meant each turn (conception §2).

    Only ask_followup is made conversational (that is where a static form hurts);
    confirmations, contradictions, and flag review keep the plain CLI behaviour.
    """

    def __init__(
        self,
        runner: ConversationRunner,
        *,
        io_in: Callable[[str], str] = input,
        io_out: Callable[[str], None] = print,
    ) -> None:
        self._runner = runner
        self._in = lambda text: io_in(text).strip()
        self._out = io_out
        self._facts: list[Fact] = []

    # The orchestration binds the growing fact list so the agent has live context.
    def bind_facts(self, facts: list[Fact]) -> None:
        self._facts = facts

    def _prompt(self, text: str) -> str:  # keep parent's confirm/contradiction/flag prompts working
        return self._in(text)

    def ask_followup(self, question: FollowUpQuestion) -> str | SkipRequested:
        tag = "CRITIQUE (bloquant)" if question.blocking else "IMPORTANT"
        self._out(f"\n[{tag}] {question.question}")
        if question.help_text:
            self._out(f"    ↳ {question.help_text}")
        self._out("    (répondez, ou posez une question / demandez une clarification)")

        history: list[dict] = []
        while True:
            user = self._in("> ")
            if not user:
                if question.blocking:
                    self._out("    Information bloquante — une réponse est requise (§7).")
                    continue
                reason = self._in("Motif du skip (obligatoire, §8) : ")
                if reason:
                    return SkipRequested(reason)
                continue
            if user.lower() == "skip" and not question.blocking:
                reason = self._in("Motif du skip (obligatoire, §8) : ")
                if reason:
                    return SkipRequested(reason)
                continue

            turn = self._runner.handle_turn(
                question.question, question.help_text, user, self._facts, history
            )
            history.append({"role": "auditeur", "content": user})
            history.append({"role": "agent", "content": turn.reply, "is_answer": turn.is_answer})
            if turn.reply:
                self._out(f"Agent : {turn.reply}")
            if turn.is_answer:
                return turn.answer or user
            # It was a question/clarification/off-topic — keep the conversation going.
