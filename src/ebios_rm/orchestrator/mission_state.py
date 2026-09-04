"""Mission state service — typed save/load + resume/redo logic (conception §10.2, §12.6).

Sits between the CLI and the dict-only MissionRepository: it (de)serializes the
domain models and owns the small decisions the repository must not (which phase to
resume from, whether a redo is still allowed under the rollback cap).
"""

from __future__ import annotations

from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.mission_repository import ROLLBACK_CAP, MissionRepository
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Output

WORKSHOP_CONTEXT = 0  # the Mission Context (intake result)
WORKSHOP_1 = 1
WORKSHOP_2 = 2


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


def save_w2_output(repo: MissionRepository, mission_id: str, output: Workshop2Output, *, status: str = "current") -> int:
    return repo.save_output(mission_id, WORKSHOP_2, output.model_dump(mode="json"), status=status)


def load_w2_output(repo: MissionRepository, mission_id: str) -> Workshop2Output | None:
    version = repo.latest_output(mission_id, WORKSHOP_2)
    return Workshop2Output.model_validate(version.output) if version else None


def is_approved(repo: MissionRepository, mission_id: str, workshop_number: int) -> bool:
    """Whether this workshop's latest version is the one the auditor approved (§2).

    The durable answer to « is that atelier done ». The mission's status string
    tracks the stage in progress and moves on — the moment atelier 3 runs, a
    mission that was w2_approved reads w3_awaiting_approval — so it cannot answer
    the question for a workshop already behind. The version status can.

    Latest, not any: an approved version followed by a newer rejected one means
    the auditor reopened the atelier, and the next workshop must wait.
    """
    version = repo.latest_output(mission_id, workshop_number)
    return version is not None and version.status == "approved"


def can_redo(repo: MissionRepository, mission_id: str, workshop_number: int) -> bool:
    """False once the rollback cap is reached — the caller must ask for reinforced confirmation (§12.6)."""
    return repo.version_count(mission_id, workshop_number) < ROLLBACK_CAP
