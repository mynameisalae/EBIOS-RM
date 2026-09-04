"""Workshop 3 — Scénarios stratégiques et point de validation de comptage (conception §17).

Single agent with an internal propose -> critique loop. Holds the only
validation point on the scenario count N; workshop 4 has no equivalent
gate. Merge/subset choices re-evaluate N against the same thresholds
recursively, always with a non-empty justification.

Atelier 2 asked which sources de risque are pertinent and what they would be
after. Atelier 3 asks by which route they would get there: one scenario per
retained SR/OV couple, told through the parties prenantes of the ecosystem, with
the gravité and the ratings carried forward from the ateliers before it rather
than judged again.

Public entry points:
    build_workshop3_input(mission_context, w1_output, w2_output) -> Workshop3Input
    ask_session_questions(w3_input, human) -> Workshop3Input
    run_workshop3(w3_input, runner) -> Workshop3Output
    gate_for(scenarios) / assemble_output(...)  — the count gate, applied by the caller
"""

from ebios_rm.workshops.workshop3_scenarios_strategiques.models import (
    GateDecision,
    Workshop3Input,
    Workshop3Output,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.questions import (
    ask_session_questions,
    session_questions,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.workshop import (
    Atelier2DataError,
    assemble_output,
    build_workshop3_input,
    gate_for,
    run_workshop3,
)

__all__ = [
    "Atelier2DataError",
    "GateDecision",
    "Workshop3Input",
    "Workshop3Output",
    "ask_session_questions",
    "assemble_output",
    "build_workshop3_input",
    "gate_for",
    "run_workshop3",
    "session_questions",
]
