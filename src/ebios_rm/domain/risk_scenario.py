"""RiskScenario and MesureSecurite — what atelier 5 works on (conception §14, §19).

A risk scenario is the whole thing read end to end: a source de risque reaching an
objectif visé, through the strategic scenario's route and the operating mode atelier 4
retained, causing a feared event on an essential asset. It carries two numbers and
neither is invented here — the gravité comes down from atelier 1 through atelier 3,
the vraisemblance up from atelier 4 (the likelihood of its most likely mode) — and
the risk level is read off the matrix.

A measure treats risks. It belongs to one of the four groups of the treatment plan
(gouvernance, protection, défense, résilience), says which risks it serves and what
it acts on (a step of a mode, a baseline gap, a stakeholder), and carries what the
plan needs to be usable: who, how hard, how long, in which order, where it stands.

Security measures lower the vraisemblance, not the gravité: if a feared event
happens, it hurts exactly as much as before. The residual evaluation therefore only
moves the likelihood, and the code refuses anything else.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import (
    Acceptabilite,
    AxeMesure,
    Gravite,
    NiveauRisque,
    OptionTraitement,
    Origin,
    Priorite,
    StatutMesure,
    VraisemblanceInitiale,
)


class MesureSecurite(BaseModel):
    """One measure of the risk treatment plan (atelier 5-3)."""

    id: str                               # M-01..
    axe: AxeMesure
    thematique: str = ""                  # the group's sub-theme, e.g. « gestion de l'authentification »
    libelle: str
    description: str = ""

    # What it treats, and what it acts on — every link checked in code.
    risques_ids: list[str] = Field(default_factory=list)
    modes_ids: list[str] = Field(default_factory=list)        # operating modes it blocks
    etapes_visees: list[str] = Field(default_factory=list)    # « SO-02 étape 3 »
    gap_ids: list[str] = Field(default_factory=list)          # atelier 1 baseline gaps it closes
    mitigation_ids_attck: list[str] = Field(default_factory=list)  # real ATT&CK ids, never invented
    origine: str = ""                     # atelier1_socle | atelier3_ecosysteme | atelier4_vulnerabilite

    # What the plan needs to be usable (the auditor owns these).
    responsable: str = ""
    freins: str = ""
    cout_complexite: str = ""             # +, ++, +++
    charge_estimee: str = ""              # « 10 j/h »
    echeance: str = ""                    # « 6 mois »
    priorite: Priorite | None = None      # computed: risk level first, then cost
    statut: StatutMesure = StatutMesure.A_LANCER

    # How much of the likelihood it can take away, in levels (0, 1 or 2) — proposed,
    # bounded in code, and only ever applied through the residual evaluation.
    effet_vraisemblance: int = 0
    justification: str = ""
    origin: Origin = Origin.ASSESSMENT


class RiskScenario(BaseModel):
    """One risk, from its initial level to its residual one (atelier 5-1, 5-2, 5-4)."""

    id: str                               # R1..
    libelle: str = ""                     # the risk in business words, for the decision-maker
    scenario_strategique_id: str
    mode_retenu_id: str = ""              # the driving operating mode of atelier 4
    modes_alternatifs_ids: list[str] = Field(default_factory=list)
    source_risque_id: str = ""
    objectif_vise_id: str = ""
    biens_essentiels_ids: list[str] = Field(default_factory=list)
    evenements_redoutes_ids: list[str] = Field(default_factory=list)

    # --- initial risk: nothing re-judged here ---
    gravite: Gravite = Gravite.MINIMALE
    vraisemblance: VraisemblanceInitiale = VraisemblanceInitiale.V1
    niveau_risque: NiveauRisque | None = None
    acceptabilite: Acceptabilite | None = None

    # --- treatment strategy (the auditor decides, §2) ---
    option_traitement: OptionTraitement | None = None
    justification_traitement: str = ""
    mesures_ids: list[str] = Field(default_factory=list)

    # --- residual risk, once the plan is counted (atelier 5-4) ---
    vraisemblance_residuelle: VraisemblanceInitiale | None = None
    motif_residuel: str = ""
    niveau_risque_residuel: NiveauRisque | None = None
    acceptabilite_residuelle: Acceptabilite | None = None
    accepte_par: str = ""                 # who formally accepted the residual risk, and when
    origin: Origin = Origin.ASSESSMENT


class IndicateurSuivi(BaseModel):
    """One steering indicator of the monitoring framework (atelier 5-5).

    Built on one of the four kinds of value the method names: a cost, a duration, a
    count or a rate.
    """

    id: str
    libelle: str
    type_valeur: str = ""      # cout | duree | nombre | taux
    cible: str = ""
    frequence: str = ""
    responsable: str = ""
    mesures_ids: list[str] = Field(default_factory=list)


class CadreSuivi(BaseModel):
    """The risk monitoring framework (atelier 5-5): what is watched, by whom, how often."""

    indicateurs: list[IndicateurSuivi] = Field(default_factory=list)
    comite: str = ""            # the steering committee and its cadence
    cycles: str = ""            # when the study itself is reviewed
    prochaine_revue: str = ""
