"""The LLM boundary for Workshop 5, behind a Protocol so orchestration is testable.

One call, one agent — unlike atelier 4, there is no fan-out here (conception
§19: "agent unique"), so unlike atelier 4's runner this one is synchronous:
no concurrent calls means no reason to pay the async/event-loop complexity
that made atelier 4's integration with the Orchestrator its own source of
bugs (see workshop4_runner.py's docstring). Real tool calls happen inside
this one call regardless of sync or async — Agno resolves them the same way.
"""

from __future__ import annotations

from typing import Protocol

from ebios_rm.repositories.attack_repository import MitigationCatalogue
from ebios_rm.workshops.workshop5_traitement_risque.models import MesuresBatch, Workshop5Input


class Workshop5AgentRunner(Protocol):
    """Everything Workshop 5 asks the model to do (conception §19)."""

    def propose_mesures(self, w5_input: Workshop5Input, mitigations: MitigationCatalogue) -> MesuresBatch:
        """Propose the treatment measures for this mission's finalized scenarios.

        ``mitigations`` is the catalogue already built for exactly the
        techniques cited in ``w5_input.scenarios`` — the real agent wraps it
        in the ATT&CK tool and calls it live; a fake used in tests may just
        read it directly, since the fiche de test only checks the ids that
        come back are real, not that a tool call happened.
        """
        ...
