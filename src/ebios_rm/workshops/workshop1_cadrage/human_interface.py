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


# A "skip reason" this long is usually the answer itself, typed one prompt too late —
# observed live, and it silently loses real audit information: the text is logged as a
# justification and never becomes a Fact. Above this length, confirm before skipping.
ANSWER_LIKE_REASON_CHARS = 80


def is_meaningful(text: str) -> bool:
    """A justification must actually be one (§8).

    "Motif du skip : :::::" and "Motif du retrait : 8" are non-empty yet say nothing;
    they satisfy the letter of §8 while emptying it of content. Noise rejection only —
    two alphanumeric characters are enough, this is not a content check.
    """
    return sum(1 for c in text if c.isalnum()) >= 2


def ask_justification(prompt: str, io_in: Callable[[str], str] = input,
                      io_out: Callable[[str], None] = print) -> str:
    """Re-prompt until the auditor gives a real reason (§8)."""
    while True:
        reason = io_in(prompt).strip()
        if is_meaningful(reason):
            return reason
        io_out("    Un motif non vide est obligatoire (§8) — indiquez la raison.")


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

    def _say(self, text: str) -> None:
        print(text)

    def _skip_outcome(self, reason: str) -> str | SkipRequested:
        """Finalise a skip — unless the "reason" reads like the answer itself.

        The auditor types 'skip', is asked why, and pastes a full technical answer
        there. Committing to the skip then throws that information away, while they
        believe they answered. Ask instead of guessing (§2).
        """
        if len(reason) < ANSWER_LIKE_REASON_CHARS:
            return SkipRequested(reason)
        while True:
            keep = self._prompt("    Cela ressemble à une réponse — l'enregistrer comme réponse ? [oui/non] : ")
            if keep.casefold() in {"o", "oui", "y", "yes"}:
                return reason
            if keep.casefold() in {"n", "non", "no"}:
                return SkipRequested(reason)
            # No default: guessing here either discards a real answer or records a
            # skip motive as one. Both are silent, so the choice must be explicit (§2).
            self._say("    Répondez 'oui' ou 'non' — une décision explicite est requise (§2).")

    def _accept_free_value(self, contradiction: Contradiction, typed: str) -> object | None:
        """A hand-typed contradiction resolution. Taken as-is here; checked by the
        conversational subclass. None means 'not accepted, ask again'."""
        return typed

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
                if is_meaningful(reason):
                    return self._skip_outcome(reason)
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
                value = self._accept_free_value(contradiction, choice)
                if value is not None:
                    return value
                continue
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


def approve_workshop(
    label: str,
    *,
    io_in: Callable[[str], str] = input,
    io_out: Callable[[str], None] = print,
) -> tuple[bool, str]:
    """Final human gate on a workshop result (conception §2, §8).

    The auditor has the last word on the whole atelier, not only field by field.
    A rejection requires a non-empty reason. Returns (approved, reason).

    ponytail: decision is returned, not persisted — writing it to workshop_versions
    (approved/superseded) and redoing the workshop on reject needs mission
    persistence, which is not built yet.
    """
    io_out(f"\n=== Validation de {label} ===")
    while True:
        choice = io_in("Approuvez-vous ce résultat ? [oui / non] : ").strip().casefold()
        if choice in {"oui", "o", "yes", "y"}:
            return True, ""
        if choice in {"non", "n", "no"}:
            reason = ask_justification("Motif du refus (obligatoire, §8) : ", io_in, io_out)
            io_out(f"Résultat NON APPROUVÉ — motif enregistré : {reason}")
            io_out("La reprise de l'atelier nécessitera la persistance de mission (à venir).")
            return False, reason
        io_out("    Répondez 'oui' ou 'non' — une décision explicite est requise (§2).")


class ConversationalHumanInterface(CLIHumanInterface):
    """Follow-ups become a real conversation: the auditor can answer, ask, or push
    back in free text, and an agent decides what they meant each turn (conception §2).

    Follow-ups and flag review are conversational; confirmations and contradictions
    keep the plain CLI behaviour.
    """

    # Dialogue turns kept across questions so the agent knows what was already
    # discussed. Capped: a long raw transcript bloats the prompt and makes the
    # model paraphrase past turns loosely. Facts themselves come from self._facts,
    # never from this transcript.
    HISTORY_TURNS = 10

    # After this many consecutive non-answers on one question, tell the auditor
    # about the '!' override so the agent can never trap them in a loop.
    MAX_PUSHBACKS = 3

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
        self._history: list[dict] = []

    # The orchestration binds the growing fact list so the agent has live context.
    def bind_facts(self, facts: list[Fact]) -> None:
        self._facts = facts

    def _prompt(self, text: str) -> str:  # keep parent's confirm/contradiction/flag prompts working
        return self._in(text)

    def _say(self, text: str) -> None:
        self._out(text)

    def _converse(self, question: str, explanation: str, user: str) -> tuple[bool, str]:
        """One agent turn. Returns (is_answer, captured_value). Records into session history.

        Intent is read from the model's own classification (TurnResult.intent), not
        inferred from the reply text.
        """
        turn = self._runner.handle_turn(
            question, explanation, user, self._facts, self._history[-self.HISTORY_TURNS:]
        )
        self._history.append({"role": "auditeur", "content": user})
        self._history.append({"role": "agent", "content": turn.reply, "intent": turn.intent})
        if turn.reply:
            self._out(f"Agent : {turn.reply}")
        return turn.is_answer, (turn.answer or user)

    def _nudge(self, pushbacks: int) -> int:
        """Count one turn that did not answer; at the threshold, advertise the '!' override.

        Blank presses and conversational non-answers share this counter: they are the
        same dead end for the auditor, so they must offer the same way out (§2).
        """
        pushbacks += 1
        if pushbacks == self.MAX_PUSHBACKS:
            self._out("    (bloqué ? préfixez '!' pour enregistrer votre réponse telle quelle)")
        return pushbacks

    def _accept_free_value(self, contradiction: Contradiction, typed: str) -> object | None:
        """Plausibility-check a hand-typed resolution, as ingestion checks what it reads (§11).

        Anything non-empty used to be accepted verbatim: an accidental paste of a file
        path became the authoritative value of organisation_nom. '!' still forces a
        value through — the auditor outranks the agent (§2).
        """
        if typed.startswith("!"):
            return typed[1:].strip() or None
        extraction = contradiction.extraction
        is_answer, value = self._converse(
            f"Quelle est la valeur correcte pour « {contradiction.field_name} » ?",
            f"Valeurs en conflit : {contradiction.declaration.value!r} (formulaire) "
            f"vs {extraction.value!r} ({extraction.source_document}).",
            typed,
        )
        return value if is_answer else None

    def ask_followup(self, question: FollowUpQuestion) -> str | SkipRequested:
        tag = "CRITIQUE (bloquant)" if question.blocking else "IMPORTANT"
        self._out(f"\n[{tag}] {question.question}")
        if question.help_text:
            self._out(f"    ↳ {question.help_text}")
        hint = "posez une question / demandez une clarification"
        if not question.blocking:
            hint += ", ou tapez 'skip' pour passer"
        self._out(f"    (répondez, {hint})")

        pushbacks = 0
        while True:
            user = self._in("> ")
            # A blank line is never a decision: skipping is an explicit act that must
            # be typed, so a stray Enter cannot start abandoning a question (§8). It is
            # still a non-answer, so it counts toward the same pushback budget — 30
            # blank Enters in a row on a blocking question found no way out otherwise.
            if not user:
                if question.blocking:
                    self._out("    Information bloquante — une réponse est requise (§7).")
                else:
                    self._out("    Répondez, ou tapez 'skip' pour passer cette question.")
                pushbacks = self._nudge(pushbacks)
                continue
            if user.lower() == "skip":
                if question.blocking:
                    self._out("    Question bloquante : elle ne peut pas être passée (§7).")
                    continue
                reason = self._in("Motif du skip (obligatoire, §8) : ")
                if is_meaningful(reason):
                    return self._skip_outcome(reason)
                self._out("    Un motif non vide est obligatoire pour passer (§8).")
                continue
            # Escape hatch: the auditor always outranks the agent (§2). Without this,
            # a model that keeps asking for detail traps a CRITICAL question forever,
            # since blank re-prompts and skip is forbidden.
            if user.startswith("!"):
                forced = user[1:].strip()
                if forced:
                    self._out("    Réponse enregistrée telle quelle, à votre demande.")
                    return forced
                continue

            is_answer, value = self._converse(question.question, question.help_text, user)
            if is_answer:
                return value
            pushbacks = self._nudge(pushbacks)

    def review_flag(self, flag: AnswerFlag) -> object | None:
        label = "INCOHÉRENTE" if flag.kind == "implausible" else "À CLARIFIER"
        self._out(f"\n[RÉPONSE {label}] Question : {flag.question}")
        self._out(f"    Réponse fournie : {flag.answer!r}")
        self._out(f"    Signalement de l'agent : {flag.reason}")
        self._out("    (corrigez, posez une question, [Entrée] pour conserver, 'skip' pour écarter)")

        while True:
            user = self._in("> ")
            if not user:
                return flag.answer
            if user.lower() == "skip":
                return None
            is_answer, value = self._converse(
                flag.question, f"Réponse actuelle jugée {flag.kind} : {flag.reason}", user
            )
            if is_answer:
                return value
