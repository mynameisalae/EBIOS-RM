# -*- coding: utf-8 -*-
"""Palier 4 : elargit l'echantillon reel de l'Atelier 4 a plusieurs scenarios
(au lieu d'un seul au palier 3), pour mesurer la frequence reelle des erreurs
de tactique ATT&CK plutot que de conclure sur un seul essai.

Les Ateliers 1, 2 et 3 restent factices/fixtures (deja documentes par
ailleurs) ; seul l'Atelier 4 fait de vrais appels, un par scenario, via le
fan-out deja existant du code.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests" / "workshops"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ebios_rm.agent_runtime import set_token_sink
from ebios_rm.config import load_settings
from ebios_rm.domain.enums import CategorieImpact, Gravite, Origin, Pertinence, StatutSelection, VraisemblanceInitiale
from ebios_rm.domain.essential_asset import EssentialAsset, SupportAsset
from ebios_rm.domain.fact import Fact
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.domain.risk_source import CoupleSROV, ObjectifVise, RiskSource
from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.orchestrator import mission_state
from ebios_rm.orchestrator.workshop4_flow import run_workshop4
from ebios_rm.repositories.attack_repository import AttackRepository, connect_readonly
from ebios_rm.repositories.mission_repository import MissionRepository, connect
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Output
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import Workshop3Output
from ebios_rm.workshops.workshop4_scenarios_operationnels.agent import AgnoWorkshop4Runner

MISSION_CONTEXT = MissionContext(
    organisation_nom="Clinique Test", secteur_activite="Santé",
    applicable_frameworks=["ANSSI_hygiene"],
    facts=[
        Fact.declaration("systeme_information_resume", "SIH central + portail patient exposé"),
        Fact.declaration("exposition_internet", "Portail de prise de rendez-vous en ligne"),
        Fact.declaration("interconnexions_tiers", "Liaison de télémaintenance avec l'éditeur du SIH"),
        Fact.declaration("authentification_forte", "Aucune, mot de passe seul"),
        Fact.declaration("journalisation", "Logs applicatifs non centralisés"),
        Fact.declaration("acces_distant_moyens", "VPN sans MFA pour le personnel administratif"),
        Fact.declaration("mobiles_byod", "Aucune gestion centralisée des terminaux mobiles"),
        Fact.declaration("securite_physique", "Badge d'accès, contrôle non audité depuis 2 ans"),
    ],
)

W1_OUTPUT = Workshop1Output(
    biens_essentiels=[EssentialAsset(id="BE-1", nom="Dossier patient", description="Données de santé",
                                      nature="information", processus_metier_associes=["Prise en charge"],
                                      origin=Origin.ASSESSMENT, derived_from_fact_fields=["systeme_information_resume"])],
    biens_supports=[SupportAsset(id="BS-1", nom="SIH", description="Système d'information hospitalier",
                                  type_support="application", biens_essentiels_supportes=["BE-1"],
                                  origin=Origin.ASSESSMENT, derived_from_fact_fields=["systeme_information_resume"])],
    evenements_redoutes=[FearedEvent(id="ER-1", description="Indisponibilité du dossier patient", bien_essentiel_id="BE-1",
                                      categorie_impact=CategorieImpact.FONCTIONNEMENT, gravite=Gravite.CRITIQUE,
                                      origin=Origin.ASSESSMENT, derived_from_fact_fields=["exposition_internet"])],
)

W2_OUTPUT = Workshop2Output(
    sources_risque=[RiskSource(id="SR-01", categorie_id="crime_organise", categorie_libelle="Cybercriminel organisé",
                                nom="Groupe cybercriminel", motivation="Rançon", statut=StatutSelection.RETENU,
                                justification="Secteur ciblé.", derived_from_fact_fields=["exposition_internet"])],
    objectifs_vises=[ObjectifVise(id="OV-01", finalite_id="lucratif", finalite_libelle="Gain financier",
                                   description="Obtenir une rançon en bloquant la prise en charge",
                                   biens_essentiels_vises=["BE-1"], statut=StatutSelection.RETENU,
                                   justification="Dépendance forte.", derived_from_fact_fields=["exposition_internet"])],
    couples=[CoupleSROV(id="CPL-01", source_risque_id="SR-01", objectif_vise_id="OV-01",
                         biens_essentiels_ids=["BE-1"], valeurs_metier=["Prise en charge"],
                         biens_supports_associes=["BS-1"], motivation=4, ressources=3, activite=4,
                         pertinence=Pertinence.ELEVE, vraisemblance_initiale=VraisemblanceInitiale.V3,
                         statut=StatutSelection.RETENU, justification="Cohérent.")],
)

# Six angles d'attaque distincts sur les memes actifs, pour varier ce que le
# modele doit citer comme techniques -- c'est cette variation qui permet de
# mesurer une frequence d'erreur plutot qu'un seul point de donnees.
NARRATIVES = [
    "Le groupe cybercriminel exploite la liaison de télémaintenance de l'éditeur du SIH "
    "et chiffre les données pour exiger une rançon.",
    "Le groupe cybercriminel hameçonne un membre du personnel administratif pour voler "
    "ses identifiants VPN, dépourvus de MFA, et accède ainsi au SIH.",
    "Le groupe cybercriminel exploite une vulnérabilité connue non corrigée sur le portail "
    "de prise de rendez-vous exposé sur Internet pour obtenir un accès initial.",
    "Le groupe cybercriminel, après un accès initial, se déplace latéralement vers le SIH "
    "en profitant de l'absence de cloisonnement réseau et de la centralisation des logs.",
    "Le groupe cybercriminel compromet un compte à privilèges via le VPN sans MFA et "
    "exfiltre les données patients avant de les chiffrer.",
    "Le groupe cybercriminel obtient un accès physique via un contrôle de badge non audité "
    "et connecte un support amovible compromis sur un poste du SIH.",
]

W3_OUTPUT = Workshop3Output(scenarios=[
    StrategicScenario(
        id=f"SS-{i:02d}", source_risque_id="SR-01", objectif_vise_id="OV-01", couple_id="CPL-01",
        resume=narrative, justification="Cohérent avec le contexte déclaré.",
        parties_prenantes=["éditeur du SIH"] if i == 1 else [],
        biens_essentiels_ids=["BE-1"], evenements_redoutes_ids=["ER-1"],
        gravite=Gravite.CRITIQUE, pertinence=Pertinence.ELEVE,
    )
    for i, narrative in enumerate(NARRATIVES, 1)
])


def build_mission() -> tuple[str, MissionRepository]:
    db_path = "data/mission/test_palier4.db"
    Path(db_path).unlink(missing_ok=True)
    repo = MissionRepository(connect(db_path))
    mission_id = repo.create_mission("test_palier4_extended", ["ANSSI_hygiene"])

    mission_state.save_mission_context(repo, mission_id, MISSION_CONTEXT)
    v1 = mission_state.save_w1_output(repo, mission_id, W1_OUTPUT)
    repo.set_version_status(mission_id, mission_state.WORKSHOP_1, v1, "approved")
    v2 = mission_state.save_w2_output(repo, mission_id, W2_OUTPUT)
    repo.set_version_status(mission_id, mission_state.WORKSHOP_2, v2, "approved")
    v3 = mission_state.save_w3_output(repo, mission_id, W3_OUTPUT)
    repo.set_version_status(mission_id, mission_state.WORKSHOP_3, v3, "approved")
    repo.set_status(mission_id, "w3_approved")
    return mission_id, repo


def main() -> int:
    settings = load_settings()
    print(f"Modèle utilisé : {settings.model_id}")
    print(f"Nombre de scénarios : {len(NARRATIVES)}\n")

    mission_id, repo = build_mission()
    set_token_sink(lambda inp, out, model: repo.log_tokens(mission_id, input_tokens=inp, output_tokens=out, model_used=model))
    catalogue = AttackRepository(connect_readonly(settings.attack_db_path)).catalogue()

    # Script d'auto-confirmation : io_in ne recoit que "> " comme texte (le
    # vrai libelle de la question passe par io_out, pas par l'argument de
    # io_in) -- donc on capture les dernieres lignes ecrites par io_out et on
    # y lit quelle question est vraiment posee avant de repondre.
    # ask_choice fait plusieurs appels io_out (la question, puis chaque
    # option) avant de lire la reponse : on accumule tout depuis la derniere
    # lecture, pas seulement le tout dernier message.
    buffer = {"lines": []}

    def io_out_capture(msg: str) -> None:
        buffer["lines"].append(msg)
        print(msg)

    def io_in_auto(prompt: str) -> str:
        # approve_workshop() passe la question directement dans `prompt` (pas
        # via io_out d'abord) ; ask_choice(), lui, l'ecrit via io_out puis
        # n'envoie que "> " comme prompt -- d'ou les deux verifications.
        text = (prompt + "\n" + "\n".join(buffer["lines"])).casefold()
        buffer["lines"] = []
        if "approuvez-vous" in text:
            return "oui"
        if "que faire de ces constats" in text:
            return "a"
        return ""  # revue : [Entrée] = confirmer tout, rien a renvoyer

    code = run_workshop4(repo, mission_id, catalogue, AgnoWorkshop4Runner(),
                          human=None, clarifier=None, io_in=io_in_auto, io_out=io_out_capture)

    # --- Tally : frequence des anomalies liees a la tactique ---
    final = mission_state.load_w4_output(repo, mission_id)
    total_steps = 0
    tactic_errors = 0
    per_scenario = []
    for s in final.scenarios:
        total_steps += len(s.attack_path)
        errs = [a for a in s.anomalies if a.code in ("tactique_incoherente", "tactique_hors_catalogue", "tactique_inconnue")]
        tactic_errors += len(errs)
        per_scenario.append((s.id, len(s.attack_path), len(errs)))

    print("\n" + "=" * 70)
    print("RÉSULTAT — fréquence des erreurs de tactique ATT&CK")
    print("=" * 70)
    for sid, nsteps, nerr in per_scenario:
        print(f"  {sid} : {nerr} erreur(s) de tactique sur {nsteps} étape(s)")
    print(f"\nTotal : {tactic_errors} erreur(s) de tactique sur {total_steps} étapes citées "
          f"({len(final.scenarios)} scénarios)")
    if total_steps:
        print(f"Taux  : {100 * tactic_errors / total_steps:.0f} %")

    totals = repo.token_totals(mission_id)
    print(f"\nTokens consommés : {totals}")
    print(f"Statut final de la mission : {repo.get_mission(mission_id).status}")

    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
