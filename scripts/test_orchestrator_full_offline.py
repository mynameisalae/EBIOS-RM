# -*- coding: utf-8 -*-
"""Fait tourner l'Orchestrateur generique sur les Ateliers 1 a 5, en entier,
avec de faux agents (zero appel reseau, zero token) -- pour prouver que
l'architecture par classe pilote reellement les vrais ateliers 2, 3, 4 et 5,
pas seulement l'Atelier 1.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests" / "workshops"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ebios_rm.domain.enums import (
    CategorieImpact, Gravite, Origin, Pertinence, StatutSelection, VraisemblanceInitiale,
)
from ebios_rm.domain.essential_asset import EssentialAsset, SupportAsset
from ebios_rm.domain.fact import Fact
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.domain.risk_source import CoupleSROV, ObjectifVise, RiskSource
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.orchestrator import mission_state, state_machine
from ebios_rm.orchestrator.orchestrator import Orchestrator
from ebios_rm.orchestrator.workshop1_runner import Workshop1Runner
from ebios_rm.orchestrator.workshop2_runner import Workshop2Runner
from ebios_rm.orchestrator.workshop3_runner import Workshop3Runner
from ebios_rm.orchestrator.workshop4_runner import Workshop4Runner
from ebios_rm.orchestrator.workshop5_runner import Workshop5Runner
from ebios_rm.repositories.mission_repository import MissionRepository, connect
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import (
    AttackStepProposal, CoherenceBatch, ScenarioAnalysisProposal,
)
from ebios_rm.workshops.workshop5_traitement_risque.models import MesuresBatch, MesureProposal
from fakes import FakeWorkshop2Runner, FakeWorkshop3Runner  # tests/workshops/fakes.py

MISSION_CONTEXT = MissionContext(
    organisation_nom="Clinique Test", secteur_activite="Sante",
    applicable_frameworks=["ANSSI_hygiene"],
    facts=[
        Fact.declaration("systeme_information_resume", "SIH central + portail patient exposé"),
        Fact.declaration("exposition_internet", "Portail de prise de rendez-vous en ligne"),
        Fact.declaration("interconnexions_tiers", "Liaison de télémaintenance avec l'éditeur du SIH"),
        Fact.declaration("authentification_forte", "Aucune, mot de passe seul"),
    ],
)


class FakeWorkshop1(Workshop1Runner):
    """Court-circuite le vrai pipeline Atelier 1 : renvoie un w1_output scripte."""

    def __init__(self) -> None:  # pas d'appel a super().__init__: pas besoin des vrais repos
        pass

    async def run(self, input, mission_id):
        return Workshop1Output(
            biens_essentiels=[
                EssentialAsset(id="BE-1", nom="Dossier patient", description="Données de santé",
                                nature="information", processus_metier_associes=["Prise en charge"],
                                origin=Origin.ASSESSMENT, derived_from_fact_fields=["systeme_information_resume"]),
            ],
            biens_supports=[
                SupportAsset(id="BS-1", nom="SIH", description="Système d'information hospitalier",
                             type_support="application", biens_essentiels_supportes=["BE-1"],
                             origin=Origin.ASSESSMENT, derived_from_fact_fields=["systeme_information_resume"]),
            ],
            evenements_redoutes=[
                FearedEvent(id="ER-1", description="Indisponibilité du dossier patient", bien_essentiel_id="BE-1",
                            categorie_impact=CategorieImpact.FONCTIONNEMENT, gravite=Gravite.CRITIQUE,
                            origin=Origin.ASSESSMENT, derived_from_fact_fields=["exposition_internet"]),
            ],
        )

    def stop(self): pass
    async def resume(self, mission_id): raise NotImplementedError


def main() -> int:
    db_path = "data/mission/test_orchestrator_full.db"
    Path(db_path).unlink(missing_ok=True)
    repo = MissionRepository(connect(db_path))
    mission_id = repo.create_mission("test_orchestrator_full", ["ANSSI_hygiene"])

    mission_state.save_mission_context(repo, mission_id, MISSION_CONTEXT)
    repo.set_status(mission_id, "context_ready")

    # --- de vrais agents factices, injectes dans les VRAIS pipelines des ateliers 2/3/4 ---
    import ebios_rm.workshops.workshop2_sources_risque.workshop as w2mod
    import ebios_rm.workshops.workshop3_scenarios_strategiques.workshop as w3mod

    class Workshop2RunnerFake(Workshop2Runner):
        def __init__(self):
            self._base = _load_base()

        async def run(self, input, mission_id):
            return w2mod.run_workshop2(input, FakeWorkshop2Runner(), self._base)

    class Workshop3RunnerFake(Workshop3Runner):
        def __init__(self):
            super().__init__(io_in=lambda p: "1", io_out=print)  # "1" = premiere option (run)

        async def run(self, input, mission_id):
            from ebios_rm.workshops.workshop3_scenarios_strategiques.workshop import run_workshop3
            output = run_workshop3(input, FakeWorkshop3Runner())
            gate = w3mod.gate_for(output.scenarios, n_initial=len(output.scenarios))
            if not gate.options_offertes:
                return output
            from ebios_rm.workshops.workshop3_scenarios_strategiques.models import ACTION_RUN
            decided = gate.model_copy(update={"action": ACTION_RUN})
            return w3mod.assemble_output(input, output.scenarios, decided, output.elements_ecartes)

    class FakeWorkshop4AgentRunner:
        async def analyse_scenario(self, w4_input, pending, catalogue):
            real = next(t for t in catalogue.techniques.values() if "initial-access" in t.tactics)
            return ScenarioAnalysisProposal(
                resume="Accès via télémaintenance, chiffrement du SIH.",
                attack_path=[
                    AttackStepProposal(tactic="initial-access", technique_id=real.technique_id,
                                        technique_name=real.name, description="Hameçonnement.",
                                        bien_support_id="BS-1", justification="Contexte."),
                    AttackStepProposal(tactic="impact", description="Chiffrement du SIH.",
                                        bien_support_id="BS-1", justification="Atteint ER-1."),
                ],
                likelihood_revision_reason="Aucune MFA, vecteur confirmé.",
                revised_likelihood="V4",
            )

        def check_coherence(self, w4_input, scenarios):
            return CoherenceBatch(constats=[]).constats

    class FakeWorkshop5AgentRunner:
        def propose_mesures(self, w5_input, mitigations):
            scenario = w5_input.scenarios[0]
            technique_id = next((s.technique_id for s in scenario.attack_path if s.technique_id), None)
            mitigation_ids = list(mitigations.ids_for(technique_id))[:1] if technique_id else []
            return MesuresBatch(mesures=[
                MesureProposal(
                    description="Renforcer l'authentification sur l'accès de télémaintenance.",
                    scenarios_associes=[scenario.id],
                    mitigation_ids_attck=mitigation_ids,
                    cout="Faible", efficacite="Réduit fortement la probabilité d'accès initial.",
                    delai="Court terme", priorite="Élevée",
                )
            ])

    def io_in_auto(prompt: str) -> str:
        # Approuve tout, confirme toute analyse, aucune reprise.
        if "oui" in prompt.casefold() or "approuvez" in prompt.casefold():
            return "o"
        return ""

    orchestrator = Orchestrator(
        repo,
        {
            1: FakeWorkshop1(),
            2: Workshop2RunnerFake(),
            3: Workshop3RunnerFake(),
            4: Workshop4Runner(repo, runner=FakeWorkshop4AgentRunner(), io_in=io_in_auto, io_out=print),
            5: Workshop5Runner(repo, runner=FakeWorkshop5AgentRunner()),
        },
        approve=lambda summary: (True, ""),
    )

    print(f"Mission de test : {mission_id}\n")
    asyncio.run(orchestrator.run_mission(mission_id))

    mission = repo.get_mission(mission_id)
    print(f"\n=== Statut final de la mission : {mission.status} ===")
    for n, loader in [(1, mission_state.load_w1_output), (2, mission_state.load_w2_output),
                       (3, mission_state.load_w3_output), (4, mission_state.load_w4_output),
                       (5, mission_state.load_w5_output)]:
        out = loader(repo, mission_id)
        approved = mission_state.is_approved(repo, mission_id, n)
        print(f"  Atelier {n} : {'approuvé' if approved else 'PAS approuvé'} — {out is not None and 'sauvegardé' or 'absent'}")
        if n == 5 and out is not None:
            print(f"    -> {len(out.mesures)} mesure(s) de traitement, contrôle qualité : {out.quality_report.statut}")

    return 0 if mission.status == state_machine.approved(5) else 1


def _load_base():
    from ebios_rm.plugins.registry import load_ebios_base
    return load_ebios_base()


if __name__ == "__main__":
    raise SystemExit(main())
