"""Adapter wiring the real Workshop 3 pipeline into the Orchestrator's
WorkshopRunner protocol (conception §10.2, §17).

Atelier 3 has one interactive step beyond the shared approve/reject gate: the
count gate (§17 steps 19-21), which decides whether the scenario list is even
ready to leave atelier 3. That decision lives inside run(), the same way
Workshop1Runner keeps its unverified-controls review inline — it is atelier 3's
own methodology, not something the Orchestrator's generic gate understands.

Scope, matching the standalone script's own documented limit: run / run_anyway /
cancel are handled here. merge and choose_subset raise WorkshopBlocked with the
same message advance_to_workshop3() gives, rather than silently pretending to
support them.
"""

from __future__ import annotations

from typing import Callable

from ebios_rm.agent_runtime import StructuredCallFailed
from ebios_rm.orchestrator.approval_cli import ask_choice
from ebios_rm.orchestrator.signals import WorkshopBlocked, WorkshopHalted
from ebios_rm.workshops.common import AtelierDataError
from ebios_rm.workshops.workshop1_cadrage.human_interface import ask_justification
from ebios_rm.workshops.workshop3_scenarios_strategiques.agent import AgnoWorkshop3Runner
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import (
    ACTION_CANCEL,
    ACTION_RUN,
    ACTION_RUN_ANYWAY,
    Workshop3Input,
    Workshop3Output,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.workshop import (
    assemble_output,
    gate_for,
    run_workshop3,
)

_GATE_LABELS = {
    ACTION_RUN: "valider cette liste et la transmettre à l'atelier 4",
    ACTION_RUN_ANYWAY: "lancer tout de même, malgré le nombre",
    ACTION_CANCEL: "en rester là (liste conservée, non approuvée)",
}

Ask = Callable[[str], str]
Say = Callable[[str], None]


class Workshop3Runner:
    """WorkshopRunner for atelier 3, backed by the real agent pipeline.

    For automated tests use a fake Workshop3AgentRunner instead — this class
    makes real OpenRouter calls and expects a real terminal for the count-gate
    prompt.
    """

    workshop_number = 3

    def __init__(self, *, io_in: Ask = input, io_out: Say = print) -> None:
        self._io_in = io_in
        self._io_out = io_out

    async def run(self, input: Workshop3Input, mission_id: str) -> Workshop3Output:
        try:
            output = run_workshop3(input, AgnoWorkshop3Runner())
        except AtelierDataError as exc:
            raise WorkshopBlocked(f"Atelier 2 comporte des anomalies bloquantes : {exc}") from exc
        except StructuredCallFailed as exc:
            raise WorkshopBlocked(f"Échec du modèle pendant l'atelier 3 : {exc}") from exc

        gate = gate_for(output.scenarios, n_initial=output.gate_decision.n_initial or len(output.scenarios))
        if not gate.options_offertes:
            return output

        unsupported = [a for a in gate.options_offertes if a not in _GATE_LABELS]
        if unsupported:
            raise WorkshopBlocked(
                f"Le point de comptage propose {unsupported}, non géré par l'Orchestrateur. "
                f"Utilisez python scripts/run_workshop3.py {mission_id} pour fusionner ou "
                "choisir un sous-ensemble, puis reprenez la mission."
            )

        keys = {str(i): action for i, action in enumerate(gate.options_offertes, 1)}
        choice = ask_choice("Que faire de cette liste ?", {k: _GATE_LABELS[a] for k, a in keys.items()},
                             self._io_in, self._io_out)
        action = keys[choice]

        if action == ACTION_CANCEL:
            # A deliberate stop, not a failure: the auditor keeps the list without
            # transmitting it. WorkshopHalted is the Orchestrator's signal for
            # "nothing more to do right now" — the mission pauses, resumable.
            raise WorkshopHalted(f"Point de comptage : liste de {gate.n} scénario(s) non transmise.")

        justification = (
            ask_justification("Motif pour lancer malgré le nombre (obligatoire, §8) : ", self._io_in, self._io_out)
            if action == ACTION_RUN_ANYWAY else ""
        )
        decided = gate.model_copy(update={"action": action, "justification": justification})
        return assemble_output(input, output.scenarios, decided, output.elements_ecartes,
                               human_edits=output.human_edits)

    def stop(self) -> None:
        pass

    async def resume(self, mission_id: str) -> Workshop3Output:
        raise NotImplementedError(
            "Atelier 3 n'a pas de point de reprise interne — un atelier interrompu "
            "doit être refait avec run(), pas repris."
        )

    def summarize_output(self, output: Workshop3Output) -> str:
        gate = output.gate_decision
        return (
            f"{len(output.scenarios)} scénario(s) stratégique(s) — "
            f"point de comptage : {gate.action or 'en attente'} — "
            f"contrôle qualité : {output.quality_report.statut}."
        )
