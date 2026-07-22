"""Workshop 1 — Cadrage et socle de sécurité (conception §15).

Single agent. Consumes the Mission Context only, never raw documents. Extracts
essential/support assets and feared events with gravity, assesses the security
baseline against the declared frameworks, and runs the dedicated legal-impact
assessment (§15.1), independent of baseline gaps.

Public entry points:
    complete_intake(form, extraction_facts, human) -> MissionContext
    run_workshop1(mission_context, runner, reference_repo) -> Workshop1Output
    run(form, extraction_facts, runner, reference_repo, human) -> Workshop1Output
"""

from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop1_cadrage.workshop import (
    complete_intake,
    run,
    run_workshop1,
)

__all__ = ["Workshop1Output", "complete_intake", "run", "run_workshop1"]
