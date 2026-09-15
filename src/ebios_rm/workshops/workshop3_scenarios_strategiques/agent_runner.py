"""The LLM boundary for Workshop 3, behind a Protocol so orchestration is testable.

Two passes, one agent (conception §17): propose the scenarios, then criticise the
list it just produced. Both only ever *propose* — every acceptance, rejection,
rating and count decision is enforced downstream in assessment.py, which has no
LLM at all. Tests inject a fake runner; the real one (agent.py) drives Agno +
OpenRouter through structured output only.
"""

from __future__ import annotations

from typing import Protocol

from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import (
    CritiqueVerdict,
    ScenarioProposal,
    Workshop3Input,
)


class Workshop3AgentRunner(Protocol):
    """Everything Workshop 3 asks the model to do (conception §17)."""

    def propose_scenarios(
        self, w3_input: Workshop3Input, revision_notes: list[str] | None = None,
    ) -> list[ScenarioProposal]:
        """Write one strategic scenario per plausible SR/OV couple (§17, pass 1).

        The route through the ecosystem and its justification, at the level of the
        business and its parties prenantes — never the operating mode, which is
        atelier 4's. The model invents no couple, no rating and no stakeholder.

        revision_notes carries the auditor's rejection reasons from prior versions
        so the redo addresses them explicitly.
        """
        ...

    def critique_scenarios(
        self, w3_input: Workshop3Input, scenarios: list[StrategicScenario],
    ) -> list[CritiqueVerdict]:
        """Fold the near-duplicates of the list just produced (§17, pass 2).

        One verdict per scenario: keep it, or name the scenario it repeats and say
        why. Pruning without a reason is refused in code — the count gate is where
        the list gets shortened, and it is the auditor's, not the model's.
        """
        ...
