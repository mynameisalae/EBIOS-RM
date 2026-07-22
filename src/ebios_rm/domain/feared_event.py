"""FearedEvent — événement redouté, with gravity (conception §14, §15, §15.1).

Gravity is one of four fixed values (§15). A feared event may accumulate impact
across the five fixed impact categories (§15.1); legal impact contributes to
gravity independently of any security-baseline gap — a feared event can be
Grave or Critique on legal grounds alone, because the legal consequence flows
from the statute, not from a missing control.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import CategorieImpact, Gravite, Origin


class LegalImpactEntry(BaseModel):
    """One legal-impact finding attached to a feared event (conception §15.1).

    Both citations are mandatory (evaluation by evidence, same discipline as
    assess_control): the precise Mission Context fact that makes the provision
    relevant, AND the legal provision itself (penalty cap, notification delay...).
    """

    categorie_impact: CategorieImpact = CategorieImpact.JURIDIQUE
    provision_citee: str  # the legal provision text (from baseline_controls.legal_impact_details)
    evidence_mission_context: str  # the precise fact cited from the Mission Context
    framework: str  # which declared referential the provision comes from


class FearedEvent(BaseModel):
    """An événement redouté with its gravity and impact provenance (conception §15, §15.1)."""

    id: str
    description: str
    bien_essentiel_id: str | None = None
    categorie_impact: CategorieImpact
    gravite: Gravite
    origin: Origin
    derived_from_fact_fields: list[str] = Field(default_factory=list)
    # Legal-impact findings that contributed to gravity, independent of baseline gaps (§15.1).
    legal_impacts: list[LegalImpactEntry] = Field(default_factory=list)
