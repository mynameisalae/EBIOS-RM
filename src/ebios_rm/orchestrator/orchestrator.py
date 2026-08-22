"""The Orchestrator — coordinates the five workshops (conception §10.2).

Workshop N -> Mission State -> Orchestrator -> Workshop N+1.
Never a direct call from one workshop to the next. This is what gives, with
no extra mechanism: pause/resume at any point, replay of a single workshop,
version history, and insertion of human validation points without ever
touching a workshop's code.

The Orchestrator does no cybersecurity reasoning itself. It reads the mission's
status, decides what happens next via state_machine.next_action, builds the
next workshop's narrow typed input (conception §9), runs it, persists its
output, and opens the human validation gate. Everything else — how a workshop
reasons, retries, or converses with the auditor mid-atelier — is internal to
that workshop and invisible here.

Intake (the questionnaire/document phase that produces the Mission Context) is
not driven by this class yet. It still runs through the existing CLI flow
(scripts/run_workshop1_from_docs.py) and must have already brought the mission
to 'context_ready' before run_mission() is called.
"""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel

from ebios_rm.orchestrator import mission_state, state_machine
from ebios_rm.orchestrator.input_adapters import build_workshop2_input
from ebios_rm.orchestrator.mission_state import can_redo
from ebios_rm.orchestrator.signals import WorkshopBlocked, WorkshopHalted
from ebios_rm.orchestrator.workshop_protocol import WorkshopRunner
from ebios_rm.repositories.mission_repository import MissionRepository
from ebios_rm.workshops.workshop1_cadrage.human_interface import approve_workshop
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output


def _default_reinforced_confirm(label: str, *, io_in: Callable[[str], str] = input, io_out: Callable[[str], None] = print) -> bool:
    """Rollback cap reached (conception §12.6) — require an explicit typed confirmation to go further."""
    io_out(f"\nPlafond de {mission_state.ROLLBACK_CAP} versions atteint pour {label} (§12.6).")
    io_out("Une nouvelle reprise est inhabituelle. Tapez CONFIRMER pour relancer malgré tout,")
    io_out("ou toute autre saisie pour arrêter et conserver la dernière version.")
    return io_in("> ").strip() == "CONFIRMER"


class Orchestrator:
    """Runs a mission through however many of the five workshops are registered.

    workshops maps atelier number -> a WorkshopRunner (workshop_protocol.WorkshopRunner).
    It does not need to contain all five: once the mission reaches an atelier
    that has no registered runner, run_mission() returns cleanly (mission stays
    at its last 'approved' status) instead of raising — an Orchestrator built
    with only {1: ..., 2: ...} today keeps working unchanged once {3: ...} is
    added later.
    """

    def __init__(
        self,
        repo: MissionRepository,
        workshops: dict[int, WorkshopRunner],
        *,
        output_models: dict[int, type[BaseModel]] | None = None,
        approve: Callable[[str], tuple[bool, str]] = approve_workshop,
        reinforced_confirm: Callable[[str], bool] = _default_reinforced_confirm,
    ) -> None:
        self._repo = repo
        self._workshops = workshops
        # Atelier 1's output type is always known; atelier 2-5's types are
        # supplied by the caller once each workshop's real model exists.
        self._output_models: dict[int, type[BaseModel]] = {mission_state.WORKSHOP_1: Workshop1Output}
        if output_models:
            self._output_models.update(output_models)
        self._approve = approve
        self._reinforced_confirm = reinforced_confirm
        self._halt_requested = False
        self._active_workshop_number: int | None = None

    # --- public API ---

    def halt(self) -> None:
        """Signal the active workshop to stop gracefully (e.g. from a Ctrl+C handler).

        Does not kill anything — it asks. The workshop decides how it saves its
        own state before raising WorkshopHalted (conception §10.2, workshop
        contract in workshop_protocol.py)."""
        self._halt_requested = True
        if self._active_workshop_number is not None:
            self._workshops[self._active_workshop_number].stop()

    async def run_mission(self, mission_id: str) -> None:
        """Drive the mission forward until it is paused, blocked, or has nothing left to do."""
        while True:
            mission = self._repo.get_mission(mission_id)
            if mission is None:
                raise ValueError(f"Unknown mission: {mission_id!r}")

            action = state_machine.next_action(mission.status)

            if action.action in ("done", "generate_report", "blocked"):
                # 'generate_report' is a deliberate stop here: the reporting agent
                # is a separate component, not built by this class.
                return

            if action.action in ("start_intake", "resume_intake"):
                raise NotImplementedError(
                    "Intake is not yet driven by the Orchestrator; the mission must "
                    "already be 'context_ready' before run_mission() is called."
                )

            if action.action == "await_approval":
                n = self._require_workshop_number(action)
                self._open_gate(mission_id, n)
                continue

            if action.action == "redo_workshop":
                n = self._require_workshop_number(action)
                if not can_redo(self._repo, mission_id, n) and not self._reinforced_confirm(self._label(n)):
                    latest = self._repo.latest_output(mission_id, n)
                    if latest is not None:
                        self._repo.set_version_status(mission_id, n, latest.version_number, "approved")
                    self._repo.log_decision(
                        mission_id, stage=f"w{n}", action="force_accepted",
                        justification="Plafond de retours en arrière atteint ; dernière version conservée (§12.6).",
                    )
                    self._repo.set_status(mission_id, state_machine.approved(n))
                    continue
                if self._halt_requested:
                    self._pause(mission_id, n)
                    return
                if not await self._run_one_workshop(mission_id, n, resume=False):
                    return  # paused or blocked mid-run — do not loop back and auto-resume
                continue

            if action.action in ("start_workshop", "resume_workshop"):
                n = self._require_workshop_number(action)
                if n not in self._workshops:
                    # Not implemented yet (e.g. only ateliers 1-2 exist today) — stop
                    # cleanly. The mission stays at its current 'approved' status,
                    # ready to continue once this atelier's runner is registered.
                    return
                if self._halt_requested:
                    self._pause(mission_id, n)
                    return
                if not await self._run_one_workshop(mission_id, n, resume=(action.action == "resume_workshop")):
                    return  # paused or blocked mid-run — do not loop back and auto-resume
                continue

            raise ValueError(f"Unhandled action: {action.action!r}")

    # --- one workshop, start to finish ---

    async def _run_one_workshop(self, mission_id: str, n: int, *, resume: bool) -> bool:
        """Returns True if run_mission should keep looping (the atelier finished
        and a decision was recorded); False if it should stop entirely (paused
        or blocked mid-run) — a bare early return here is not enough, because
        run_mission's loop would otherwise re-read the now-'paused' status and
        immediately call resume() again within the same run_mission() call."""
        workshop = self._workshop_for(n)
        self._active_workshop_number = n
        self._repo.set_status(mission_id, state_machine.running(n))

        try:
            if resume:
                output = await workshop.resume(mission_id)
            else:
                workshop_input = self._build_input_for(mission_id, n)
                output = await workshop.run(workshop_input, mission_id)
        except WorkshopHalted:
            self._pause(mission_id, n)
            return False
        except WorkshopBlocked as exc:
            self._repo.log_decision(mission_id, stage=f"w{n}", action="blocked", justification=exc.reason)
            self._repo.set_status(mission_id, state_machine.MissionStatus.BLOCKED)
            return False
        finally:
            self._active_workshop_number = None

        version_number = self._save_output(mission_id, n, output)
        self._repo.set_status(mission_id, state_machine.awaiting_approval(n))
        self._open_gate(mission_id, n, output=output, version_number=version_number)
        return True

    def _open_gate(
        self, mission_id: str, n: int, *, output: BaseModel | None = None, version_number: int | None = None
    ) -> None:
        """Show the atelier's output for approval and record the auditor's decision (conception §7, §8).

        Marks both the mission's status AND that specific version's status —
        the same two-writes pattern the current CLI script uses for atelier 1
        (workshop_versions.status tracks current/approved/superseded/rejected
        independently of the mission-level wN_* status)."""
        if version_number is None:
            latest = self._repo.latest_output(mission_id, n)
            if latest is None:
                raise RuntimeError(f"Mission {mission_id} is awaiting approval for atelier {n} but has no saved output.")
            version_number = latest.version_number
        if output is None:
            output = self._load_output(mission_id, n)
        if output is None:
            raise RuntimeError(f"Mission {mission_id} is awaiting approval for atelier {n} but has no saved output.")

        summary = self._workshop_for(n).summarize_output(output)
        approved_ok, reason = self._approve(f"{self._label(n)}\n{summary}")

        if approved_ok:
            self._repo.log_decision(mission_id, stage=f"w{n}", action="approved", justification="")
            self._repo.set_status(mission_id, state_machine.approved(n))
            self._repo.set_version_status(mission_id, n, version_number, "approved")
        else:
            self._repo.log_decision(mission_id, stage=f"w{n}", action="rejected", justification=reason)
            self._repo.set_status(mission_id, state_machine.rejected(n))
            self._repo.set_version_status(mission_id, n, version_number, "rejected")

    # --- input construction (conception §9: narrow typed inputs only) ---

    def _build_input_for(self, mission_id: str, n: int) -> BaseModel:
        if n == mission_state.WORKSHOP_1:
            context = mission_state.load_mission_context(self._repo, mission_id)
            if context is None:
                raise RuntimeError(f"Mission {mission_id} has no Mission Context — intake must run first.")
            return context
        if n == mission_state.WORKSHOP_2:
            w1_output = mission_state.load_w1_output(self._repo, mission_id)
            if w1_output is None:
                raise RuntimeError(f"Mission {mission_id} has no approved atelier 1 output.")
            return build_workshop2_input(w1_output)
        raise NotImplementedError(
            f"No input adapter registered yet for atelier {n} — add build_workshop{n}_input() to "
            f"ebios_rm.orchestrator.input_adapters once atelier {n - 1}'s real output shape exists."
        )

    # --- output persistence ---

    def _save_output(self, mission_id: str, n: int, output: BaseModel) -> int:
        if n == mission_state.WORKSHOP_1:
            return mission_state.save_w1_output(self._repo, mission_id, output)
        return mission_state.save_workshop_output(self._repo, mission_id, n, output)

    def _load_output(self, mission_id: str, n: int) -> BaseModel | None:
        if n == mission_state.WORKSHOP_1:
            return mission_state.load_w1_output(self._repo, mission_id)
        return mission_state.load_workshop_output(self._repo, mission_id, n, self._model_for(n))

    def _model_for(self, n: int) -> type[BaseModel]:
        model_cls = self._output_models.get(n)
        if model_cls is None:
            raise NotImplementedError(
                f"No output model registered for atelier {n} — pass "
                f"output_models={{{n}: YourOutputType}} to Orchestrator() once it exists."
            )
        return model_cls

    # --- misc ---

    def _pause(self, mission_id: str, n: int) -> None:
        self._repo.log_decision(
            mission_id, stage=f"w{n}", action="paused",
            justification="Interruption demandée (Ctrl+C ou arrêt externe).",
        )
        self._repo.set_status(mission_id, state_machine.paused(n))

    def _workshop_for(self, n: int) -> WorkshopRunner:
        workshop = self._workshops.get(n)
        if workshop is None:
            raise KeyError(f"No workshop registered for atelier {n}")
        return workshop

    @staticmethod
    def _require_workshop_number(action: state_machine.NextAction) -> int:
        if action.workshop_number is None:
            raise ValueError(f"Action {action.action!r} requires a workshop_number")
        return action.workshop_number

    @staticmethod
    def _label(n: int) -> str:
        return f"Atelier {n}"
