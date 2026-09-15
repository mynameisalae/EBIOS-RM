"""The LLM boundary for Workshop 4, behind a Protocol so orchestration is testable.

Two kinds of call (conception §18): one analysis per strategic scenario, each by an
independent sub-agent — never a Team, the sub-agents do not know about each other —
and a single coherence call once the set is stable. Both only propose; every check,
rating and decision is enforced in assessment.py. Tests inject a fake runner; the
real one (agent.py) drives Agno + OpenRouter through structured output only.
"""

from __future__ import annotations

from typing import Protocol

from ebios_rm.domain.operational_scenario import OperationalScenario
from ebios_rm.repositories.attack_repository import AttackCatalogue
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import (
    CoherenceFindingProposal,
    ScenarioAnalysisProposal,
    Workshop4Input,
)


class Workshop4AgentRunner(Protocol):
    """Everything Workshop 4 asks the model to do (conception §18)."""

    async def analyse_scenario(
        self, w4_input: Workshop4Input, pending: OperationalScenario, catalogue: AttackCatalogue,
    ) -> ScenarioAnalysisProposal:
        """Write the operational scenario of one strategic scenario (§18 step 22).

        ``pending`` carries the strategic scenario id and, on a redo, the analysis
        the auditor sent back with every reason given so far, so the prompt can
        exclude that answer explicitly (§18 step 25, §21).
        """
        ...

    def check_coherence(
        self, w4_input: Workshop4Input, scenarios: list[OperationalScenario],
    ) -> list[CoherenceFindingProposal]:
        """Read the confirmed set together, once it is stable (§18 step 28)."""
        ...
