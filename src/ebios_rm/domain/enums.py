"""Fixed enumerations shared across layers (conception §4, §5, §6, §7, §15, §15.1).

Every value pinned here is normative — the fiches de test assert against these
exact strings, so they must never drift.
"""

from enum import Enum


class Origin(str, Enum):
    """The three origins of information (conception §4)."""

    DECLARATION = "declaration"  # entered by the auditor in the intake form — highest confidence
    EXTRACTION = "extraction"    # found by the AI in a supplied document — requires source_quote
    ASSESSMENT = "assessment"    # reasoned/inferred by the AI — requires assessment_basis, lowest confidence


class FactStatus(str, Enum):
    """Lifecycle of a Fact status (conception §6)."""

    DECLARED = "declared"            # entered by the auditor — no human action
    EXTRACTED = "extracted"          # found in a document, with source_quote — human must validate
    ASSESSED = "assessed"            # inferred by the AI from other Facts — human must validate
    CONTRADICTION = "contradiction"  # sources disagree — mandatory human resolution, never automatic
    MISSING = "missing"              # not found — human, unless not tracked as a Fact (§5.2)
    APPROVED = "approved"            # validated by the auditor — no human action
    REJECTED = "rejected"            # rejected — human must replace or justify
    SKIPPED = "skipped"              # auditor chose not to answer — justification mandatory (§8)


class Confidence(str, Enum):
    """Confidence attached to a Fact (conception §5.1)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PriorityLevel(str, Enum):
    """Information priority matrix — two levels only, no silent-omission level (conception §7)."""

    CRITICAL = "critical"    # the workshop cannot continue without explicit supply or confirmation
    IMPORTANT = "important"  # the AI asks; Skip/Unknown/Not-Applicable only with a non-empty justification


class Gravite(str, Enum):
    """The four fixed gravity values for a feared event (conception §15, generative validation criterion)."""

    MINIMALE = "Minimale"
    SIGNIFICATIVE = "Significative"
    GRAVE = "Grave"
    CRITIQUE = "Critique"


class CategorieImpact(str, Enum):
    """Impact categories, pinned to five values aligned with real professional practice (conception §15.1)."""

    FINANCIER = "financier"
    FONCTIONNEMENT = "fonctionnement"
    IMAGE = "image"
    JURIDIQUE = "juridique"  # sanctions, formal notice, litigation
    VIE_PRIVEE_PERSONNES_CONCERNEES = "vie_privee_personnes_concernees"  # impact on the data subjects


class Pertinence(str, Enum):
    """Pertinence of an SR/OV couple — three fixed values (fiche de test atelier 2)."""

    FAIBLE = "Faible"
    MOYEN = "Moyen"
    ELEVE = "Élevé"


class VraisemblanceInitiale(str, Enum):
    """Initial likelihood of an SR/OV couple, V1..V4 (fiche de test atelier 2).

    "Does this source target this organisation", never technical success — the
    likelihood of an attack succeeding belongs to atelier 4.
    """

    V1 = "V1"
    V2 = "V2"
    V3 = "V3"
    V4 = "V4"


class NiveauRisque(str, Enum):
    """Risk level of an operational scenario (atelier 4, conception §18 step 29).

    Read from a fixed gravité × vraisemblance matrix in code, never worded by the
    model. Where each level sits against the organisation's risk acceptance is
    atelier 5's decision, not this scale's.
    """

    FAIBLE = "Faible"
    MOYEN = "Moyen"
    ELEVE = "Élevé"
    CRITIQUE = "Critique"


class Acceptabilite(str, Enum):
    """How a risk level sits against the organisation's acceptance thresholds (atelier 5-2).

    The scale the method proposes: a low risk is accepted as it stands, a medium one
    is tolerated under control (monitored, improved over time), a high one is
    unacceptable — reduction measures are mandatory in the short term, failing which
    all or part of the activity is refused.
    """

    ACCEPTABLE = "Acceptable en l'état"
    TOLERABLE = "Tolérable sous contrôle"
    INACCEPTABLE = "Inacceptable"


class OptionTraitement(str, Enum):
    """The four risk treatment options of ISO 27005:2022, as atelier 5-2 applies them."""

    REDUCTION = "reduction"   # act on the scenario so it becomes less likely
    MAINTIEN = "maintien"     # keep the risk as it is (accept it)
    PARTAGE = "partage"       # share or transfer it (insurance, contract, third party)
    EVITEMENT = "evitement"   # refuse it: the activity or the exposure is given up


class AxeMesure(str, Enum):
    """The four groups a risk treatment plan is organised in (atelier 5-3)."""

    GOUVERNANCE = "gouvernance"  # governance and anticipation
    PROTECTION = "protection"
    DEFENSE = "defense"
    RESILIENCE = "resilience"


class Priorite(str, Enum):
    """Priority of a measure in the plan — risk level first, then cost and delay (atelier 5-3)."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class StatutMesure(str, Enum):
    """Where a measure stands in the plan (atelier 5-3)."""

    A_LANCER = "À lancer"
    EN_COURS = "En cours"
    TERMINE = "Terminé"


class ImpactType(str, Enum):
    """How one baseline gap bears on one operational scenario (conception §18).

    Every value owes a non-empty impact_on_scenario — not_relevant included.
    """

    INCREASES_LIKELIHOOD = "increases_likelihood"  # makes a step of the path possible or easier
    INCREASES_IMPACT = "increases_impact"          # worsens the consequence, not the access
    NO_IMPACT = "no_impact"                        # on the path's ground, but changes nothing here
    NOT_RELEVANT = "not_relevant"                  # concerns nothing in this scenario


class StatutSelection(str, Enum):
    """Outcome of an atelier 2 filter (white-box §7, §10, §11).

    Nothing is deleted: an écarté element keeps its reason (§17, §19).
    """

    RETENU = "retenu"
    SECONDAIRE = "secondaire"
    ECARTE = "ecarte"


class Hebergement(str, Enum):
    """Hosting model declared in the intake form (conception §11.1)."""

    SUR_SITE = "sur_site"
    CLOUD = "cloud"
    HYBRIDE = "hybride"


class LegalImpactType(str, Enum):
    """Nature of a purely-legal provision (conception §12.3).

    A control row whose legal_impact_type is set is excluded from the workshop 4
    relevance filter and instead feeds the workshop 1 legal-impact assessment.
    """

    FINANCIAL_PENALTY = "financial_penalty"
    MANDATORY_NOTIFICATION = "mandatory_notification"
    LIABILITY = "liability"
