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
