"""Agno-backed Workshop 5 runner (conception §3.2, §10.1, §19).

One agent, four calls, structured output only — same deviation as the other ateliers:
the ATT&CK mitigation lookup runs in code (AttackRepository.mitigations_for) and its
result is injected into the prompt, so the model can only cite ids the base returned.
"""

from __future__ import annotations

from ebios_rm.agent_runtime import AgnoRunner
from ebios_rm.domain.risk_scenario import RiskScenario
from ebios_rm.repositories.attack_repository import AttackMitigation
from ebios_rm.workshops.workshop5_traitement_risque import prompts
from ebios_rm.workshops.workshop5_traitement_risque.models import (
    IndicatorBatch,
    IndicatorProposal,
    MeasureBatch,
    MeasureProposal,
    ResidualBatch,
    ResidualProposal,
    RiskFormulationBatch,
    RiskFormulationProposal,
    Workshop5Input,
    Workshop5Output,
)


class AgnoWorkshop5Runner(AgnoRunner):
    """Concrete Workshop5AgentRunner backed by Agno + OpenRouter.

    A call that cannot produce its schema raises StructuredCallFailed (agent_runtime),
    never a methodology outcome — an empty plan is not « nothing to do ».
    """

    INSTRUCTIONS = prompts.SYSTEM_INSTRUCTIONS

    def formulate_risques(
        self, w5_input: Workshop5Input, risques: list[RiskScenario],
    ) -> list[RiskFormulationProposal]:
        if not risques:
            return []
        return self._run_structured(
            RiskFormulationBatch,
            prompts.formulations_prompt(w5_input, risques),
            what="formulation métier des risques",
        ).formulations

    def propose_mesures(
        self, w5_input: Workshop5Input, output: Workshop5Output, risques: list[RiskScenario],
        mitigations: dict[str, list[AttackMitigation]],
        revision_notes: list[str] | None = None,
    ) -> list[MeasureProposal]:
        if not risques:
            return []
        return self._run_structured(
            MeasureBatch,
            prompts.mesures_prompt(w5_input, output, risques, mitigations, revision_notes),
            what=f"mesures du plan de traitement ({len(risques)} risque(s))",
        ).mesures

    def evaluate_residuel(
        self, w5_input: Workshop5Input, output: Workshop5Output, risques: list[RiskScenario],
    ) -> list[ResidualProposal]:
        if not risques:
            return []
        return self._run_structured(
            ResidualBatch,
            prompts.residuel_prompt(w5_input, output, risques),
            what="vraisemblance résiduelle après plan",
        ).risques

    def propose_indicateurs(
        self, w5_input: Workshop5Input, output: Workshop5Output,
    ) -> list[IndicatorProposal]:
        if not output.mesures:
            return []
        return self._run_structured(
            IndicatorBatch,
            prompts.indicateurs_prompt(w5_input, output),
            what="indicateurs de suivi",
        ).indicateurs
