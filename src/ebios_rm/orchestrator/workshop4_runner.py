"""Adapter wiring the real Workshop 4 pipeline into the Orchestrator's
WorkshopRunner protocol (conception §10.2, §18).

Workshop4Flow already does everything atelier 4 needs (fan-out, batch review,
coherence, per-scenario redo cap) — this adapter drives that class directly
through its analyse/review/coherence loop (``advance()``) and stops there,
leaving the final approve/reject decision (§18 step 29) to the Orchestrator's
own gate. That is the one seam this adapter cuts: everywhere else,
Workshop4Flow's own methods are reused unmodified, including its checkpointing
(``mission_state.checkpoint_w4_output``), which is what makes this the first
adapter with a real resume() — the others have no mid-run checkpoint to resume
from.

Known scope limit, documented rather than half-solved: a rejection at the
Orchestrator's gate carries one free-text reason, not the per-scenario
targeting Workshop4Flow.redo() uses. run() called again after a reject
therefore restarts atelier 4 from a clean slate rather than reopening just the
scenarios the auditor objected to — correct, but more expensive than it needs
to be. Threading the rejection reason back into a targeted reopen is future
work, once the Orchestrator's reject signal carries more than a string.

Workshop4Flow.advance() is synchronous and, inside it, run_analyses() opens its
own event loop (asyncio.run()) to await every sub-agent concurrently — correct
when called from the standalone script's sync main(), but asyncio.run() cannot
nest inside one that is already running, which the Orchestrator's run() always
is (run_mission() is async). advance() is therefore off-loaded to a worker
thread (asyncio.to_thread), where it is free to own its own loop. This is a
seam in Workshop4Flow itself, not something to route around in every caller —
worth fixing at the source (e.g. run_analyses() checking for a running loop
before deciding whether to open its own) once someone owns that change.
"""

from __future__ import annotations

import asyncio
from typing import Callable

from ebios_rm.agent_runtime import StructuredCallFailed
from ebios_rm.config import load_settings
from ebios_rm.mission_context.clarification import ClarificationRunner
from ebios_rm.orchestrator import mission_state
from ebios_rm.orchestrator.signals import WorkshopBlocked, WorkshopHalted
# _Paused is "private" to workshop4_flow, reused deliberately — same pattern as
# Workshop1Runner loading the CLI script's own private helpers (see its docstring).
from ebios_rm.orchestrator.workshop4_flow import STAGE, Workshop4Flow, _Paused
from ebios_rm.repositories.attack_repository import (
    AttackCatalogue,
    AttackRepository,
    AttackRepositoryError,
    connect_readonly,
)
from ebios_rm.repositories.mission_repository import MissionRepository
from ebios_rm.workshops.common import AtelierDataError
from ebios_rm.workshops.workshop1_cadrage.human_interface import HumanInterface
from ebios_rm.workshops.workshop4_scenarios_operationnels import (
    Workshop4Input,
    Workshop4Output,
    ask_session_questions,
    build_workshop4_input,
    initial_output,
)
from ebios_rm.workshops.workshop4_scenarios_operationnels.agent import AgnoWorkshop4Runner
from ebios_rm.workshops.workshop4_scenarios_operationnels.agent_runner import Workshop4AgentRunner

Ask = Callable[[str], str]
Say = Callable[[str], None]


class Workshop4Runner:
    """WorkshopRunner for atelier 4, backed by the real fan-out/fan-in pipeline.

    For automated tests inject a fake Workshop4AgentRunner via ``runner=``
    instead — this class makes real OpenRouter calls by default.
    """

    workshop_number = 4

    def __init__(
        self,
        repo: MissionRepository,
        *,
        runner: Workshop4AgentRunner | None = None,
        human: HumanInterface | None = None,
        clarifier: ClarificationRunner | None = None,
        io_in: Ask = input,
        io_out: Say = print,
    ) -> None:
        self._repo = repo
        self._runner = runner or AgnoWorkshop4Runner()
        self._human = human
        self._clarifier = clarifier
        self._io_in = io_in
        self._io_out = io_out
        self._catalogue: AttackCatalogue | None = None

    def _load_catalogue(self) -> AttackCatalogue:
        if self._catalogue is None:
            try:
                self._catalogue = AttackRepository(
                    connect_readonly(load_settings().attack_db_path)
                ).catalogue()
            except AttackRepositoryError as exc:
                raise WorkshopBlocked(str(exc)) from exc
        return self._catalogue

    def _flow(self, mission_id: str, mission_context, w4_input: Workshop4Input) -> Workshop4Flow:
        return Workshop4Flow(
            self._repo, mission_id, mission_context, w4_input, self._load_catalogue(), self._runner,
            self._clarifier, self._io_in, self._io_out,
        )

    async def run(self, input: Workshop4Input, mission_id: str) -> Workshop4Output:
        if input.alertes_bloquantes:
            raise WorkshopBlocked(f"Atelier 3 comporte des anomalies bloquantes : {input.alertes_bloquantes}")

        mission_context = mission_state.load_mission_context(self._repo, mission_id)
        if mission_context is None:
            raise WorkshopBlocked(f"Mission {mission_id} : Mission Context introuvable.")

        w4_input = input
        if self._human is not None:
            enriched = ask_session_questions(w4_input, self._human)
            answered = mission_state.persist_session_answers(
                self._repo, mission_id, mission_context, w4_input, enriched, stage=STAGE)
            if answered:
                self._io_out(f"  {answered} réponse(s) de séance enregistrée(s) dans le contexte de la mission.")
            w4_input = enriched

        # Toujours un départ propre : voir la limite documentée en tête de module
        # sur le rejet-puis-relance qui ne cible pas encore un sous-ensemble.
        output = initial_output(w4_input, self._load_catalogue().version)
        mission_state.save_w4_output(self._repo, mission_id, output)
        self._repo.set_status(mission_id, "w4_in_progress")

        flow = self._flow(mission_id, mission_context, w4_input)
        try:
            advanced = await asyncio.to_thread(flow.advance, output)
        except _Paused:
            raise WorkshopHalted("Atelier 4 interrompu par l'auditeur — tout est enregistré.") from None
        except StructuredCallFailed as exc:
            raise WorkshopBlocked(f"Échec du modèle pendant l'atelier 4 : {exc}") from exc
        except AtelierDataError as exc:
            raise WorkshopBlocked(f"Atelier 3 comporte des anomalies bloquantes : {exc}") from exc
        return advanced

    def stop(self) -> None:
        # No external stop() hook exposed by Workshop4Flow today — the auditor
        # halts it interactively ('q' at a decision), which already raises
        # _Paused and is caught above. A Ctrl+C mid fan-out is caught by Python
        # itself; asyncio.gather's already-returned analyses are still
        # checkpointed as they complete (workshop.py's ``saved`` callback).
        pass

    async def resume(self, mission_id: str) -> Workshop4Output:
        """Continue exactly where the last checkpoint left off (§18) — the one
        adapter where this is a real resume, not a restart: Workshop4Flow
        checkpoints after every sub-agent answer and every review decision."""
        saved = mission_state.load_w4_output(self._repo, mission_id)
        if saved is None:
            raise WorkshopBlocked(f"Mission {mission_id} : aucun atelier 4 en cours à reprendre.")
        mission_context = mission_state.load_mission_context(self._repo, mission_id)
        if mission_context is None:
            raise WorkshopBlocked(f"Mission {mission_id} : Mission Context introuvable.")

        w1 = mission_state.load_w1_output(self._repo, mission_id)
        w2 = mission_state.load_w2_output(self._repo, mission_id)
        w3 = mission_state.load_w3_output(self._repo, mission_id)
        w4_input = build_workshop4_input(mission_context, w1, w2, w3)

        flow = self._flow(mission_id, mission_context, w4_input)
        try:
            return await asyncio.to_thread(flow.advance, saved)
        except _Paused:
            raise WorkshopHalted("Atelier 4 interrompu par l'auditeur — tout est enregistré.") from None
        except StructuredCallFailed as exc:
            raise WorkshopBlocked(f"Échec du modèle pendant l'atelier 4 : {exc}") from exc

    def summarize_output(self, output: Workshop4Output) -> str:
        return (
            f"{len(output.scenarios)} scénario(s) opérationnel(s), ATT&CK {output.attck_version} — "
            f"cohérence : {output.coherence.decision if output.coherence else 'non effectuée'} — "
            f"contrôle qualité : {output.quality_report.statut}."
        )
