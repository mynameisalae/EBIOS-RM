"""Mission state service — typed save/load + resume/redo logic (conception §10.2, §12.6).

Sits between the CLI and the dict-only MissionRepository: it (de)serializes the
domain models and owns the small decisions the repository must not (which phase to
resume from, whether a redo is still allowed under the rollback cap).
"""

from __future__ import annotations

from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.mission_repository import ROLLBACK_CAP, MissionRepository
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output

WORKSHOP_CONTEXT = 0  # the Mission Context (intake result)
WORKSHOP_1 = 1


def save_mission_context(repo: MissionRepository, mission_id: str, mc: MissionContext) -> None:
    """Save the finished Mission Context as a new version (intake complete)."""
    repo.save_output(mission_id, WORKSHOP_CONTEXT, mc.model_dump(mode="json"), status="current")


def checkpoint_mission_context(repo: MissionRepository, mission_id: str, mc: MissionContext) -> None:
    """Save intake progress in place after each answer, so a mid-intake crash resumes (phase A)."""
    repo.save_output(mission_id, WORKSHOP_CONTEXT, mc.model_dump(mode="json"), status="current", overwrite=True)


def load_mission_context(repo: MissionRepository, mission_id: str) -> MissionContext | None:
    version = repo.latest_output(mission_id, WORKSHOP_CONTEXT)
    return MissionContext.model_validate(version.output) if version else None


def save_w1_output(repo: MissionRepository, mission_id: str, output: Workshop1Output, *, status: str = "current") -> int:
    return repo.save_output(mission_id, WORKSHOP_1, output.model_dump(mode="json"), status=status)


def load_w1_output(repo: MissionRepository, mission_id: str) -> Workshop1Output | None:
    version = repo.latest_output(mission_id, WORKSHOP_1)
    return Workshop1Output.model_validate(version.output) if version else None


def can_redo(repo: MissionRepository, mission_id: str, workshop_number: int) -> bool:
    """False once the rollback cap is reached — the caller must ask for reinforced confirmation (§12.6)."""
    return repo.version_count(mission_id, workshop_number) < ROLLBACK_CAP
