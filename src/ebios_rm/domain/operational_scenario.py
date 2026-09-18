"""OperationalScenario — scénario opérationnel, the fan-out/fan-in output of workshop 4 (conception §14, §18).

One operational scenario is one approved strategic scenario told as the attack it
would take: the elementary actions a source de risque performs on the support
assets of this organisation, in ATT&CK terms, from first contact to the feared event.

The model proposes the path, how each baseline gap bears on it, and the revised
likelihood with its reason. Code decides that every technique id is one the ATT&CK
base returned, that no gap entry is left without a sentence, the phase of each step,
and the risk level. The auditor decides whether any of it is right.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import (
    Gravite,
    ImpactType,
    NiveauRisque,
    Origin,
    VraisemblanceInitiale,
)

# Where one scenario stands in the review loop (§18 steps 25-27).
STATUT_A_ANALYSER = "a_analyser"  # never analysed
STATUT_A_REVISER = "a_reviser"    # sent back: amend the analysis on the auditor's reasons
STATUT_A_REFAIRE = "a_refaire"    # sent back: discard it and build another path
STATUT_ANALYSE = "analyse"        # analysed, awaiting the auditor
STATUT_CONFIRME = "confirme"      # confirmed by the auditor
STATUTS_EN_ATTENTE = frozenset({STATUT_A_ANALYSER, STATUT_A_REVISER, STATUT_A_REFAIRE})


class AttackStep(BaseModel):
    """One elementary action of the attack path (§18 attack_path)."""

    phase: str = ""                  # Connaître / Rentrer / Trouver / Exploiter, from the tactic, in code
    tactic: str                      # ATT&CK tactic shortname, e.g. 'initial-access'
    technique_id: str | None = None  # an id the ATT&CK base returned, or None — never invented (§18)
    technique_name: str = ""         # the base's own name whenever technique_id is set
    description: str                 # the action in this organisation's terms (step description)
    bien_support_id: str = ""        # the atelier 1 support asset acted on, when there is one
    justification: str = ""          # what in the dossier makes this step feasible here


class GapConsideration(BaseModel):
    """How one stripped baseline gap bears on the scenario (§18 baseline_gaps_considered).

    impact_on_scenario is never empty whatever impact_type says: « not relevant » is
    a claim like any other and owes its reason (§18 step 24).
    """

    gap_id: str
    impact_type: ImpactType
    impact_on_scenario: str


class NewBaselineGap(BaseModel):
    """A weakness the dossier reveals that no baseline gap captures (§18 new_baseline_gap_identified).

    A proposal to the auditor, never written back into atelier 1: repairing an
    earlier atelier silently is forbidden (§2, §16).
    """

    weakness: str
    risk_categories: list[str] = Field(default_factory=list)
    justification: str
    derived_from_fact_fields: list[str] = Field(default_factory=list)


class Anomaly(BaseModel):
    """What the code found in an analysis — highlighted for the auditor, never quietly repaired (§18 steps 23-25).

    A blocking anomaly does not delete anything: it means confirming the scenario
    takes an explicit override.
    """

    code: str
    message: str
    bloquante: bool = True


class OperationalScenario(BaseModel):
    """One analysed strategic scenario (conception §18 subagent_output)."""

    id: str                                  # SO-01.., in the order of the strategic scenarios
    scenario_strategique_id: str
    source_risque_id: str
    objectif_vise_id: str

    resume: str = ""
    attack_path: list[AttackStep] = Field(default_factory=list)

    # --- carried from ateliers 1 to 3, never re-judged here ---
    biens_essentiels_ids: list[str] = Field(default_factory=list)
    evenements_redoutes_ids: list[str] = Field(default_factory=list)
    gravite: Gravite = Gravite.MINIMALE
    vraisemblance_initiale: VraisemblanceInitiale = VraisemblanceInitiale.V1

    # --- the revision (§18) ---
    likelihood_revision_reason: str = ""
    revised_likelihood: VraisemblanceInitiale | None = None
    revised_risk_level: NiveauRisque | None = None  # gravité x revised_likelihood, computed in code

    baseline_gaps_considered: list[GapConsideration] = Field(default_factory=list)
    new_baseline_gap_identified: NewBaselineGap | None = None

    # --- the review loop (§18 steps 23-27) ---
    anomalies: list[Anomaly] = Field(default_factory=list)
    statut: str = STATUT_A_ANALYSER
    iterations: int = 0                      # analyses run on this scenario, capped at 3 before a CONFIRMER
    motifs_auditeur: list[str] = Field(default_factory=list)

    origin: Origin = Origin.ASSESSMENT

    @property
    def blocking_anomalies(self) -> list[Anomaly]:
        return [a for a in self.anomalies if a.bloquante]
