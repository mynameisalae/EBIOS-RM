"""Typed input/output for Workshop 5 — traitement du risque (conception §19).

Same three families as the earlier ateliers:
  * ``Workshop5Input`` — everything the single agent may see. Built from the
    finalized Atelier 4 output and the Atelier 1 baseline gaps.
  * ``MesureProposal`` / ``MesuresBatch`` — what the agent returns in its one
    call. Structured output plus real tool calls (get_mitigations_for_technique)
    — the first atelier of the project to use genuine tool calling rather than
    resolving everything in code beforehand (§3.1, §10.1).
  * ``Workshop5Output`` — the validated w5_output: one Mesure per accepted
    proposal, what was set aside and why, the quality report.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from ebios_rm.domain.mesure import Mesure
from ebios_rm.domain.operational_scenario import OperationalScenario
from ebios_rm.workshops.common import ElementEcarteBase
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap
from ebios_rm.workshops.workshop2_sources_risque.models import (  # noqa: F401 — re-exported
    STATUT_AVERTISSEMENT,
    STATUT_ERREUR,
    STATUT_OK,
    QualityCheck,
    QualityReport,
)

# --- Input contract ----------------------------------------------------------


class Workshop5Input(BaseModel):
    """Everything the atelier 5 agent may see, and nothing else (conception §9, §19).

    Two differences from atelier 4's input worth noting:

    * ``scenarios`` here are the *finalized* atelier 4 scenarios (post-coherence,
      post-approval) — the route, the confirmed likelihood and risk level, and
      each scenario's own ``baseline_gaps_considered``, which already tells the
      agent which gaps bear on which attack path without it re-deriving that.

    * ``baseline_gaps`` are the *full*, unstripped gaps from atelier 1 —
      framework and control_id included. Atelier 4 never sees that (§12.3,
      §20.3: no regulatory bias in the technical path). Atelier 5 is the
      opposite case: it must name a gap's regulatory origin outright to decide
      whether it is in its technical scope (the RGPD Article 32 exception, and
      the exclusion of RGPD entries with no covers_risk_category — see
      workshop.py, which resolves that from the reference repository before
      this input is built, not from the model's own reading of the framework).
    """

    organisation_nom: str
    secteur_activite: str

    scenarios: list[OperationalScenario] = Field(default_factory=list)
    baseline_gaps: list[BaselineGap] = Field(default_factory=list)


# --- LLM proposal (structured output + real tool calls) ---------------------
# Field order is the generation order: what is treated, then how, then what it
# costs to weigh. priorite stays a plain string here, checked in code (§18's
# convention: a model that writes « Haute » instead of the fixed vocabulary
# produces a visible anomaly, not a silently accepted wrong value).


class MesureProposal(BaseModel):
    """One proposed measure, before validation (§19 w5_output.mesures)."""

    description: str = ""
    scenarios_associes: list[str] = Field(default_factory=list)
    mitigation_ids_attck: list[str] = Field(default_factory=list)
    cout: str = ""
    efficacite: str = ""
    delai: str = ""
    priorite: str = ""


class MesuresBatch(BaseModel):
    """The single agent's whole answer for this mission (§19)."""

    mesures: list[MesureProposal] = Field(default_factory=list)


# --- Discarded elements: never dropped, always with their reason ------------

REASON_MITIGATION_INCONNUE = "mitigation_inconnue"
REASON_SCENARIO_INCONNU = "scenario_inconnu"
REASON_PRIORITE_INVALIDE = "priorite_invalide"
REASON_CRITERE_MANQUANT = "critere_manquant"

ECARTE_REASON_LABELS = {
    REASON_MITIGATION_INCONNUE: "Identifiant de mitigation ATT&CK non retourné par l'outil de consultation",
    REASON_SCENARIO_INCONNU: "Mesure associée à un scénario opérationnel qui n'existe pas",
    REASON_PRIORITE_INVALIDE: "Priorité hors de l'échelle Faible / Moyenne / Élevée",
    REASON_CRITERE_MANQUANT: "Coût, efficacité ou délai manquant — un critère d'arbitrage ne peut être vide",
}


class ElementEcarte(ElementEcarteBase):
    """A proposed measure that did not make it into w5_output, with why (§16, §19)."""

    LABELS: ClassVar[dict[str, str]] = ECARTE_REASON_LABELS


# --- Validated output ---------------------------------------------------------


class Workshop5Output(BaseModel):
    """w5_output (conception §19). ``mesures`` is what the reporting agent reads."""

    mesures: list[Mesure] = Field(default_factory=list)
    elements_ecartes: list[ElementEcarte] = Field(default_factory=list)
    quality_report: QualityReport = Field(default_factory=QualityReport)
    human_edits: list[dict] = Field(default_factory=list)
