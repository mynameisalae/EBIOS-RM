"""Narrow, typed inputs handed from one atelier to the next (conception §9, §16-19).

The Orchestrator is the only place these are built — never a workshop, never a
direct pass-through of a previous atelier's full output. Each function here does
one strip: it takes the previous atelier's validated output and returns exactly
the fields the next atelier needs, nothing else.

Workshop2Input is defined here (not inside workshops/workshop2_sources_risque/)
so that whoever implements Workshop 2's own agent/model files never has to touch
this boundary contract, and the Orchestrator never has to import from a workshop
package it does not own.

Workshop3Input, the Workshop 4 sub-agent input (SubAgentInput), and Workshop5Input
are deliberately not defined yet: their constituent domain types (RiskSource,
StrategicScenario, OperationalScenario) are still docstring-only stubs in
ebios_rm.domain. Adding a placeholder shape now would just have to be redone once
each upstream workshop defines its real output — so each adapter is added here
only once the workshop that produces its input actually exists.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebios_rm.domain.essential_asset import EssentialAsset
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output


class Workshop2Input(BaseModel):
    """What Workshop 2 (Sources de risque) receives from Workshop 1 (conception §16).

    Deliberately narrow: biens_supports, baseline_scope_decisions,
    baseline_gaps_full, unverified_controls and human_edits from Workshop1Output
    are NOT included — Workshop 2 has no methodological need for them.
    """

    biens_essentiels: list[EssentialAsset] = Field(default_factory=list)
    evenements_redoutes: list[FearedEvent] = Field(default_factory=list)


def build_workshop2_input(w1_output: Workshop1Output) -> Workshop2Input:
    return Workshop2Input(
        biens_essentiels=w1_output.biens_essentiels,
        evenements_redoutes=w1_output.evenements_redoutes,
    )
