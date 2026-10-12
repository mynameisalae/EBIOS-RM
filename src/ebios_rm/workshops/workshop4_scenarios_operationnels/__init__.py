"""Workshop 4 — Scénarios opérationnels, fan-out / fan-in (conception §18).

The only multi-agent workshop: N independent Agno Agent instances, never Team,
one per strategic scenario, dispatched via asyncio.gather. Baseline gaps arrive
stripped of framework/control_id (conception §12.3, §15) — this workshop only
ever sees the raw weakness, never its regulatory origin.

Atelier 3 said by which route a source de risque would reach the organisation.
Atelier 4 says how the attack would actually unfold on the support assets, in ATT&CK
terms, and how likely it is to succeed given the real security baseline. Every
technique id is checked against the ATT&CK base in code, every gap entry must say
something, and the risk level is read off a fixed matrix — the sub-agents propose,
the auditor reviews the N results together and decides.

Public entry points:
    build_workshop4_input(mission_context, w1, w2, w3) -> Workshop4Input
    ask_session_questions(w4_input, human) -> Workshop4Input
    initial_output(w4_input, attck_version) -> Workshop4Output
    run_analyses(w4_input, output, runner, catalogue, checkpoint=...) -> Workshop4Output
    run_coherence(w4_input, output, runner) / assemble_output(w4_input, output, catalogue)
"""

from ebios_rm.workshops.workshop4_scenarios_operationnels.models import (
    Workshop4Input,
    Workshop4Output,
)
from ebios_rm.workshops.workshop4_scenarios_operationnels.questions import (
    ask_session_questions,
    session_questions,
)
from ebios_rm.workshops.workshop4_scenarios_operationnels.workshop import (
    assemble_output,
    build_workshop4_input,
    initial_output,
    pending_scenarios,
    run_analyses,
    run_coherence,
    run_enumeration,
    scenarios_without_modes,
)

__all__ = [
    "Workshop4Input",
    "Workshop4Output",
    "ask_session_questions",
    "assemble_output",
    "build_workshop4_input",
    "initial_output",
    "pending_scenarios",
    "run_analyses",
    "run_enumeration",
    "scenarios_without_modes",
    "run_coherence",
    "session_questions",
]
