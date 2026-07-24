"""Workshop 1 — Cadrage et socle de sécurité (conception §15).

Single agent. Consumes the Mission Context only, never raw documents. Extracts
essential/support assets and feared events with gravity, assesses the security
baseline against the declared frameworks, and runs the dedicated legal-impact
assessment (§15.1), independent of baseline gaps.

Public entry points:
    complete_intake_from_documents(intake_doc, supporting_docs, ingestion_runner,
                                   human, auditor_reviewer) -> MissionContext
    run_workshop1(mission_context, runner, reference_repo) -> Workshop1Output
"""

from ebios_rm.workshops.workshop1_cadrage.intake_ingestion import (
    complete_intake_from_documents,
    complete_intake_from_facts,
)
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop1_cadrage.workshop import run_workshop1

__all__ = [
    "Workshop1Output",
    "complete_intake_from_documents",
    "complete_intake_from_facts",
    "run_workshop1",
]
