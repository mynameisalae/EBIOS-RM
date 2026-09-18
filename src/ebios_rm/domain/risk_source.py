"""RiskSource / ObjectifVise / CoupleSROV — the atelier 2 entities (white-box §8, §10, §12).

A source de risque is a *motivated actor category* (cybercriminel, concurrent,
État, employé mécontent), never a server, a database, a vulnerability or an
attack technique (white-box §17). MITRE ATT&CK named groups are campaign
clusters, not sources de risque; they belong to atelier 4 where the modes
opératoires live (§15).

Like every atelier 1 entity, all three carry their provenance: the context
elements each was derived from, and the Origin telling a supplied fact apart
from an AI assumption (§8 "les faits fournis doivent être distingués des
hypothèses produites par l'IA").
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import (
    Origin,
    Pertinence,
    StatutSelection,
    VraisemblanceInitiale,
)


class RiskSource(BaseModel):
    """A source de risque retained (or kept secondary) by the atelier 2 filter (white-box §7, §8)."""

    id: str
    categorie_id: str  # id of a category of the approved SR/OV base — never invented (§6)
    categorie_libelle: str = ""
    nom: str
    description: str = ""
    motivation: str = ""  # what this actor would be after, in this context
    statut: StatutSelection = StatutSelection.RETENU
    justification: str  # why plausible *here* — non-empty, enforced in assessment.py
    derived_from_fact_fields: list[str] = Field(default_factory=list)
    origin: Origin = Origin.ASSESSMENT


class ObjectifVise(BaseModel):
    """An objectif visé — what a source de risque wants to obtain (white-box §9, §10).

    An objective, never a technique: « injection SQL », « PowerShell » or
    « phishing » describe a modality and are rejected in assessment.py.
    """

    id: str
    finalite_id: str  # id of a finalité of the approved SR/OV base
    finalite_libelle: str = ""
    description: str
    enjeu: str = ""  # the atelier 1 stake concerned
    biens_essentiels_vises: list[str] = Field(default_factory=list)  # EssentialAsset ids
    statut: StatutSelection = StatutSelection.RETENU
    justification: str
    derived_from_fact_fields: list[str] = Field(default_factory=list)
    origin: Origin = Origin.ASSESSMENT


class CoupleSROV(BaseModel):
    """A retained SR/OV couple with its full trace back to atelier 1 (white-box §11, §12, §13).

    The trace (biens essentiels, valeurs métier, biens supports) is computed in
    code from the atelier 1 output, never by the model: it is a lookup, and a
    hallucinated one would silently break traceability.

    motivation / ressources / activite are the model's rated judgments (1..4);
    pertinence and vraisemblance_initiale are derived from them deterministically
    (assessment.py) — the LLM never invents a score or a scale (§13, §17).
    """

    id: str
    source_risque_id: str
    objectif_vise_id: str

    # --- traceability, computed (§12) ---
    biens_essentiels_ids: list[str] = Field(default_factory=list)
    valeurs_metier: list[str] = Field(default_factory=list)
    biens_supports_associes: list[str] = Field(default_factory=list)

    # --- characterisation (§13) ---
    motivation: int = 0   # 1..4, how much this source wants this objective here
    ressources: int = 0   # 1..4, means it can bring to bear
    activite: int = 0     # 1..4, how active this source is against this sector
    pertinence: Pertinence = Pertinence.FAIBLE
    vraisemblance_initiale: VraisemblanceInitiale = VraisemblanceInitiale.V1

    statut: StatutSelection = StatutSelection.RETENU
    justification: str
