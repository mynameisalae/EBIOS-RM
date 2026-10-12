"""The LLM boundary for Workshop 5, behind a Protocol so orchestration is testable.

Four calls (méthode atelier 5): how each risk reads for a decision-maker (5-1), the
measures of the treatment plan (5-3), the likelihood that remains once the plan is in
place (5-4), and the indicators that will follow it (5-5).

What the model is never asked: the treatment option per risk and the acceptance of the
residual risks. Those are the two decisions the method puts on people (§2).
"""

from __future__ import annotations

from typing import Protocol

from ebios_rm.domain.risk_scenario import RiskScenario
from ebios_rm.repositories.attack_repository import AttackMitigation
from ebios_rm.workshops.workshop5_traitement_risque.models import (
    IndicatorProposal,
    MeasureProposal,
    ResidualProposal,
    RiskFormulationProposal,
    Workshop5Input,
    Workshop5Output,
)


class Workshop5AgentRunner(Protocol):
    """Everything Workshop 5 asks the model to do (conception §19)."""

    def formulate_risques(
        self, w5_input: Workshop5Input, risques: list[RiskScenario],
        revision_notes: list[str] | None = None,
    ) -> list[RiskFormulationProposal]:
        """Write each risk in business words, for the people who will rule on it (5-1)."""
        ...

    def propose_mesures(
        self, w5_input: Workshop5Input, output: Workshop5Output, risques: list[RiskScenario],
        mitigations: dict[str, list[AttackMitigation]],
        revision_notes: list[str] | None = None,
    ) -> list[MeasureProposal]:
        """Propose the measures of the treatment plan for the risks the auditor is treating (5-3).

        ``revision_notes``, here and on the two other revisable calls, carries the
        auditor's reasons — a rejection at the gate, or what they asked to add — so a
        relaunch corrects them instead of proposing the same thing again (§12.6).
        """
        ...

    def evaluate_residuel(
        self, w5_input: Workshop5Input, output: Workshop5Output, risques: list[RiskScenario],
    ) -> list[ResidualProposal]:
        """Say what likelihood remains once the plan is in place, and why (5-4)."""
        ...

    def propose_indicateurs(
        self, w5_input: Workshop5Input, output: Workshop5Output,
        revision_notes: list[str] | None = None,
    ) -> list[IndicatorProposal]:
        """Propose the monitoring indicators of the plan (5-5)."""
        ...
