"""EssentialAsset / SupportAsset — biens essentiels / biens supports (conception §14, §15).

Both carry their provenance the same way every organizational assertion does:
each is backed by the Facts it was derived from, so the auditor can trace an
asset back to a declaration, an extraction (with citation), or an assessment.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import Origin


class EssentialAsset(BaseModel):
    """A bien essentiel — information or process the organization must protect (conception §15)."""

    id: str
    nom: str
    description: str
    # 'information' or 'processus' — kept free text on purpose; EBIOS RM does not pin a closed list here.
    nature: str
    processus_metier_associes: list[str] = Field(default_factory=list)
    origin: Origin
    derived_from_fact_fields: list[str] = Field(default_factory=list)  # traceability back to Mission Context


class SupportAsset(BaseModel):
    """A bien support — the technical/human/organizational asset an essential asset relies on (conception §15)."""

    id: str
    nom: str
    description: str
    type_support: str  # e.g. serveur, application, poste, personne, prestataire
    biens_essentiels_supportes: list[str] = Field(default_factory=list)  # EssentialAsset ids
    origin: Origin
    derived_from_fact_fields: list[str] = Field(default_factory=list)
