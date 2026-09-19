"""Adapter wiring the real Workshop 5 pipeline into the Orchestrator's
WorkshopRunner protocol (conception §10.2, §19).

Same shape as Workshop2Runner: one call, no fan-out, no bespoke gate beyond
the shared approve/reject the Orchestrator already owns. The one difference
from every earlier adapter is what run_workshop5() itself needs: unlike
Workshop2/3's run_workshopN(), it does not take just the narrow Workshop5Input
— it also re-checks the finalized atelier 4 output against atelier 1's full
baseline gaps (validate_atelier4, §19 étape 0), so this adapter loads both
w1_output and w4_output from mission state itself rather than folding them
into the input the Orchestrator built.

The ATT&CK repository is opened once and kept for the runner's lifetime, the
same lazy-cache pattern Workshop4Runner uses for its catalogue — atelier 5
builds its own narrower MitigationCatalogue per run (only the techniques the
approved scenarios actually cite), so what is cached here is the connection,
not a catalogue.
"""

from __future__ import annotations

from ebios_rm.agent_runtime import StructuredCallFailed
from ebios_rm.config import load_settings
from ebios_rm.orchestrator import mission_state
from ebios_rm.orchestrator.signals import WorkshopBlocked
from ebios_rm.repositories.attack_repository import AttackRepository, AttackRepositoryError, connect_readonly
from ebios_rm.repositories.mission_repository import MissionRepository
from ebios_rm.workshops.common import AtelierDataError
from ebios_rm.workshops.workshop5_traitement_risque import Workshop5Input, Workshop5Output, run_workshop5
from ebios_rm.workshops.workshop5_traitement_risque.agent import AgnoWorkshop5Runner
from ebios_rm.workshops.workshop5_traitement_risque.agent_runner import Workshop5AgentRunner


class Workshop5Runner:
    """WorkshopRunner for atelier 5, backed by the real agent pipeline.

    For automated tests inject a fake Workshop5AgentRunner via ``runner=``
    instead — this class makes real OpenRouter calls (with real tool calling)
    by default.
    """

    workshop_number = 5

    def __init__(self, repo: MissionRepository, *, runner: Workshop5AgentRunner | None = None) -> None:
        self._repo = repo
        self._runner = runner or AgnoWorkshop5Runner()
        self._attack_repo: AttackRepository | None = None

    def _load_attack_repo(self) -> AttackRepository:
        if self._attack_repo is None:
            try:
                self._attack_repo = AttackRepository(connect_readonly(load_settings().attack_db_path))
            except AttackRepositoryError as exc:
                raise WorkshopBlocked(str(exc)) from exc
        return self._attack_repo

    async def run(self, input: Workshop5Input, mission_id: str) -> Workshop5Output:
        w1_output = mission_state.load_w1_output(self._repo, mission_id)
        w4_output = mission_state.load_w4_output(self._repo, mission_id)
        if w1_output is None or w4_output is None:
            raise WorkshopBlocked(f"Mission {mission_id} : atelier 1 ou atelier 4 approuvé introuvable.")

        try:
            return run_workshop5(input, self._runner, self._load_attack_repo(), w4_output, w1_output)
        except AtelierDataError as exc:
            raise WorkshopBlocked(f"Atelier 4 comporte des anomalies bloquantes : {exc}") from exc
        except StructuredCallFailed as exc:
            raise WorkshopBlocked(f"Échec du modèle pendant l'atelier 5 : {exc}") from exc

    def stop(self) -> None:
        # run_workshop5() is one synchronous call with no interruption point
        # exposed today, same limitation as Workshop1Runner/Workshop2Runner.
        pass

    async def resume(self, mission_id: str) -> Workshop5Output:
        raise NotImplementedError(
            "Atelier 5 n'a pas de point de reprise interne — un atelier interrompu "
            "doit être refait avec run(), pas repris."
        )

    def summarize_output(self, output: Workshop5Output) -> str:
        return (
            f"{len(output.mesures)} mesure(s) de traitement proposée(s), "
            f"{len(output.elements_ecartes)} élément(s) écarté(s) — "
            f"contrôle qualité : {output.quality_report.statut}."
        )
