"""Adapter wiring the real, LLM-backed Workshop 1 pipeline into the Orchestrator's
WorkshopRunner protocol (conception §10.2, §15).

The real pipeline (run_workshop1() + AgnoWorkshop1Runner) and the Orchestrator's
four-method contract were built independently. This adapter is the only place
that bridges them. Persistence and the approve/reject gate are NOT duplicated
here — the Orchestrator already owns both. This class's only job is to run the
atelier and hand back a finished Workshop1Output, including the read-only
unverified-controls review that scripts/run_workshop1_from_docs.py shows the
auditor before approval.

Not included yet: gap consolidation (_consolidate_gaps in the CLI script). It
performs its own save internally, which would create a redundant version on
every normal run, not just on redo — wiring it in cleanly needs a small change
to that function first, so it is left out of this first pass deliberately.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.orchestrator.signals import WorkshopBlocked
from ebios_rm.repositories.mission_repository import MissionRepository
from ebios_rm.repositories.reference_repository import ReferenceRepository
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output

_CLI_PATH = Path(__file__).resolve().parents[3] / "scripts" / "run_workshop1_from_docs.py"


def _load_cli() -> Any:
    """Load the CLI script as a module so its private helpers (_review_unverified,
    _check_controls_available) can be reused instead of duplicated — the same
    pattern tests/test_redo_loop.py already uses."""
    spec = importlib.util.spec_from_file_location("cli_docs_for_orchestrator", _CLI_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Workshop1Runner:
    """WorkshopRunner for atelier 1, backed by the real agent pipeline.

    For automated tests use FakeWorkshopRunner (tests/orchestrator/orchestrator_fakes.py)
    instead — this class makes real OpenRouter calls and expects a real terminal
    for the auditor-facing prompts inside run_workshop1's agent and the
    unverified-controls review.
    """

    workshop_number = 1

    def __init__(self, reference_repo: ReferenceRepository, repo: MissionRepository) -> None:
        self._reference_repo = reference_repo
        self._repo = repo
        self._cli = _load_cli()

    def check_controls_available(self, mission_context: MissionContext, mission_id: str) -> MissionContext | None:
        """Pre-flight gate (conception §2, §12.5): refuse to run while a declared
        framework has zero loaded controls. Returns the (possibly updated)
        context to use, or None if the auditor chose to stop the mission."""
        return self._cli._check_controls_available(self._repo, mission_id, mission_context, self._reference_repo)

    async def run(self, input: MissionContext, mission_id: str) -> Workshop1Output:
        from ebios_rm.workshops.workshop1_cadrage.agent import AgnoWorkshop1Runner, Workshop1AgentError  # noqa: PLC0415
        from ebios_rm.workshops.workshop1_cadrage.workshop import run_workshop1  # noqa: PLC0415

        try:
            output = run_workshop1(input, AgnoWorkshop1Runner(), self._reference_repo)
        except Workshop1AgentError as exc:
            # A model/provider failure (rate limit, deprecated model, transient
            # outage) is not a workshop bug — it's exactly what WorkshopBlocked
            # exists for (conception §10.2): the Orchestrator records the reason
            # and stops cleanly instead of the raw exception crashing the whole
            # run_mission() call and leaving the mission stuck mid-status.
            raise WorkshopBlocked(f"Échec du modèle pendant l'atelier 1 : {exc}") from exc
        self._cli._review_unverified(self._repo, mission_id, output)
        return output

    def stop(self) -> None:
        # run_workshop1() is one synchronous call with no interruption point
        # exposed today — a real mid-atelier stop would need that function to
        # expose one. Not attempted in this pass.
        pass

    async def resume(self, mission_id: str) -> Workshop1Output:
        raise NotImplementedError(
            "Workshop 1 has no real mid-run checkpoint yet (see stop()) — "
            "a halted atelier 1 must be redone with run(), not resumed."
        )

    def summarize_output(self, output: Workshop1Output) -> str:
        return (
            f"{len(output.biens_essentiels)} bien(s) essentiel(s), "
            f"{len(output.biens_supports)} bien(s) support(s), "
            f"{len(output.evenements_redoutes)} événement(s) redouté(s), "
            f"{len(output.baseline_gaps_full)} écart(s) du socle, "
            f"{len(output.unverified_controls)} contrôle(s) non vérifiable(s)."
        )
