"""Workshop 5 — Traitement du risque (conception §19; méthode atelier 5).

Single agent consuming the finalised output of ateliers 1 to 4. The method's five
activities, in order: build and grade the risk map (5-1), decide what is acceptable and
which treatment option applies (5-2), write the treatment plan in its four axes (5-3),
re-evaluate what remains and have it formally accepted (5-4), and set up the monitoring
framework (5-5).

Three rules the code enforces rather than trusts: a risk inherits its gravité from
atelier 1 and its vraisemblance from the mode opératoire atelier 4 retained — nothing is
re-rated here; a security measure lowers the vraisemblance, never the gravité, so the
residual re-evaluation may only move the likelihood downwards and only as far as the
retained measures claim; and the two decisions the method puts on people — the treatment
option per risk and the acceptance of the residual risks — are never asked of the model.

ATT&CK mitigations for the techniques the modes cite are read from the base in code
(AttackRepository.mitigations_for) and injected into the prompt, so a proposed measure
can only cite ids the base returned.

Public entry points:
    build_workshop5_input(mission_context, w1, w2, w3, w4) -> Workshop5Input
    ask_session_questions(w5_input, human) -> Workshop5Input
    initial_output(w5_input, attck_version) -> Workshop5Output      # 5-1
    formulate(w5_input, output, runner)                             # 5-1
    run_mesures(w5_input, output, runner, mitigations, risques)     # 5-3
    run_residuel(w5_input, output, runner, risques)                 # 5-4
    run_cadre(w5_input, output, runner, comite=..., cycles=...)     # 5-5
    assemble_output(w5_input, output) / techniques_citees(w5_input)
"""

from ebios_rm.workshops.workshop5_traitement_risque.models import (
    Workshop5Input,
    Workshop5Output,
)
from ebios_rm.workshops.workshop5_traitement_risque.questions import (
    ask_session_questions,
    session_questions,
)
from ebios_rm.workshops.workshop5_traitement_risque.workshop import (
    assemble_output,
    build_workshop5_input,
    formulate,
    initial_output,
    run_cadre,
    run_mesures,
    run_residuel,
    techniques_citees,
)

__all__ = [
    "Workshop5Input",
    "Workshop5Output",
    "ask_session_questions",
    "assemble_output",
    "build_workshop5_input",
    "formulate",
    "initial_output",
    "run_cadre",
    "run_mesures",
    "run_residuel",
    "session_questions",
    "techniques_citees",
]
