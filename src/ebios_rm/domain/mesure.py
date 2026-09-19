"""Mesure — one treatment measure, the fan-in output of workshop 5 (conception §19).

A measure answers "what do we do about it": one or more operational scenarios
(and/or baseline gaps) it reduces, the real ATT&CK mitigation(s) it implements
when it addresses a cited technique, and the four criteria the auditor weighs
a treatment plan on — cost, effectiveness, delay, priority.

The model proposes; code decides the priority is one of the three fixed values
and that every mitigation id it cites is real (checked against the ATT&CK base
via the same kind of read-only repository atelier 4 already uses).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import Origin, PrioriteMesure
from ebios_rm.domain.operational_scenario import Anomaly


class Mesure(BaseModel):
    """One treatment measure (conception §19 w5_output.mesures — the exact schema
    the fiche de test pins: id, description, scenarios_associes,
    mitigation_ids_attck, cout, efficacite, delai, priorite)."""

    id: str  # MT-01.., in the order the measures were produced
    description: str

    # The operational scenarios this measure reduces. A measure answering a
    # baseline gap that is not tied to any one scenario's steps (a general
    # weakness of the socle) may carry an empty list here — it still belongs
    # in w5_output, just not attached to a specific attack path.
    scenarios_associes: list[str] = Field(default_factory=list)

    # A measure derived from an ATT&CK-cited technique names the real
    # mitigation(s) get_mitigations_for_technique(id) returned — never invented
    # (same discipline as atelier 4's technique_id, conception §18).
    mitigation_ids_attck: list[str] = Field(default_factory=list)

    # --- the four criteria the auditor arbitrates on ---
    cout: str = ""         # qualitative, e.g. "Faible", "Moyen (formation)", "Élevé (nouvel outil)"
    efficacite: str = ""   # what residual risk looks like once applied, in the auditor's terms
    delai: str = ""        # rough time to implement, qualitative
    # None when the model's own priorite text did not fold onto the fixed
    # vocabulary — flagged as an anomaly (assessment.py), never guessed. The
    # measure itself is still kept: a real description with an unreadable
    # priority is still useful to the auditor, unlike an empty proposal.
    priorite: PrioriteMesure | None = None

    # Beyond the bare w5_output.mesures schema, same reason atelier 4's
    # OperationalScenario carries more than its own terse conception line:
    # what build_mesure found wrong (an unreadable priority, a dropped
    # citation) has to live somewhere the auditor actually sees it.
    anomalies: list[Anomaly] = Field(default_factory=list)
    origin: Origin = Origin.ASSESSMENT

    @property
    def blocking_anomalies(self) -> list[Anomaly]:
        return [a for a in self.anomalies if a.bloquante]
