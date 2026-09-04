"""StrategicScenario — scénario stratégique, produced by the propose/critique loop of workshop 3 (conception §14, §17).

One scenario is one retained SR/OV couple, told as a route: this source de risque,
reaching this organisation through these parties prenantes, to obtain this
objectif visé, and what it would cost if it succeeded.

Nothing here is a new judgment on the risk itself. The gravité comes from the
atelier 1 feared event, the pertinence and initial likelihood from the atelier 2
couple; atelier 3 adds the route through the ecosystem and the wording, and
carries the rest forward unchanged so atelier 4 receives one object instead of
three to join.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import Gravite, Origin, Pertinence, VraisemblanceInitiale


class StrategicScenario(BaseModel):
    """A retained strategic scenario (conception §17)."""

    id: str
    source_risque_id: str
    objectif_vise_id: str
    couple_id: str

    resume: str  # the route in one sentence, in the organisation's own terms
    justification: str

    # The ecosystem route. Names as the context writes them — a party the study
    # never heard of is not a route, it is an invention (checked in assessment.py).
    parties_prenantes: list[str] = Field(default_factory=list)

    # --- carried from the earlier ateliers, never re-judged here (§17) ---
    biens_essentiels_ids: list[str] = Field(default_factory=list)
    evenements_redoutes_ids: list[str] = Field(default_factory=list)
    gravite: Gravite = Gravite.MINIMALE          # worst feared event on the assets targeted
    pertinence: Pertinence = Pertinence.FAIBLE
    vraisemblance_initiale: VraisemblanceInitiale = VraisemblanceInitiale.V1

    # « pertinence / vraisemblance », the pair atelier 3 reports on (§17 schema).
    # Composed in code from the two fields above, never worded by the model.
    vraisemblance_pertinence: str = ""

    # Set when this scenario is the result of merging several at the count gate,
    # so a reader can see the list was reduced and why (§17 step 21).
    issu_de: list[str] = Field(default_factory=list)

    origin: Origin = Origin.ASSESSMENT
