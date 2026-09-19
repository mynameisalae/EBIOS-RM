"""Workshop 5 — Traitement du risque (conception §19).

Single agent consuming the finalized atelier 4 output. For each ATT&CK
technique cited across the approved operational scenarios, it looks up real
mitigations via the ATT&CK toolkit (get_mitigations_for_technique — genuine
tool calling, the first atelier of the project to use it rather than resolving
everything in code beforehand, §3.1, §10.1) and proposes treatment measures,
weighed on cost, effectiveness, delay and priority. Measures addressing
baseline-gap weaknesses (including RGPD Article 32) are included too; RGPD
entries with no covers_risk_category stay out of this technical scope.

Produces towards: the reporting agent (conception §20).

Public entry points:
    build_workshop5_input(mission_context, w1_output, w4_output) -> Workshop5Input
    cited_technique_ids(w5_input) -> set[str]
    run_workshop5(w5_input, runner, attack_repo, w4_output, w1_output) -> Workshop5Output
"""

from ebios_rm.workshops.workshop5_traitement_risque.models import (
    ElementEcarte,
    MesureProposal,
    MesuresBatch,
    Workshop5Input,
    Workshop5Output,
)
from ebios_rm.workshops.workshop5_traitement_risque.workshop import (
    build_workshop5_input,
    cited_technique_ids,
    run_workshop5,
)

__all__ = [
    "ElementEcarte",
    "MesureProposal",
    "MesuresBatch",
    "Workshop5Input",
    "Workshop5Output",
    "build_workshop5_input",
    "cited_technique_ids",
    "run_workshop5",
]
