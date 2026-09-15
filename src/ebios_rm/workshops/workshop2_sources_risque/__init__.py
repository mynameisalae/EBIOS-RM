"""Workshop 2 — Sources de risque et objectifs visés (white-box atelier 2).

Atelier 1 asked « qu'est-ce qui a de la valeur et sur quoi cela repose ? ».
Atelier 2 changes perspective: « quelles sources de risque sont pertinentes, et
quels objectifs peuvent-elles viser ? ». Support assets stay important, but they
never become an SR or an OV by themselves.

Consumes a narrow, justified input (Workshop2Input) built from the Mission Context
and the atelier 1 output — never the security-baseline gaps, which answer *would
an attacker succeed* and belong to atelier 4.

Public entry points:
    build_workshop2_input(mission_context, w1_output) -> Workshop2Input
    ask_session_questions(w2_input, human) -> Workshop2Input
    run_workshop2(w2_input, runner, base) -> Workshop2Output
"""

from ebios_rm.workshops.workshop2_sources_risque.models import (
    Workshop2Input,
    Workshop2Output,
)
from ebios_rm.workshops.workshop2_sources_risque.questions import (
    ask_session_questions,
    session_questions,
)
from ebios_rm.workshops.workshop2_sources_risque.workshop import (
    ALL_BLOCKS,
    BLOCK_COUPLES,
    BLOCK_OBJECTIFS,
    BLOCK_SOURCES,
    Atelier1DataError,
    build_workshop2_input,
    run_workshop2,
)

__all__ = [
    "ALL_BLOCKS",
    "BLOCK_COUPLES",
    "BLOCK_OBJECTIFS",
    "BLOCK_SOURCES",
    "Atelier1DataError",
    "Workshop2Input",
    "Workshop2Output",
    "ask_session_questions",
    "build_workshop2_input",
    "run_workshop2",
    "session_questions",
]
