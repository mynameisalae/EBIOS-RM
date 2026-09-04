"""The auditor's review loop, shared by the workshop runners (conception §2, §8, §12.6).

Reject -> correct yourself / relaunch the agent / stop, bounded by the rollback
cap, with every decision logged and every version status written. The flow is the
same for every atelier; what differs is the output being reviewed, how it prints,
and how it is regenerated — those are injected.

ponytail: scripts/run_workshop1_from_docs.py still carries its own copy. Its
orchestration is being extracted separately, and rewriting it here would collide
with that work; ateliers 2 and 3 share this one so the copy count stops at two.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ebios_rm.orchestrator import mission_state
from ebios_rm.repositories.mission_repository import MissionRepository
from ebios_rm.workshops.workshop1_cadrage.human_edit import EditError, apply_edit, get_value
from ebios_rm.workshops.workshop1_cadrage.human_interface import approve_workshop, ask_justification

Ask = Callable[[str], str]
Say = Callable[[str], None]


def ask_choice(question: str, options: dict[str, str], io_in: Ask = input, io_out: Say = print) -> str:
    while True:
        io_out(f"\n{question}")
        for key, label in options.items():
            io_out(f"   [{key}] {label}")
        answer = io_in("> ").strip().casefold()
        if answer in options:
            return answer
        io_out(f"    Réponse attendue : {', '.join(options)}.")


def ask_blocks(labels: dict[str, tuple[str, str]], io_in: Ask = input, io_out: Say = print) -> set[str]:
    """Which parts of the output to regenerate — the rest is kept verbatim (§12.6)."""
    io_out("\nQuelles parties faut-il refaire ? (numéros séparés par des virgules, vide = tout)")
    for key, (_, label) in labels.items():
        io_out(f"   [{key}] {label}")
    while True:
        answer = io_in("> ").strip()
        if not answer:
            return {block for block, _ in labels.values()}
        keys = [k.strip() for k in answer.split(",") if k.strip()]
        if keys and all(k in labels for k in keys):
            return {labels[k][0] for k in keys}
        io_out(f"    Réponse attendue : {', '.join(labels)} (ou vide pour tout refaire).")


def ask_ids(question: str, known: set[str], io_in: Ask = input, io_out: Say = print) -> list[str]:
    """A list of ids the auditor picks from ``known`` — empty answer means none."""
    while True:
        raw = io_in(f"{question} ").strip()
        if not raw:
            return []
        picked = [p.strip().upper() for p in raw.replace(";", ",").split(",") if p.strip()]
        unknown = [p for p in picked if p not in known]
        if not unknown:
            return picked
        io_out(f"    Identifiant inconnu : {', '.join(unknown)}.")


def prior_rejection_reasons(repo: MissionRepository, mission_id: str, stage: str) -> list[str]:
    """Reject reasons already logged for this stage, so a redo carries the full feedback.

    Read back from the decision log rather than kept in memory: a mission resumed
    in a new process must hand the agent every reason it has been given, not only
    the ones from this run.
    """
    return [d.justification_given for d in repo.decisions(mission_id)
            if d.stage == stage and d.action_taken == "rejected"]


def interrupted(label: str, resume_command: str) -> int:
    """Ctrl+C, or a model that cannot answer: everything saved so far is a version.

    Stopping is a normal way out — the auditor may have nothing to rule on today —
    so say how to come back instead of dumping a traceback.
    """
    print(f"\n\n{label.capitalize()} mis en pause — la dernière version enregistrée est conservée.")
    print(f"  Pour reprendre :  {resume_command}")
    return 130  # conventional exit code for SIGINT


def quality_errors(output: Any) -> list[Any]:
    """The blocking quality-check failures of an output, if it carries a report at all."""
    report = getattr(output, "quality_report", None)
    return list(getattr(report, "erreurs", []) or [])


def quality_override(output: Any, io_in: Ask = input, io_out: Say = print) -> bool:
    """A quality error blocks approval unless the auditor overrides it explicitly (§14, §19).

    Without this the checker is decorative: the erreurs print above the same two
    keystrokes as a clean run, and get approved past.
    """
    errors = quality_errors(output)
    if not errors:
        return True
    io_out("\n=== Contrôle qualité EN ERREUR — approbation bloquée (§14) ===")
    for check in errors:
        io_out(f"   XX {check.controle} : {check.message}")
    io_out("Corrigez ces points (rejet puis reprise, ou correction manuelle).")
    io_out("Tapez CONFIRMER pour approuver malgré tout, toute autre saisie pour refuser.")
    return io_in("> ").strip() == "CONFIRMER"


@dataclass
class ApprovalLoop:
    """Review one workshop's output until it is approved, corrected, or set aside.

    ``rerun(notes, blocks, previous)`` regenerates the output — ``blocks`` is None
    for a workshop with nothing to redo partially. ``save`` persists a corrected
    version. ``model_cls`` re-validates an edited output before it is saved, so a
    hand-typed value that breaks the schema is refused at the prompt rather than
    at the next load.
    """

    repo: MissionRepository
    mission_id: str
    stage: str
    workshop_number: int
    label: str                                   # « l'atelier 2 », shown to the auditor
    print_output: Callable[[Any], None]
    rerun: Callable[[list[str], set[str] | None, Any], Any]
    save: Callable[[Any], None]
    model_cls: Any
    edit_examples: str = ""
    block_labels: dict[str, tuple[str, str]] | None = None
    io_in: Ask = input
    io_out: Say = print

    # --- pieces ---

    def prior_rejection_reasons(self) -> list[str]:
        return prior_rejection_reasons(self.repo, self.mission_id, self.stage)

    def _status(self, suffix: str) -> str:
        return f"w{self.workshop_number}_{suffix}"

    def review_and_approve(self, output: Any) -> tuple[bool, str]:
        self.print_output(output)
        version = self.repo.latest_output(self.mission_id, self.workshop_number)
        if quality_override(output, self.io_in, self.io_out):
            approved, reason = approve_workshop(self.label, io_in=self.io_in, io_out=self.io_out)
        else:
            approved, reason = False, "Contrôle qualité en erreur, non levé par l'auditeur"

        action = "approved" if approved else "rejected"
        self.repo.log_decision(
            self.mission_id, stage=self.stage, action=action,
            justification="Approuvé par l'auditeur" if approved else reason,
        )
        self.repo.set_status(self.mission_id, self._status("approved" if approved else "rejected"))
        if version:
            self.repo.set_version_status(
                self.mission_id, self.workshop_number, version.version_number, action)
        if approved:
            totals = self.repo.token_totals(self.mission_id)
            self.io_out(f"{self.label.capitalize()} approuvé. Mission {self.mission_id} sauvegardée.")
            self.io_out(f"Tokens consommés : {totals['input_tokens']} entrée / "
                        f"{totals['output_tokens']} sortie sur {totals['llm_calls']} appels.")
        else:
            self.io_out(f"{self.label.capitalize()} non approuvé : {reason}")
        return approved, reason

    def edit(self, output: Any) -> Any:
        """Let the auditor correct values directly, each with a mandatory justification (§2, §8)."""
        data = output.model_dump(mode="json")
        changed = False
        self.io_out("\n=== Correction manuelle ===")
        self.io_out("Indiquez le chemin du champ à corriger, par exemple :")
        self.io_out(f"   {self.edit_examples}")
        self.io_out("Entrée vide pour terminer.")

        while True:
            path = self.io_in("Chemin : ").strip()
            if not path:
                break
            try:
                current = get_value(data, path)
            except EditError as exc:
                self.io_out(f"   {exc}")
                continue
            self.io_out(f"   Valeur actuelle : {current!r}")
            new_raw = self.io_in("   Nouvelle valeur : ").strip()
            if not new_raw:
                self.io_out("   Annulé.")
                continue
            reason = ask_justification("   Justification (obligatoire, §8) : ", self.io_in, self.io_out)
            try:
                edited = apply_edit(data, path, new_raw, justification=reason)
                self.model_cls.model_validate(edited)
            except (EditError, ValueError) as exc:
                self.io_out(f"   {str(exc)[:200]}")
                continue
            data = edited
            self.repo.log_decision(self.mission_id, stage=self.stage,
                                   action=f"edited:{path}", justification=reason)
            self.io_out("   Modification enregistrée.")
            changed = True

        if not changed:
            return output
        corrected = self.model_cls.model_validate(data)
        self.save(corrected)
        self.repo.set_status(self.mission_id, self._status("awaiting_approval"))
        self.io_out("Version corrigée sauvegardée.")
        return corrected

    def reinforced_confirm(self) -> bool:
        """Rollback cap reached (§12.6) — require an explicit typed confirmation to go further."""
        self.io_out(f"\nPlafond de {mission_state.ROLLBACK_CAP} versions atteint pour "
                    f"{self.label} (§12.6).")
        self.io_out("Une nouvelle reprise est inhabituelle. Tapez CONFIRMER pour relancer malgré tout,")
        self.io_out("ou toute autre saisie pour arrêter et conserver la dernière version.")
        return self.io_in("> ").strip() == "CONFIRMER"

    # --- the loop ---

    def run(self, output: Any) -> int:
        """Review, and on rejection loop into correction or redo (§12.6). Returns an exit code."""
        while True:
            approved, _reason = self.review_and_approve(output)
            if approved:
                return 0

            choice = ask_choice(
                "Que voulez-vous faire ?",
                {"c": "corriger vous-même un ou plusieurs champs",
                 "r": "relancer l'agent en tenant compte du motif",
                 "q": "en rester là (dernière version conservée, non approuvée)"},
                self.io_in, self.io_out,
            )
            if choice == "q":
                self.io_out("Dernière version conservée (non approuvée).")
                return 1
            if choice == "c":
                output = self.edit(output)
                continue

            if (not mission_state.can_redo(self.repo, self.mission_id, self.workshop_number)
                    and not self.reinforced_confirm()):
                self.io_out("Dernière version conservée (non approuvée).")
                return 1

            blocks = ask_blocks(self.block_labels, self.io_in, self.io_out) if self.block_labels else None
            notes = self.prior_rejection_reasons()  # includes the reason just logged
            output = self.rerun(notes, blocks, output)
