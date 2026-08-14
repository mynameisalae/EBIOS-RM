"""Typed input/output for Workshop 2 — sources de risque (white-box §3, §19, §20).

Three families:
  * ``Workshop2Input`` — the *narrow, justified* input the workshop is allowed to
    see (white-box §3). Built by build_input.py from the Mission Context and the
    atelier 1 output; nothing else may reach the model.
  * Proposal models — what the LLM returns (structured output, never tool calls).
  * Output models — the validated w2_output emitted after the deterministic
    filters, the couple construction, the priorisation and the quality check.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebios_rm.domain.essential_asset import EssentialAsset, SupportAsset
from ebios_rm.domain.fact import Fact
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.domain.risk_source import CoupleSROV, ObjectifVise, RiskSource


# --- Input (white-box §3) ---

# The Mission Context fields atelier 2 is allowed to read, and only those. This
# tuple *is* the input contract: exposure and attractiveness, which is what
# plausibility rests on.
#
# What is deliberately absent, and must stay absent: baseline_gaps_full,
# unverified_controls, human_edits. A gap is a weakness — "pas de MFA sur les
# accès distants". Weaknesses answer *would an attacker succeed*; atelier 2 asks
# *who would want to attack us, and what for*. Feed a model a list of weaknesses
# and it hands back "vol d'identifiants" and "exploitation de faille" — techniques
# wearing the costume of sources de risque, which white-box §17 forbids outright.
# The gaps already have their destination: atelier 4.
CONTEXT_FIELDS: tuple[str, ...] = (
    "activites_description",
    "perimetre_inclus",
    "perimetre_exclu",
    "objectifs_etude",
    "processus_metier_critiques",
    "informations_sensibles",
    "valeurs_prioritaires",
    "obligations_metier",
    "exposition_internet",
    "interconnexions_tiers",
    "fournisseurs_tiers_critiques",
    "infogerance",
    "sources_menace_percues",
    "chemin_attaque_probable",
    "incidents_securite_passes",
    "perimetre_geographique",
    "taille_effectif",
    "certifications_obtenues",
    # Asked during the atelier 2 session itself (questions.py) — they have no
    # equivalent in the intake questionnaire because only atelier 2 needs them.
    "concurrence_directe",
    "departs_conflictuels",
    "visibilite_publique",
)


class Atelier1Alert(BaseModel):
    """A defect found in the atelier 1 output (white-box §4).

    Raised for the auditor, never repaired by the model: « erreur de donnée
    n'est pas erreur de raisonnement ».
    """

    reference: str   # the id or field the problem concerns
    probleme: str
    bloquant: bool = True


class Workshop2Input(BaseModel):
    """Everything atelier 2 may see, and nothing else (white-box §3).

    Narrow means *justified*, not minimal: you cannot judge whether a state actor
    is plausible without the organisation's activity, perimeter and exposure.
    """

    organisation_nom: str
    secteur_activite: str

    # Organisational context / perimeter / stakeholders / constraints (§3), each
    # one a CONTEXT_FIELDS entry that the Mission Context actually held.
    contexte: dict[str, object] = Field(default_factory=dict)

    # Atelier 1 output, minus everything atelier 2 has no business seeing.
    biens_essentiels: list[EssentialAsset] = Field(default_factory=list)
    biens_supports: list[SupportAsset] = Field(default_factory=list)
    evenements_redoutes: list[FearedEvent] = Field(default_factory=list)

    # The Facts behind ``contexte``, provenance intact, plus any answer given
    # during the atelier 2 session (questions.py). Facts and assumptions must stay
    # distinguishable all the way into the SR/OV justifications (white-box §8).
    faits_contexte: list[Fact] = Field(default_factory=list)

    # Defects found in the atelier 1 output while building this input (§4).
    alertes_atelier1: list[Atelier1Alert] = Field(default_factory=list)

    @property
    def alertes_bloquantes(self) -> list[Atelier1Alert]:
        return [a for a in self.alertes_atelier1 if a.bloquant]


# --- LLM proposal models (structured output) ---

class RiskSourceProposal(BaseModel):
    """One candidate source de risque, as the model proposes it (white-box §6, §7)."""

    categorie_id: str            # must exist in the approved base — checked in code (§6)
    nom: str
    description: str = ""
    motivation: str = ""
    statut: str = "retenu"       # 'retenu' | 'secondaire' | 'ecarte'
    justification: str = ""      # why plausible in THIS context — non-empty or écarté
    derived_from_fact_fields: list[str] = Field(default_factory=list)


class RiskSourceBatch(BaseModel):
    sources: list[RiskSourceProposal] = Field(default_factory=list)


class ObjectifViseProposal(BaseModel):
    """One candidate objectif visé (white-box §9, §10)."""

    finalite_id: str             # must exist in the approved base
    description: str
    enjeu: str = ""
    biens_essentiels_vises: list[str] = Field(default_factory=list)
    statut: str = "retenu"
    justification: str = ""
    derived_from_fact_fields: list[str] = Field(default_factory=list)


class ObjectifViseBatch(BaseModel):
    objectifs: list[ObjectifViseProposal] = Field(default_factory=list)


class CoupleProposal(BaseModel):
    """One SR/OV couple the model judges coherent, with its rated judgments (§11, §13).

    motivation/ressources/activite are ratings on 1..4; the pertinence and the
    initial likelihood are computed from them in code — the model never invents a
    score, a scale or a formula (§17).
    """

    source_risque_id: str
    objectif_vise_id: str
    justification: str = ""
    motivation: int = 0
    ressources: int = 0
    activite: int = 0
    statut: str = "retenu"


class CoupleBatch(BaseModel):
    couples: list[CoupleProposal] = Field(default_factory=list)


# --- Discarded elements: never dropped, always with their reason (§17, §19) ---

REASON_HORS_CATALOGUE = "hors_catalogue"
REASON_SANS_JUSTIFICATION = "sans_justification"
REASON_SANS_ANCRAGE_CONTEXTE = "sans_ancrage_contexte"
REASON_PAS_UN_ACTEUR = "pas_un_acteur"
REASON_TECHNIQUE_PAS_OBJECTIF = "technique_pas_objectif"
REASON_BIEN_ESSENTIEL_INCONNU = "bien_essentiel_inconnu"
REASON_DOUBLON = "doublon"
REASON_REFERENCE_INVALIDE = "reference_invalide"
REASON_EXTREMITE_NON_RETENUE = "extremite_non_retenue"
REASON_SCORES_INVALIDES = "scores_invalides"
REASON_ECARTE_PAR_AGENT = "ecarte_par_agent"

ECARTE_REASON_LABELS = {
    REASON_HORS_CATALOGUE: "Catégorie absente de la base EBIOS RM approuvée",
    REASON_SANS_JUSTIFICATION: "Aucune justification fournie",
    REASON_SANS_ANCRAGE_CONTEXTE: "Aucun élément de contexte cité à l'appui",
    REASON_PAS_UN_ACTEUR: "Formulation décrivant un bien ou une vulnérabilité, pas un acteur",
    REASON_TECHNIQUE_PAS_OBJECTIF: "Formulation décrivant une technique, pas un objectif visé",
    REASON_BIEN_ESSENTIEL_INCONNU: "Bien essentiel visé inconnu de l'atelier 1",
    REASON_DOUBLON: "Doublon d'un élément déjà retenu",
    REASON_REFERENCE_INVALIDE: "Référence inconnue (source de risque ou objectif visé)",
    REASON_EXTREMITE_NON_RETENUE: "Source de risque ou objectif visé non retenu",
    REASON_SCORES_INVALIDES: "Cotation hors échelle (motivation / ressources / activité sur 1 à 4)",
    REASON_ECARTE_PAR_AGENT: "Écarté par l'agent, avec justification",
}


class ElementEcarte(BaseModel):
    """A candidate that did not make it, with why (white-box §17, §19, §20).

    Deleting a discarded element without recording the reason is a forbidden
    design error: the auditor must be able to see what was considered and rejected.
    """

    type: str        # 'source_risque' | 'objectif_vise' | 'couple'
    reference: str   # id when it had one, otherwise the proposed label
    libelle: str = ""
    raison: str = REASON_ECARTE_PAR_AGENT
    detail: str = ""

    @property
    def raison_label(self) -> str:
        return ECARTE_REASON_LABELS.get(self.raison, self.raison)


# --- Quality checker (white-box §14) ---

STATUT_OK = "ok"
STATUT_AVERTISSEMENT = "avertissement"
STATUT_ERREUR = "erreur"


class QualityCheck(BaseModel):
    """One control of the independent quality checker (white-box §14)."""

    controle: str
    statut: str = STATUT_OK
    message: str = ""


class QualityReport(BaseModel):
    """The quality checker's verdict — an output blocks on 'erreur' (white-box §14, §19)."""

    checks: list[QualityCheck] = Field(default_factory=list)

    @property
    def erreurs(self) -> list[QualityCheck]:
        return [c for c in self.checks if c.statut == STATUT_ERREUR]

    @property
    def avertissements(self) -> list[QualityCheck]:
        return [c for c in self.checks if c.statut == STATUT_AVERTISSEMENT]

    @property
    def statut(self) -> str:
        if self.erreurs:
            return STATUT_ERREUR
        if self.avertissements:
            return STATUT_AVERTISSEMENT
        return "valide"


# --- Validated output (white-box §19) ---

class Workshop2Output(BaseModel):
    """w2_output (white-box §19, §20)."""

    sources_risque: list[RiskSource] = Field(default_factory=list)
    objectifs_vises: list[ObjectifVise] = Field(default_factory=list)
    couples: list[CoupleSROV] = Field(default_factory=list)
    couples_secondaires: list[CoupleSROV] = Field(default_factory=list)
    elements_ecartes: list[ElementEcarte] = Field(default_factory=list)
    quality_report: QualityReport = Field(default_factory=QualityReport)
    alertes_atelier1: list[Atelier1Alert] = Field(default_factory=list)
    # Corrections the auditor made directly on this output (conception §2, §8) —
    # same shape as workshop 1, carried verbatim across a partial redo.
    human_edits: list[dict] = Field(default_factory=list)
