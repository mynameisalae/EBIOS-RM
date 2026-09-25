"""Typed input/output for Workshop 5 — traitement du risque (conception §14, §19; méthode atelier 5).

The five activities of the method, in order, and what each produces:
  5-1  the risks, formulated in business words, placed on the gravité x vraisemblance
       map, and the coverage check against atelier 1's feared events;
  5-2  the acceptability of each risk and the treatment option the auditor decides;
  5-3  the security measures, grouped in the four axes of the treatment plan;
  5-4  the residual risks, once the plan is counted, formally accepted;
  5-5  the monitoring framework — indicators, committee, review cycles.

Same three families as the other ateliers: the narrow input, the proposal models the
LLM fills, and the validated output.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from ebios_rm.domain.essential_asset import EssentialAsset, SupportAsset
from ebios_rm.domain.fact import Fact
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.domain.operational_scenario import OperationalScenario
from ebios_rm.domain.risk_scenario import CadreSuivi, MesureSecurite, RiskScenario
from ebios_rm.domain.risk_source import ObjectifVise, RiskSource
from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.workshops.common import AtelierAlert, ElementEcarteBase
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap
from ebios_rm.workshops.workshop2_sources_risque.models import (  # noqa: F401 — re-exported
    STATUT_AVERTISSEMENT,
    STATUT_ERREUR,
    STATUT_OK,
    QualityCheck,
    QualityReport,
)

# --- Input contract --------------------------------------------------------

# What atelier 5 reads from the Mission Context. Not the technical posture — atelier 4
# already answered whether an attack works — but what decides whether a measure is
# realistic here and who will carry it: maturity, governance, size, deadlines,
# obligations, what is already in place, and what the session adds about thresholds,
# budget and the committee.
CONTEXT_FIELDS: tuple[str, ...] = (
    # who decides and with what means
    "gouvernance_securite",
    "maturite_securite",
    "taille_effectif",
    "objectifs_etude",
    "perimetre_inclus",
    "contraintes_calendrier",
    "obligations_metier",
    "analyse_risques_existante",
    "certifications_obtenues",
    "audits_anterieurs",
    # what already exists, so a measure is not proposed twice
    "sensibilisation",
    "supervision_securite",
    "plan_reponse_incident",
    "sauvegarde_strategie",
    "plan_reprise_informatique",
    "plan_continuite_metier",
    "rto_rpo",
    "chiffrement_donnees",
    # the ecosystem a measure may have to be contracted with
    "fournisseurs_tiers_critiques",
    "infogerance",
    "clauses_securite_contrats",
    "sous_traitants_donnees",
    # asked in the atelier 5 session itself (questions.py)
    "seuil_acceptation_risque",
    "moyens_traitement",
    "responsables_mesures",
    "cadence_comite_securite",
)

# The expert follow-ups of the atelier 1 intake travel here too: they hold the detail a
# measure has to fit (a backup with no integrity check, a liaison nobody documented).
EXPERT_QUESTION_PREFIX = "AUD-"

# Sub-themes of the four axes of the treatment plan, as the method lists them. Offered
# to the model as the vocabulary to file a measure under, and used to check what it
# hands back — a plan whose axes are invented cannot be compared to the next study's.
THEMATIQUES: dict[str, tuple[str, ...]] = {
    "gouvernance": (
        "organisation du management du risque et amélioration continue",
        "processus d'homologation",
        "maîtrise de l'écosystème",
        "gestion du facteur humain (sensibilisation, entraînement)",
        "indicateurs de pilotage",
        "connaissance des vulnérabilités (audits, veille)",
        "connaissance de la menace (veille)",
    ),
    "protection": (
        "cloisonnement par domaines de confiance",
        "authentification et contrôle d'accès",
        "administration et supervision",
        "entrées/sorties de données et supports amovibles",
        "protection des données (intégrité, confidentialité, clés)",
        "sécurité des passerelles et des biens supports de frontière",
        "sécurité physique et organisationnelle",
        "maintien en condition de sécurité et obsolescence",
        "sécurité du développement, des acquisitions et de la chaîne d'approvisionnement",
    ),
    "defense": (
        "surveillance d'événements",
        "détection et classification d'incidents",
        "réponse à un incident de cybersécurité",
    ),
    "resilience": (
        "continuité d'activité (sauvegarde, restauration, modes dégradés)",
        "reprise d'activité",
        "gestion de crise cyber",
        "plan de formation",
        "plan d'exercice et de test",
    ),
}

# Where a measure comes from. The plan gathers all three (méthode, atelier 5-3).
ORIGINE_SOCLE = "atelier1_socle"              # closes a baseline gap
ORIGINE_ECOSYSTEME = "atelier3_ecosysteme"    # lowers a stakeholder's threat level
ORIGINE_VULNERABILITE = "atelier4_vulnerabilite"  # breaks a step of an operating mode
ORIGINES = (ORIGINE_SOCLE, ORIGINE_ECOSYSTEME, ORIGINE_VULNERABILITE)

# Cost / complexity, as the plan writes it.
COUTS = ("+", "++", "+++")


class Workshop5Input(BaseModel):
    """Everything atelier 5 may see (méthode atelier 5 « éléments en entrée »).

    The method's inputs are the security baseline (atelier 1), the ecosystem measures
    and strategic scenarios (atelier 3) and the operational scenarios (atelier 4).

    Unlike atelier 4, the baseline gaps arrive whole — framework and control id
    included. Atelier 4 had to judge an attack without knowing which standard named a
    weakness (§12.3); atelier 5 writes the plan that closes those gaps, and a plan
    that cannot say which requirement it satisfies is not auditable.
    """

    organisation_nom: str
    secteur_activite: str

    contexte: dict[str, object] = Field(default_factory=dict)
    faits_contexte: list[Fact] = Field(default_factory=list)

    # Atelier 4: every developed mode opératoire, the driving one flagged (retenu).
    modes_operatoires: list[OperationalScenario] = Field(default_factory=list)
    # Atelier 3, for the route a risk is told through.
    scenarios_strategiques: list[StrategicScenario] = Field(default_factory=list)
    # Atelier 2, for who the attacker is and what they are after.
    sources_risque: list[RiskSource] = Field(default_factory=list)
    objectifs_vises: list[ObjectifVise] = Field(default_factory=list)
    # Atelier 1.
    biens_essentiels: list[EssentialAsset] = Field(default_factory=list)
    biens_supports: list[SupportAsset] = Field(default_factory=list)
    evenements_redoutes: list[FearedEvent] = Field(default_factory=list)
    baseline_gaps: list[BaselineGap] = Field(default_factory=list)

    alertes_atelier4: list[AtelierAlert] = Field(default_factory=list)

    @property
    def alertes_bloquantes(self) -> list[AtelierAlert]:
        return [a for a in self.alertes_atelier4 if a.bloquant]


# --- LLM proposal models (structured output) -------------------------------

class RiskFormulationProposal(BaseModel):
    """How one risk reads for a decision-maker (atelier 5-1)."""

    risque_id: str = ""
    libelle: str = ""


class RiskFormulationBatch(BaseModel):
    formulations: list[RiskFormulationProposal] = Field(default_factory=list)


class MeasureProposal(BaseModel):
    """One candidate measure of the treatment plan (atelier 5-3).

    Field order is the generation order: what it acts on before what it costs, and the
    justification before the effect claimed on the likelihood.
    """

    axe: str = ""
    thematique: str = ""
    libelle: str = ""
    description: str = ""
    risques_ids: list[str] = Field(default_factory=list)
    modes_ids: list[str] = Field(default_factory=list)
    etapes_visees: list[str] = Field(default_factory=list)
    gap_ids: list[str] = Field(default_factory=list)
    mitigation_ids_attck: list[str] = Field(default_factory=list)
    origine: str = ""
    freins: str = ""
    cout_complexite: str = ""
    charge_estimee: str = ""
    echeance: str = ""
    justification: str = ""
    effet_vraisemblance: int = 0


class MeasureBatch(BaseModel):
    mesures: list[MeasureProposal] = Field(default_factory=list)


class ResidualProposal(BaseModel):
    """The likelihood of one risk once the retained measures are in place (atelier 5-4)."""

    risque_id: str = ""
    motif: str = ""
    vraisemblance_residuelle: str = ""


class ResidualBatch(BaseModel):
    risques: list[ResidualProposal] = Field(default_factory=list)


class IndicatorProposal(BaseModel):
    """One steering indicator of the monitoring framework (atelier 5-5)."""

    libelle: str = ""
    type_valeur: str = ""      # cout | duree | nombre | taux
    cible: str = ""
    frequence: str = ""
    mesures_ids: list[str] = Field(default_factory=list)


class IndicatorBatch(BaseModel):
    indicateurs: list[IndicatorProposal] = Field(default_factory=list)


# --- Discarded elements: never dropped, always with their reason ------------

REASON_MESURE_SANS_LIEN = "mesure_sans_lien"
REASON_MESURE_AXE_INCONNU = "mesure_axe_inconnu"
REASON_MESURE_RISQUE_INCONNU = "mesure_risque_inconnu"
REASON_MESURE_DOUBLON = "mesure_doublon"
REASON_MESURE_ECARTEE_PAR_AUDITEUR = "mesure_ecartee_par_auditeur"
REASON_RESIDUEL_INCONNU = "residuel_risque_inconnu"
REASON_RESIDUEL_SANS_MESURE = "residuel_sans_mesure"
REASON_RESIDUEL_AGGRAVE = "residuel_aggrave"
REASON_INDICATEUR_NON_MESURABLE = "indicateur_non_mesurable"

ECARTE_REASON_LABELS = {
    REASON_MESURE_SANS_LIEN: "Mesure ne traitant aucun risque, aucune étape et aucun écart du socle",
    REASON_MESURE_AXE_INCONNU: "Mesure rangée sous un axe absent du plan de traitement",
    REASON_MESURE_RISQUE_INCONNU: "Mesure citant un risque qui n'existe pas",
    REASON_MESURE_DOUBLON: "Mesure reprenant une mesure déjà retenue",
    REASON_MESURE_ECARTEE_PAR_AUDITEUR: "Mesure écartée par l'auditeur",
    REASON_RESIDUEL_INCONNU: "Évaluation résiduelle citant un risque qui n'existe pas",
    REASON_RESIDUEL_SANS_MESURE: "Vraisemblance résiduelle abaissée sans aucune mesure retenue",
    REASON_RESIDUEL_AGGRAVE: "Vraisemblance résiduelle supérieure à la vraisemblance initiale",
    REASON_INDICATEUR_NON_MESURABLE: "Indicateur sans valeur mesurable (coût, durée, nombre ou taux)",
}


class ElementEcarte(ElementEcarteBase):
    """Something that did not make it into w5_output, with why (§16, §19)."""

    LABELS: ClassVar[dict[str, str]] = ECARTE_REASON_LABELS


# --- The coverage check of activity 5-1 -------------------------------------

class CouvertureER(BaseModel):
    """Whether a feared event of atelier 1 ended up in a risk scenario (atelier 5-1).

    The method's own completeness check: a serious or critical feared event covered by
    no risk means ateliers 2 to 4 have to be iterated, not that the study is finished.
    """

    evenement_redoute_id: str
    description: str = ""
    gravite: str = ""
    risques_ids: list[str] = Field(default_factory=list)

    @property
    def couvert(self) -> bool:
        return bool(self.risques_ids)


# --- Validated output ------------------------------------------------------

# The activities whose model call has already been paid for. Read back on resume so a
# run that stops between two of them does not buy the same answer twice — and so an
# activity that legitimately produced nothing (a plan with no measure kept) is not
# mistaken for an activity that never ran.
ACTIVITE_FORMULATION = "5-1"
ACTIVITE_MESURES = "5-3"
# Set by the auditor, not by a call: the plan as it stands is the one they reviewed.
ACTIVITE_PLAN_VALIDE = "5-3-plan-valide"


class Workshop5Output(BaseModel):
    """w5_output — the five deliverables of atelier 5 in one object."""

    risques: list[RiskScenario] = Field(default_factory=list)
    mesures: list[MesureSecurite] = Field(default_factory=list)
    couverture_er: list[CouvertureER] = Field(default_factory=list)
    cadre_suivi: CadreSuivi | None = None
    elements_ecartes: list[ElementEcarte] = Field(default_factory=list)
    quality_report: QualityReport = Field(default_factory=QualityReport)
    alertes_atelier4: list[AtelierAlert] = Field(default_factory=list)
    attck_version: str = ""
    activites_faites: list[str] = Field(default_factory=list)
    human_edits: list[dict] = Field(default_factory=list)
