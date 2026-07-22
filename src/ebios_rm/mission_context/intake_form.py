"""org_context_form — the standardized intake form (conception §11.1).

This is the single structured file that poses, up front, every generic question
common to any EBIOS RM mission — the same form is the starting point whatever the
client. Every field the auditor fills becomes a Fact of origin 'declaration'
(§4), the highest confidence. The list is non-exhaustive by construction: new
fields may be added without an architecture change, as long as they follow the
same Fact-attachment rule.

Each field is also tagged — via FIELD_SPECS below — with the human-facing
question used to render the client questionnaire (see questionnaire.py) and with
its priority level (§7), so the questionnaire, the priority matrix, and the
schema can never drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import Hebergement, PriorityLevel


class OrgContextForm(BaseModel):
    """The intake form schema (conception §11.1).

    Optional fields (``None`` / empty) are exactly the ones the priority matrix
    (§7) may raise as follow-up questions once the form and any documents are
    ingested — Critical ones block, Important ones require a justification to skip.
    """

    organisation_nom: str
    secteur_activite: str
    taille_effectif: int
    perimetre_geographique: list[str] = Field(default_factory=list)

    systeme_information_resume: str  # free description of the IT architecture
    hebergement: Hebergement

    teletravail_autorise: bool
    acces_distant_moyens: list[str] = Field(default_factory=list)  # e.g. VPN, MFA, VDI

    edr_av_deploye: str | None = None
    sauvegarde_strategie: str | None = None

    donnees_personnelles_traitees: bool
    categories_donnees_personnelles: list[str] | None = None

    incidents_securite_passes: str | None = None
    audits_anterieurs: str | None = None

    fournisseurs_tiers_critiques: list[str] = Field(default_factory=list)

    # §12.4 — pre-filled with the four defaults, editable by the auditor (declaration, never inference).
    applicable_frameworks: list[str] = Field(
        default_factory=lambda: ["ISO27001", "ANSSI_hygiene", "RGPD", "NIST"]
    )

    processus_metier_critiques: list[str] = Field(default_factory=list)  # seed for essential assets (atelier 1)

    documents_fournis: list[str] | None = None  # names of attached files, entirely optional


@dataclass(frozen=True)
class FieldSpec:
    """Rendering + priority metadata for one intake field (conception §7, §11.1)."""

    name: str
    section: str
    question: str
    priority: PriorityLevel
    help_text: str = ""
    # False for fields the priority matrix must never raise as a follow-up
    # (genuinely optional, e.g. the list of attached documents — §11.1).
    askable: bool = True
    # Name of a boolean field this one is conditional on: only asked when that
    # field is True (e.g. data-subject categories only matter if PII is processed).
    depends_on_true: str | None = None


# Ordered specification driving both the client questionnaire and the priority matrix.
# CRITICAL: the workshop cannot continue without an explicit value or confirmation.
# IMPORTANT: asked when missing; Skip/Unknown/Not-Applicable accepted only with a non-empty reason (§8).
FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec(
        "organisation_nom", "Identité de l'organisation",
        "Quel est le nom de l'organisation auditée ?", PriorityLevel.CRITICAL,
    ),
    FieldSpec(
        "secteur_activite", "Identité de l'organisation",
        "Quel est le secteur d'activité principal ?", PriorityLevel.CRITICAL,
    ),
    FieldSpec(
        "taille_effectif", "Identité de l'organisation",
        "Quel est l'effectif total (nombre de personnes) ?", PriorityLevel.IMPORTANT,
    ),
    FieldSpec(
        "perimetre_geographique", "Identité de l'organisation",
        "Sur quels pays / sites l'audit porte-t-il ?", PriorityLevel.IMPORTANT,
        "Liste des implantations géographiques dans le périmètre.",
    ),
    FieldSpec(
        "systeme_information_resume", "Système d'information",
        "Décrivez librement l'architecture de votre système d'information.", PriorityLevel.CRITICAL,
        "Applications métier, hébergement, réseaux, postes, principaux flux.",
    ),
    FieldSpec(
        "hebergement", "Système d'information",
        "Comment est hébergé le système d'information ?", PriorityLevel.CRITICAL,
        "Une valeur parmi : sur_site, cloud, hybride.",
    ),
    FieldSpec(
        "teletravail_autorise", "Accès et postes de travail",
        "Le télétravail est-il autorisé ?", PriorityLevel.IMPORTANT,
    ),
    FieldSpec(
        "acces_distant_moyens", "Accès et postes de travail",
        "Quels moyens d'accès distant sont utilisés ?", PriorityLevel.IMPORTANT,
        "Ex. VPN, MFA, VDI, bureau distant.",
    ),
    FieldSpec(
        "edr_av_deploye", "Protection des postes et serveurs",
        "Quel EDR / antivirus est déployé ?", PriorityLevel.IMPORTANT,
    ),
    FieldSpec(
        "sauvegarde_strategie", "Continuité",
        "Quelle est la stratégie de sauvegarde ?", PriorityLevel.IMPORTANT,
        "Fréquence, hors-ligne / immuable, tests de restauration.",
    ),
    FieldSpec(
        "donnees_personnelles_traitees", "Données personnelles (RGPD)",
        "L'organisation traite-t-elle des données personnelles ?", PriorityLevel.CRITICAL,
    ),
    FieldSpec(
        "categories_donnees_personnelles", "Données personnelles (RGPD)",
        "Quelles catégories de données personnelles sont traitées ?", PriorityLevel.IMPORTANT,
        "Ex. clients, salariés, données de santé, données sensibles.",
        depends_on_true="donnees_personnelles_traitees",
    ),
    FieldSpec(
        "incidents_securite_passes", "Historique",
        "Des incidents de sécurité notables sont-ils déjà survenus ?", PriorityLevel.IMPORTANT,
    ),
    FieldSpec(
        "audits_anterieurs", "Historique",
        "Des audits ou évaluations antérieurs existent-ils ?", PriorityLevel.IMPORTANT,
    ),
    FieldSpec(
        "fournisseurs_tiers_critiques", "Écosystème",
        "Quels sont les fournisseurs / tiers critiques ?", PriorityLevel.IMPORTANT,
        "Prestataires dont une défaillance affecterait directement l'activité.",
    ),
    FieldSpec(
        "applicable_frameworks", "Référentiels applicables",
        "Quels référentiels de conformité s'appliquent ?", PriorityLevel.CRITICAL,
        "Pré-rempli : ISO27001, ANSSI_hygiene, RGPD, NIST. À confirmer, retirer ou compléter (ex. HIPAA).",
    ),
    FieldSpec(
        "processus_metier_critiques", "Métier",
        "Quels sont les processus métier critiques ?", PriorityLevel.CRITICAL,
        "Amorce des biens essentiels de l'atelier 1.",
    ),
    FieldSpec(
        "documents_fournis", "Pièces jointes",
        "Quels documents joignez-vous en complément ? (optionnel)", PriorityLevel.IMPORTANT,
        "Politique de sécurité, schéma réseau, inventaire, rapport précédent…",
        askable=False,
    ),
)

FIELD_SPEC_BY_NAME: dict[str, FieldSpec] = {spec.name: spec for spec in FIELD_SPECS}
