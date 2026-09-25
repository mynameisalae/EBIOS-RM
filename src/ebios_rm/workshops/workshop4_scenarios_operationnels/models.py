"""Typed input/output for Workshop 4 — scénarios opérationnels (conception §14, §18).

Same three families as ateliers 2 and 3:
  * ``Workshop4Input`` — everything a sub-agent may see. Built by workshop.py from
    the Mission Context and the approved outputs of ateliers 1 to 3.
  * Proposal models — what one sub-agent returns for one scenario, and what the
    coherence pass returns over all of them. Structured output only.
  * Output models — the validated w4_output: one operational scenario per strategic
    scenario, the coherence review, what was set aside and why, the quality report.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from ebios_rm.domain.essential_asset import EssentialAsset, SupportAsset
from ebios_rm.domain.fact import Fact
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.domain.operational_scenario import OperationalScenario
from ebios_rm.domain.risk_source import ObjectifVise, RiskSource
from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.workshops.common import AtelierAlert, ElementEcarteBase
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGapForW4
from ebios_rm.workshops.workshop2_sources_risque.models import (  # noqa: F401 — re-exported
    STATUT_AVERTISSEMENT,
    STATUT_ERREUR,
    STATUT_OK,
    QualityCheck,
    QualityReport,
)

# --- Input contract --------------------------------------------------------

# The Mission Context fields atelier 4 may read. Atelier 4 asks whether an attack
# would work here, step by step, so the contract is the technical posture: what is
# exposed, how identities and privileges are held, what would detect or stop each
# step, and what survives the last one.
#
# Deliberately absent: applicable_frameworks and every certification field. Atelier
# 4 never learns the regulatory origin of a weakness (§12.3, §20.3) — the gaps reach
# it stripped of framework and control id, and the context must not put them back.
# The business-impact fields are absent too: the gravité is carried from atelier 1,
# not re-judged from the raw answers.
CONTEXT_FIELDS: tuple[str, ...] = (
    # what the attack is aimed at
    "systeme_information_resume",
    "applications_principales",
    "systemes_exploitation",
    "systemes_obsoletes",
    "developpement_logiciel",
    "hebergement",
    "fournisseurs_cloud",
    "perimetre_inclus",
    "perimetre_exclu",
    # how one gets in
    "exposition_internet",
    "acces_distant_moyens",
    "teletravail_autorise",
    "wifi",
    "mobiles_byod",
    "interconnexions_tiers",
    "fournisseurs_tiers_critiques",
    "infogerance",
    "sous_traitants_donnees",
    "securite_physique",
    "sensibilisation",
    # how one moves and rises once inside
    "architecture_reseau",
    "gestion_identites",
    "authentification_forte",
    "comptes_privilegies",
    "politique_mots_de_passe",
    "droits_administrateur",
    "revue_acces",
    # what would notice or stop a step
    "edr_av_deploye",
    "mises_a_jour",
    "gestion_vulnerabilites",
    "journalisation",
    "supervision_securite",
    "plan_reponse_incident",
    # what survives the last step
    "chiffrement_donnees",
    "sauvegarde_strategie",
    "tests_restauration",
    "plan_reprise_informatique",
    # what has been seen, and what the client expects
    "incidents_securite_passes",
    "audits_anterieurs",
    "chemin_attaque_probable",
    # asked in the atelier 4 session itself (questions.py)
    "acces_prestataires",
    "cloisonnement_administration",
    "delai_detection",
    "isolement_sauvegardes",
    "controle_flux_sortants",
)

# The expert questions the agent wrote itself during the atelier 1 intake carry the
# most technical detail of the dossier (a VPN liaison, a backup check). Their field
# name is a hash, so they travel with the question they answer.
EXPERT_QUESTION_PREFIX = "AUD-"

# The vocabulary of covers_risk_category (plugins/frameworks/*/controls.json), which
# is what a proposed new gap may be filed under.
RISK_CATEGORIES: tuple[str, ...] = (
    "reconnaissance", "initial_access", "execution", "privilege_escalation",
    "defense_evasion", "credential_access", "lateral_movement", "exfiltration",
    "impact", "data_destruction",
)

# --- The ways into the organisation a mode opératoire can take ---------------
# A fixed list, because the coverage check has to be a lookup and not a text
# match: the enumeration tags each candidate with one voie, and a voie the dossier
# names but no mode explores is then a gap in the study the code can point at.
VOIE_SERVICE_EXPOSE = "service_expose"
VOIE_ACCES_DISTANT = "acces_distant"
VOIE_TIERS = "tiers"
VOIE_PERSONNE_POSTE = "personne_poste"
VOIE_INTERNE_LEGITIME = "interne_legitime"
VOIE_ACCES_PHYSIQUE = "acces_physique"

VOIE_LABELS = {
    VOIE_SERVICE_EXPOSE: "Service exposé sur Internet",
    VOIE_ACCES_DISTANT: "Accès distant des collaborateurs",
    VOIE_TIERS: "Tiers, prestataire ou liaison permanente",
    VOIE_PERSONNE_POSTE: "Personne et son poste (message piégé, support amovible, mobile)",
    VOIE_INTERNE_LEGITIME: "Accès légitime détourné (interne, compte à privilèges)",
    VOIE_ACCES_PHYSIQUE: "Accès physique aux locaux ou au matériel",
}
VOIES: tuple[str, ...] = tuple(VOIE_LABELS)

# Which context fields make a voie plausible in this dossier. Read to tell the
# auditor which ways in no mode opératoire explored — never to invent a mode.
VOIE_CONTEXT_FIELDS: dict[str, tuple[str, ...]] = {
    VOIE_SERVICE_EXPOSE: ("exposition_internet", "applications_principales"),
    VOIE_ACCES_DISTANT: ("acces_distant_moyens", "teletravail_autorise", "wifi"),
    VOIE_TIERS: ("interconnexions_tiers", "fournisseurs_tiers_critiques", "infogerance",
                 "sous_traitants_donnees", "acces_prestataires"),
    VOIE_PERSONNE_POSTE: ("sensibilisation", "mobiles_byod", "droits_administrateur"),
    VOIE_INTERNE_LEGITIME: ("gestion_identites", "comptes_privilegies", "revue_acces"),
    VOIE_ACCES_PHYSIQUE: ("securite_physique",),
}


class Workshop4Input(BaseModel):
    """Everything an atelier 4 sub-agent may see, and nothing else (conception §9, §18).

    §18 lists the scenario, the relevant facts and the stripped gaps. The rest is
    what those three are unreadable without: the source's motivation and the
    objective (what the attacker is after), the essential assets and feared events
    (where the path must end), and the support assets (what the steps act on).
    """

    organisation_nom: str
    secteur_activite: str

    contexte: dict[str, object] = Field(default_factory=dict)
    faits_contexte: list[Fact] = Field(default_factory=list)

    # Atelier 3, as the count gate left it — approved, final, not re-validated here.
    scenarios: list[StrategicScenario] = Field(default_factory=list)

    # Atelier 2, only the ends of those scenarios.
    sources_risque: list[RiskSource] = Field(default_factory=list)
    objectifs_vises: list[ObjectifVise] = Field(default_factory=list)

    # Atelier 1.
    biens_essentiels: list[EssentialAsset] = Field(default_factory=list)
    biens_supports: list[SupportAsset] = Field(default_factory=list)
    evenements_redoutes: list[FearedEvent] = Field(default_factory=list)
    # Stripped of framework and control_id; legal-only rows already excluded (§12.3, §15).
    baseline_gaps: list[BaselineGapForW4] = Field(default_factory=list)

    alertes_atelier3: list[AtelierAlert] = Field(default_factory=list)

    @property
    def alertes_bloquantes(self) -> list[AtelierAlert]:
        return [a for a in self.alertes_atelier3 if a.bloquant]


# --- LLM proposal models (structured output) -------------------------------
# Field order is the generation order: the path and the gaps come before the
# likelihood, and the reason before the verdict it supports. Enumerated values are
# plain strings, checked in code — a model that writes « V3 (très vraisemblable) »
# produces an anomaly the auditor can see, not four paid retries.

class AttackStepProposal(BaseModel):
    tactic: str = ""
    technique_id: str | None = None
    technique_name: str = ""
    description: str = ""
    bien_support_id: str = ""
    justification: str = ""


class GapConsiderationProposal(BaseModel):
    gap_id: str = ""
    impact_type: str = ""
    impact_on_scenario: str = ""


class NewBaselineGapProposal(BaseModel):
    weakness: str = ""
    risk_categories: list[str] = Field(default_factory=list)
    justification: str = ""
    derived_from_fact_fields: list[str] = Field(default_factory=list)


class ModeCandidateProposal(BaseModel):
    """One candidate mode opératoire, before anyone develops it (§18, enumeration).

    Cheap on purpose: the way in and why it holds here, not the attack path. What
    survives the checks becomes a scenario to analyse; the rest is écarté with its
    reason. No count is asked for — the dossier decides how many there are.
    """

    libelle: str = ""
    voie: str = ""                  # one of VOIES
    point_entree: str = ""          # the support asset, third party or person it starts from
    justification: str = ""         # why this way in is plausible for THIS organisation
    derived_from_fact_fields: list[str] = Field(default_factory=list)
    doublon_de: str = ""            # the libellé of the candidate this one repeats, if any


class ModeCandidateBatch(BaseModel):
    modes: list[ModeCandidateProposal] = Field(default_factory=list)


class ScenarioAnalysisProposal(BaseModel):
    """One sub-agent's answer for one mode opératoire (§18 subagent_output)."""

    resume: str = ""
    attack_path: list[AttackStepProposal] = Field(default_factory=list)
    baseline_gaps_considered: list[GapConsiderationProposal] = Field(default_factory=list)
    likelihood_revision_reason: str = ""
    revised_likelihood: str = ""
    new_baseline_gap_identified: NewBaselineGapProposal | None = None


CONSTAT_CONTRADICTION = "techniques_contradictoires"
CONSTAT_DOUBLON = "doublon"
CONSTAT_REVISION = "revision_niveau_risque"
CONSTAT_LABELS = {
    CONSTAT_CONTRADICTION: "Techniques contradictoires",
    CONSTAT_DOUBLON: "Doublon",
    CONSTAT_REVISION: "Révision du niveau de risque",
}


class CoherenceFindingProposal(BaseModel):
    type: str = ""
    scenario_ids: list[str] = Field(default_factory=list)
    explication: str = ""
    scenario_a_reviser: str = ""
    vraisemblance_proposee: str = ""


class CoherenceBatch(BaseModel):
    constats: list[CoherenceFindingProposal] = Field(default_factory=list)


# --- Discarded elements: never dropped, always with their reason ------------

REASON_ANALYSE_REMPLACEE = "analyse_remplacee"
REASON_ENTREE_ECART_INCONNU = "entree_ecart_inconnu"
REASON_NOUVEL_ECART_SANS_ANCRAGE = "nouvel_ecart_sans_ancrage"
REASON_CONSTAT_INVALIDE = "constat_invalide"
REASON_MODE_SANS_ANCRAGE = "mode_sans_ancrage"
REASON_MODE_VOIE_INCONNUE = "mode_voie_inconnue"
REASON_MODE_DOUBLON = "mode_doublon"
REASON_MODE_AU_DELA_DU_PLAFOND = "mode_au_dela_du_plafond"
REASON_MODE_ECARTE_PAR_AUDITEUR = "mode_ecarte_par_auditeur"

ECARTE_REASON_LABELS = {
    REASON_ANALYSE_REMPLACEE: "Analyse renvoyée par l'auditeur, remplacée par sa reprise",
    REASON_ENTREE_ECART_INCONNU: "Entrée citant un écart du socle qui n'a pas été transmis",
    REASON_NOUVEL_ECART_SANS_ANCRAGE: "Nouvel écart proposé sans description ou sans élément de contexte cité",
    REASON_CONSTAT_INVALIDE: "Constat de cohérence inexploitable (type, scénarios ou explication)",
    REASON_MODE_SANS_ANCRAGE: "Mode opératoire sans libellé, sans justification ou sans champ de contexte cité",
    REASON_MODE_VOIE_INCONNUE: "Mode opératoire dont la voie d'entrée n'est pas une voie connue",
    REASON_MODE_DOUBLON: "Mode opératoire reprenant une voie d'entrée déjà couverte pour ce scénario",
    REASON_MODE_AU_DELA_DU_PLAFOND: "Mode opératoire au-delà du plafond, non développé",
    REASON_MODE_ECARTE_PAR_AUDITEUR: "Mode opératoire écarté par l'auditeur avant développement",
}


class ElementEcarte(ElementEcarteBase):
    """Something that did not make it into w4_output, with why (§16, §19)."""

    LABELS: ClassVar[dict[str, str]] = ECARTE_REASON_LABELS


# --- The coherence review (§18 step 28) ------------------------------------

COHERENCE_SANS_CONSTAT = "sans_constat"  # nothing to rule on: under two scenarios, or nothing found
COHERENCE_APPLIQUEE = "appliquee"        # findings accepted, proposed revisions applied
COHERENCE_ECARTEE = "ecartee"            # findings set aside by the auditor, with a reason


class CoherenceFinding(BaseModel):
    type: str
    scenario_ids: list[str]
    explication: str
    scenario_a_reviser: str = ""
    vraisemblance_proposee: str = ""  # V1..V4 for a revision, checked before it is kept

    @property
    def label(self) -> str:
        return CONSTAT_LABELS.get(self.type, self.type)


class CoherenceReview(BaseModel):
    """The single coherence call over the stable set, and what the auditor made of it.

    ``decision`` empty means the auditor has not ruled yet — the state a resumed
    mission picks up at, without paying for the call again.
    """

    constats: list[CoherenceFinding] = Field(default_factory=list)
    decision: str = ""
    justification: str = ""


# --- Validated output ------------------------------------------------------

class Workshop4Output(BaseModel):
    """w4_output (conception §18). ``scenarios`` is what atelier 5 treats."""

    scenarios: list[OperationalScenario] = Field(default_factory=list)
    coherence: CoherenceReview | None = None
    elements_ecartes: list[ElementEcarte] = Field(default_factory=list)
    quality_report: QualityReport = Field(default_factory=QualityReport)
    alertes_atelier3: list[AtelierAlert] = Field(default_factory=list)
    attck_version: str = ""
    human_edits: list[dict] = Field(default_factory=list)
