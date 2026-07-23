"""Conversational follow-ups: answer vs question vs garbage (conception §2)."""

from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.conversation import TurnResult
from ebios_rm.mission_context.priority_matrix import FollowUpQuestion
from ebios_rm.domain.enums import PriorityLevel
from ebios_rm.workshops.workshop1_cadrage.human_interface import (
    ConversationalHumanInterface,
    SkipRequested,
)


class ScriptedTurnRunner:
    """Classifies each input by a scripted map: text -> TurnResult."""

    def __init__(self, script: dict[str, TurnResult]) -> None:
        self.script = script
        self.seen: list[str] = []

    def handle_turn(self, question, explanation, user_input, facts, history):
        self.seen.append(user_input)
        return self.script[user_input]


def _io(inputs: list[str]):
    it = iter(inputs)
    out: list[str] = []
    return (lambda _p: next(it)), out.append, out


def _q(blocking=False):
    p = PriorityLevel.CRITICAL if blocking else PriorityLevel.IMPORTANT
    return FollowUpQuestion("edr_av_deploye", "Quel EDR est déployé ?", p, "Un EDR détecte les menaces.")


def test_question_then_answer():
    # Auditor first asks what it means, then answers.
    runner = ScriptedTurnRunner({
        "c'est quoi un EDR ?": TurnResult(is_answer=False, reply="Un EDR surveille les postes."),
        "on a Defender": TurnResult(is_answer=True, answer="Microsoft Defender", reply=""),
    })
    ask, show, out = _io(["c'est quoi un EDR ?", "on a Defender"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    result = hi.ask_followup(_q())
    assert result == "Microsoft Defender"                 # answer captured, not the question
    assert runner.seen == ["c'est quoi un EDR ?", "on a Defender"]
    assert any("Un EDR surveille" in line for line in out)  # agent explained, did not record it


def test_skip_stays_deterministic():
    runner = ScriptedTurnRunner({})  # never called
    ask, show, out = _io(["skip", "pas d'info côté client"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    result = hi.ask_followup(_q(blocking=False))
    assert isinstance(result, SkipRequested)
    assert result.reason == "pas d'info côté client"
    assert runner.seen == []  # skip bypasses the LLM


def test_garbage_then_answer():
    runner = ScriptedTurnRunner({
        "asdf": TurnResult(is_answer=False, reply="Je n'ai pas compris. La question porte sur l'EDR."),
        "aucun EDR": TurnResult(is_answer=True, answer="Aucun EDR déployé"),
    })
    ask, show, out = _io(["asdf", "aucun EDR"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.ask_followup(_q()) == "Aucun EDR déployé"
