"""Typed input/output for Workshop 3 — scénarios stratégiques (conception §14, §17).

Three families, same shape as atelier 2:
  * ``Workshop3Input`` — the narrow, justified input atelier 3 is allowed to see.
    Built by workshop.py from the Mission Context, the atelier 1 output and the
    *approved* atelier 2 output.
  * Proposal models — what the LLM returns on each of the two passes (propose,
    then critique), structured output only.
  * Output models — the validated w3_output: the scenarios, the count-gate
    decision, everything discarded with its reason, and the quality report.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebios_rm.domain.essential_asset import EssentialAsset
from ebios_rm.domain.fact import Fact
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.domain.risk_source import CoupleSROV, ObjectifVise, RiskSource
from ebios_rm.domain.strategic_scenario import StrategicScenario

# The quality report shape is atelier 2's, reused rather than restated. ponytail:
# one definition, imported across the two workshops; move it to domain/ when a
# third one needs it.
from ebios_rm.workshops.workshop2_sources_risque.models import (
    STATUT_AVERTISSEMENT,
    STATUT_ERREUR,
    STATUT_OK,
    QualityCheck,
    QualityReport,
)



# --- Input contract --------------------------------------------------------

# The Mission Context fields atelier 3 may read, and only those. Atelier 3 asks by
# which route a source de risque would reach this organisation, so the contract is
# the ecosystem: who is already connected, how far in they are, and what the study
# covers.
#
# What is deliberately absent, and must stay absent: baseline_gaps_full and
# unverified_controls (a weakness answers *would the attack work*, which is
# atelier 4's question), the atelier 2 elements_ecartes, quality_report and
# human_edits, and every superseded version of anything. Atelier 3 reads the
# approved result of the ateliers before it, not their history.
CONTEXT_FIELDS: tuple[str, ...] = (
    # framing
    "activites_description",
    "perimetre_inclus",
    "perimetre_exclu",
    "perimetre_geographique",
    "objectifs_etude",
    "processus_metier_critiques",
    # the ecosystem itself — the parties a scenario can route through
    "fournisseurs_tiers_critiques",
    "fournisseurs_cloud",
    "interconnexions_tiers",
    "infogerance",
    "sous_traitants_donnees",
    "clauses_securite_contrats",
    # how the outside reaches in
    "exposition_internet",
    "acces_distant_moyens",
    "teletravail_autorise",
    # what the ecosystem is worth trusting with
    "maturite_securite",
    "certifications_obtenues",
    "audits_anterieurs",
    # what has already been seen, and what the client expects
    "incidents_securite_passes",
    "sources_menace_percues",
    "chemin_attaque_probable",
)


class Atelier2Alert(BaseModel):
    """A defect found in the atelier 2 output, raised for the auditor, never repaired.

    Same rule as atelier 2 applies to atelier 1 (white-box §4): « erreur de donnée
    n'est pas erreur de raisonnement ». A couple pointing at a source de risque
    that does not exist is fixed in atelier 2, not quietly worked around here.
    """

    reference: str
    probleme: str
    bloquant: bool = True


class Workshop3Input(BaseModel):
    """Everything atelier 3 may see, and nothing else (conception §17).

    Narrow means justified, not minimal: a scenario cannot be told without the
    source, the objective, the assets at stake and the ecosystem it travels
    through, so all four travel — the *approved* versions of them, once.
    """

    organisation_nom: str
    secteur_activite: str

    contexte: dict[str, object] = Field(default_factory=dict)

    # Atelier 2, filtered to what a scenario is built from: the retained couples
    # and the sources and objectives they actually reference.
    couples: list[CoupleSROV] = Field(default_factory=list)
    sources_risque: list[RiskSource] = Field(default_factory=list)
    objectifs_vises: list[ObjectifVise] = Field(default_factory=list)

    # Atelier 1, for the stake a scenario ends on: which assets, and how bad.
    biens_essentiels: list[EssentialAsset] = Field(default_factory=list)
    evenements_redoutes: list[FearedEvent] = Field(default_factory=list)

    # The Facts behind ``contexte``, provenance intact (§8).
    faits_contexte: list[Fact] = Field(default_factory=list)

    alertes_atelier2: list[Atelier2Alert] = Field(default_factory=list)

    @property
    def alertes_bloquantes(self) -> list[Atelier2Alert]:
        return [a for a in self.alertes_atelier2 if a.bloquant]


# --- LLM proposal models (structured output) -------------------------------

class ScenarioProposal(BaseModel):
    """One candidate scenario, pass 1 (§17 « propose »).

    Field order is the generation order: the route and its justification are
    written before anything that reads as a conclusion.
    """

    couple_id: str  # must be a retained atelier 2 couple — checked in code
    resume: str = ""
    parties_prenantes: list[str] = Field(default_factory=list)
    justification: str = ""
    derived_from_fact_fields: list[str] = Field(default_factory=list)


class ScenarioBatch(BaseModel):
    scenarios: list[ScenarioProposal] = Field(default_factory=list)


class CritiqueVerdict(BaseModel):
    """One verdict of pass 2 (§17 « critique »): keep this scenario, or fold it into another.

    ``doublon_de`` empty means keep. Non-empty names the scenario this one repeats,
    and the reason is mandatory — a scenario is never dropped silently (§19).
    """

    scenario_id: str
    raison: str = ""
    doublon_de: str = ""


class CritiqueBatch(BaseModel):
    verdicts: list[CritiqueVerdict] = Field(default_factory=list)


# --- Discarded elements: never dropped, always with their reason ------------

REASON_COUPLE_INCONNU = "couple_inconnu"
REASON_SANS_JUSTIFICATION = "sans_justification"
REASON_SANS_ANCRAGE_CONTEXTE = "sans_ancrage_contexte"
REASON_PARTIE_PRENANTE_INCONNUE = "partie_prenante_inconnue"
REASON_DOUBLON = "doublon"
REASON_QUASI_DOUBLON = "quasi_doublon"
REASON_FUSIONNE = "fusionne"
REASON_HORS_SOUS_ENSEMBLE = "hors_sous_ensemble"
REASON_ECARTE_PAR_AUDITEUR = "ecarte_par_auditeur"
REASON_NON_TRAITE = "non_traite"

ECARTE_REASON_LABELS = {
    REASON_COUPLE_INCONNU: "Couple SR/OV inconnu ou non retenu en atelier 2",
    REASON_SANS_JUSTIFICATION: "Aucune justification fournie",
    REASON_SANS_ANCRAGE_CONTEXTE: "Aucun élément de contexte cité à l'appui",
    REASON_PARTIE_PRENANTE_INCONNUE: "Partie prenante absente du contexte de la mission",
    REASON_DOUBLON: "Deuxième scénario sur le même couple SR/OV",
    REASON_QUASI_DOUBLON: "Quasi-doublon écarté par la passe de critique",
    REASON_FUSIONNE: "Fusionné dans un autre scénario au point de comptage",
    REASON_HORS_SOUS_ENSEMBLE: "Hors du sous-ensemble retenu au point de comptage",
    REASON_ECARTE_PAR_AUDITEUR: "Couple écarté par l'auditeur avant la génération",
    REASON_NON_TRAITE: "Aucun scénario proposé par l'agent pour ce couple",
}


class ElementEcarte(BaseModel):
    """A candidate that did not make it, with why (§19)."""

    type: str = "scenario"
    reference: str
    libelle: str = ""
    raison: str = REASON_QUASI_DOUBLON
    detail: str = ""

    @property
    def raison_label(self) -> str:
        return ECARTE_REASON_LABELS.get(self.raison, self.raison)


# --- The count gate (§17) --------------------------------------------------

ACTION_RUN = "run"
ACTION_RUN_ANYWAY = "run_anyway"
ACTION_MERGE = "merge"
ACTION_CHOOSE_SUBSET = "choose_subset"
ACTION_CANCEL = "cancel"


class GateDecision(BaseModel):
    """What was decided about the scenario count, and why (§17 steps 19-21).

    Recorded in the output, not only in the decision log: atelier 4's size is this
    number, and a reader must be able to see whether the list they are looking at
    is the one the agent produced or one the auditor reduced.
    """

    n: int = 0                 # the count the decision was taken on
    n_initial: int = 0         # before any merge or subset
    action: str = ACTION_RUN
    justification: str = ""
    options_offertes: list[str] = Field(default_factory=list)
    estimation_appels_llm: int = 0
    estimation_secondes: float = 0.0


# --- Validated output ------------------------------------------------------

class Workshop3Output(BaseModel):
    """w3_output (conception §17).

    ``scenarios`` is the list atelier 4 fans out over: approved, final, and not
    re-validated downstream.
    """

    scenarios: list[StrategicScenario] = Field(default_factory=list)
    gate_decision: GateDecision = Field(default_factory=GateDecision)
    elements_ecartes: list[ElementEcarte] = Field(default_factory=list)
    quality_report: QualityReport = Field(default_factory=QualityReport)
    alertes_atelier2: list[Atelier2Alert] = Field(default_factory=list)
    human_edits: list[dict] = Field(default_factory=list)
