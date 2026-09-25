"""Mission state service — typed save/load + resume/redo logic (conception §10.2, §12.6).

Sits between the CLI and the dict-only MissionRepository: it (de)serializes the
domain models and owns the small decisions the repository must not (which phase to
resume from, whether a redo is still allowed under the rollback cap).
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.mission_repository import ROLLBACK_CAP, MissionRepository
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Output
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import Workshop3Output
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import Workshop4Output
from ebios_rm.workshops.workshop5_traitement_risque.models import Workshop5Output

WORKSHOP_CONTEXT = 0  # the Mission Context (intake result)
WORKSHOP_1 = 1
WORKSHOP_2 = 2
WORKSHOP_3 = 3
WORKSHOP_4 = 4
WORKSHOP_5 = 5

T = TypeVar("T", bound=BaseModel)


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


def save_w3_output(repo: MissionRepository, mission_id: str, output: Workshop3Output, *, status: str = "current") -> int:
    return repo.save_output(mission_id, WORKSHOP_3, output.model_dump(mode="json"), status=status)


def load_w3_output(repo: MissionRepository, mission_id: str) -> Workshop3Output | None:
    version = repo.latest_output(mission_id, WORKSHOP_3)
    return Workshop3Output.model_validate(version.output) if version else None


def save_w4_output(repo: MissionRepository, mission_id: str, output: Workshop4Output, *, status: str = "current") -> int:
    """A new attempt at atelier 4 — the first run, or a redo decided at the approval gate."""
    return repo.save_output(mission_id, WORKSHOP_4, output.model_dump(mode="json"), status=status)


def checkpoint_w4_output(repo: MissionRepository, mission_id: str, output: Workshop4Output) -> int:
    """Progress within one attempt, in place: every returned analysis, every review decision.

    Atelier 4 pays one call per scenario and the review can span days; a new version
    per result would also exhaust the rollback cap (§12.6) before the auditor ever
    reached the approval gate. An attempt whose version was already ruled on starts
    a new version instead.
    """
    return repo.save_output(mission_id, WORKSHOP_4, output.model_dump(mode="json"), status="current", overwrite=True)


def load_w4_output(repo: MissionRepository, mission_id: str) -> Workshop4Output | None:
    version = repo.latest_output(mission_id, WORKSHOP_4)
    return Workshop4Output.model_validate(version.output) if version else None


def save_w5_output(repo: MissionRepository, mission_id: str, output: Workshop5Output, *, status: str = "current") -> int:
    """A new attempt at atelier 5 — the first run, or a redo decided at the approval gate."""
    return repo.save_output(mission_id, WORKSHOP_5, output.model_dump(mode="json"), status=status)


def checkpoint_w5_output(repo: MissionRepository, mission_id: str, output: Workshop5Output) -> int:
    """Progress within one attempt, in place — same reason as atelier 4.

    Atelier 5 is a séance: the risk map is read, each risk gets a decision, the plan is
    reviewed measure by measure, the residual risks are accepted by name. That spans
    hours or days, and a version per decision would exhaust the rollback cap (§12.6)
    before the auditor reached the approval gate.
    """
    return repo.save_output(mission_id, WORKSHOP_5, output.model_dump(mode="json"), status="current", overwrite=True)


def load_w5_output(repo: MissionRepository, mission_id: str) -> Workshop5Output | None:
    version = repo.latest_output(mission_id, WORKSHOP_5)
    return Workshop5Output.model_validate(version.output) if version else None


def persist_session_answers(repo, mission_id, mission_context, before, after, *, stage: str) -> int:
    """Write the session's new Facts back into the Mission Context. Returns how many.

    Session answers are facts about the organisation, not workshop scratch: stored
    here, a rerun does not ask them again and the report agent sees them with their
    provenance intact.
    """
    known = {f.field_name for f in before.faits_contexte}
    new_facts = [f for f in after.faits_contexte if f.field_name not in known]
    if not new_facts:
        return 0
    updated = mission_context.model_copy(update={"facts": [*mission_context.facts, *new_facts]})
    save_mission_context(repo, mission_id, updated)
    repo.log_decision(
        mission_id, stage=stage, action=f"session_answers:{len(new_facts)}",
        justification="; ".join(f.field_name for f in new_facts),
    )
    return len(new_facts)


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


# --- Generic save/load for workshops 2-5 ---
#
# Workshop 1 keeps its dedicated save_w1_output/load_w1_output above (existing
# tests depend on the exact names). Workshops 2-5 share one generic pair instead
# of four near-identical copies — same underlying repo.save_output/latest_output,
# just parameterized by workshop_number and the caller's own Pydantic model.


def save_workshop_output(
    repo: MissionRepository, mission_id: str, workshop_number: int, output: BaseModel, *, status: str = "current"
) -> int:
    return repo.save_output(mission_id, workshop_number, output.model_dump(mode="json"), status=status)


def load_workshop_output(
    repo: MissionRepository, mission_id: str, workshop_number: int, model_cls: type[T]
) -> T | None:
    version = repo.latest_output(mission_id, workshop_number)
    return model_cls.model_validate(version.output) if version else None
