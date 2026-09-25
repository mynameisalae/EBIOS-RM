"""Adapter wiring the real Workshop 2 pipeline into the Orchestrator's
WorkshopRunner protocol (conception §10.2, §16).

Same shape as Workshop1Runner: this class's only job is to run the atelier and
hand back a finished Workshop2Output. Persistence and the approve/reject gate
are NOT duplicated here — the Orchestrator already owns both. The reject/redo
cycle every atelier shares (redo_workshop, the rollback cap of §12.6) replaces
the bespoke ApprovalLoop.rerun mechanism the standalone script uses; this
adapter's run() is always a single, complete attempt.
"""

from __future__ import annotations

from ebios_rm.agent_runtime import StructuredCallFailed
from ebios_rm.orchestrator.signals import WorkshopBlocked
from ebios_rm.plugins.registry import load_ebios_base
from ebios_rm.workshops.common import AtelierDataError
from ebios_rm.workshops.workshop2_sources_risque.agent import AgnoWorkshop2Runner
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Input, Workshop2Output
from ebios_rm.workshops.workshop2_sources_risque.workshop import run_workshop2


class Workshop2Runner:
    """WorkshopRunner for atelier 2, backed by the real agent pipeline.

    For automated tests use a fake Workshop2AgentRunner instead — this class
    makes real OpenRouter calls.
    """

    workshop_number = 2

    def __init__(self, *, base_id: str | None = None) -> None:
        # Loaded once, not per run(): the SR/OV base rarely changes within a
        # mission and discover_ebios_bases() reads the plugin directory each call.
        self._base = load_ebios_base(base_id)

    async def run(self, input: Workshop2Input, mission_id: str) -> Workshop2Output:
        try:
            return run_workshop2(input, AgnoWorkshop2Runner(), self._base)
        except AtelierDataError as exc:
            # Atelier 1 held anomalies that make atelier 2 impossible to run
            # honestly (§2) — not a model failure, but the Orchestrator's
            # contract only has one signal for "cannot proceed."
            raise WorkshopBlocked(f"Atelier 1 comporte des anomalies bloquantes : {exc}") from exc
        except StructuredCallFailed as exc:
            raise WorkshopBlocked(f"Échec du modèle pendant l'atelier 2 : {exc}") from exc

    def stop(self) -> None:
        # run_workshop2() is one synchronous call with no interruption point
        # exposed today, same limitation as Workshop1Runner.
        pass

    async def resume(self, mission_id: str) -> Workshop2Output:
        raise NotImplementedError(
            "Atelier 2 n'a pas de point de reprise interne — un atelier interrompu "
            "doit être refait avec run(), pas repris."
        )

    def summarize_output(self, output: Workshop2Output) -> str:
        return (
            f"{len(output.sources_risque)} source(s) de risque, "
            f"{len(output.objectifs_vises)} objectif(s) visé(s), "
            f"{len(output.couples)} couple(s) retenu(s), "
            f"{len(output.couples_secondaires)} secondaire(s) — "
            f"contrôle qualité : {output.quality_report.statut}."
        )
