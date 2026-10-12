"""Adapter wiring the real Workshop 5 pipeline into the Orchestrator's
WorkshopRunner protocol (conception §10.2, §19).

Workshop5Flow already does everything atelier 5 needs (the five activities, the
auditor's decisions, the plan review, the formal acceptance of the residual risks,
resume from any checkpoint) — this adapter drives that class through ``advance()``
and stops there, leaving the final approve/reject decision to the Orchestrator's
own gate. Same seam, same reason as Workshop4Runner.

Unlike atelier 4 there is no fan-out here: the activities are sequential and each is
one call, so advance() is called directly rather than off-loaded to a worker thread.

Known scope limit, documented rather than half-solved: a rejection at the
Orchestrator's gate carries one free-text reason. run() called again therefore
rebuilds the risk map from scratch, while Workshop5Flow.redo() keeps the auditor's
treatment decisions and reopens only the plan with the rejection reasons attached.
Threading the reason back into a targeted reopen is future work, once the
Orchestrator's reject signal carries more than a string.
"""

from __future__ import annotations

from typing import Callable

from ebios_rm.agent_runtime import StructuredCallFailed
from ebios_rm.config import load_settings
from ebios_rm.mission_context.clarification import ClarificationRunner
from ebios_rm.orchestrator import mission_state
from ebios_rm.orchestrator.signals import WorkshopBlocked, WorkshopHalted
# _Paused is "private" to workshop5_flow, reused deliberately — same pattern as
# Workshop4Runner (see its docstring).
from ebios_rm.orchestrator.workshop5_flow import STAGE, Workshop5Flow, Workshop5NotReady, _Paused
from ebios_rm.repositories.attack_repository import (
    AttackRepository,
    AttackRepositoryError,
    connect_readonly,
)
from ebios_rm.repositories.mission_repository import MissionRepository
from ebios_rm.workshops.common import AtelierDataError
from ebios_rm.workshops.workshop1_cadrage.human_interface import HumanInterface
from ebios_rm.workshops.workshop5_traitement_risque import (
    Workshop5Input,
    Workshop5Output,
    ask_session_questions,
    build_workshop5_input,
)
from ebios_rm.workshops.workshop5_traitement_risque.agent import AgnoWorkshop5Runner
from ebios_rm.workshops.workshop5_traitement_risque.agent_runner import Workshop5AgentRunner

Ask = Callable[[str], str]
Say = Callable[[str], None]


class Workshop5Runner:
    """WorkshopRunner for atelier 5, backed by the real treatment pipeline.

    For automated tests inject a fake Workshop5AgentRunner via ``runner=`` instead —
    this class makes real OpenRouter calls by default.
    """

    workshop_number = 5

    def __init__(
        self,
        repo: MissionRepository,
        *,
        runner: Workshop5AgentRunner | None = None,
        attack: AttackRepository | None = None,
        human: HumanInterface | None = None,
        clarifier: ClarificationRunner | None = None,
        io_in: Ask = input,
        io_out: Say = print,
    ) -> None:
        self._repo = repo
        self._runner = runner or AgnoWorkshop5Runner()
        self._attack = attack
        self._human = human
        self._clarifier = clarifier
        self._io_in = io_in
        self._io_out = io_out

    def _load_attack(self) -> AttackRepository:
        if self._attack is None:
            try:
                self._attack = AttackRepository(connect_readonly(load_settings().attack_db_path))
                self._attack.version()
            except AttackRepositoryError as exc:
                raise WorkshopBlocked(str(exc)) from exc
        return self._attack

    def _flow(self, mission_id: str, mission_context, w5_input: Workshop5Input) -> Workshop5Flow:
        return Workshop5Flow(
            self._repo, mission_id, mission_context, w5_input, self._load_attack(), self._runner,
            self._clarifier, self._io_in, self._io_out,
        )

    def _advance(self, flow: Workshop5Flow, output: Workshop5Output | None) -> Workshop5Output:
        try:
            return flow.advance(output if output is not None else flow.start())
        except _Paused:
            raise WorkshopHalted("Atelier 5 interrompu par l'auditeur — tout est enregistré.") from None
        except StructuredCallFailed as exc:
            raise WorkshopBlocked(f"Échec du modèle pendant l'atelier 5 : {exc}") from exc
        except (AtelierDataError, Workshop5NotReady) as exc:
            raise WorkshopBlocked(f"L'atelier 5 ne peut pas démarrer : {exc}") from exc

    async def run(self, input: Workshop5Input, mission_id: str) -> Workshop5Output:
        if input.alertes_bloquantes:
            raise WorkshopBlocked(f"Atelier 4 comporte des anomalies bloquantes : {input.alertes_bloquantes}")

        mission_context = mission_state.load_mission_context(self._repo, mission_id)
        if mission_context is None:
            raise WorkshopBlocked(f"Mission {mission_id} : Mission Context introuvable.")

        w5_input = input
        if self._human is not None:
            enriched = ask_session_questions(w5_input, self._human)
            answered = mission_state.persist_session_answers(
                self._repo, mission_id, mission_context, w5_input, enriched, stage=STAGE)
            if answered:
                self._io_out(f"  {answered} réponse(s) de séance enregistrée(s) dans le contexte de la mission.")
            w5_input = enriched

        # Toujours un départ propre : voir la limite documentée en tête de module
        # sur le rejet-puis-relance qui ne cible pas encore le seul plan.
        return self._advance(self._flow(mission_id, mission_context, w5_input), None)

    def stop(self) -> None:
        # No external stop() hook exposed by Workshop5Flow today — the auditor halts it
        # interactively ('q' at a decision), which already raises _Paused and is caught
        # above. Every decision taken before that is checkpointed as it happens.
        pass

    async def resume(self, mission_id: str) -> Workshop5Output:
        """Continue exactly where the last checkpoint left off (§19).

        A real resume, like atelier 4's: Workshop5Flow checkpoints after every model
        call and every decision of the séance, and reads where it stands off the saved
        w5_output itself.
        """
        saved = mission_state.load_w5_output(self._repo, mission_id)
        if saved is None:
            raise WorkshopBlocked(f"Mission {mission_id} : aucun atelier 5 en cours à reprendre.")
        mission_context = mission_state.load_mission_context(self._repo, mission_id)
        if mission_context is None:
            raise WorkshopBlocked(f"Mission {mission_id} : Mission Context introuvable.")

        w1 = mission_state.load_w1_output(self._repo, mission_id)
        w2 = mission_state.load_w2_output(self._repo, mission_id)
        w3 = mission_state.load_w3_output(self._repo, mission_id)
        w4 = mission_state.load_w4_output(self._repo, mission_id)
        if w1 is None or w2 is None or w3 is None or w4 is None:
            raise WorkshopBlocked(f"Mission {mission_id} : les ateliers 1 à 4 ne sont pas tous enregistrés.")
        w5_input = build_workshop5_input(mission_context, w1, w2, w3, w4)

        return self._advance(self._flow(mission_id, mission_context, w5_input), saved)

    def summarize_output(self, output: Workshop5Output) -> str:
        accepted = sum(1 for r in output.risques if r.accepte_par.strip())
        return (
            f"{len(output.risques)} risque(s) dont {accepted} résiduel(s) accepté(s), "
            f"{len(output.mesures)} mesure(s) au plan, "
            f"{len(output.cadre_suivi.indicateurs) if output.cadre_suivi else 0} indicateur(s) de suivi — "
            f"contrôle qualité : {output.quality_report.statut}."
        )
