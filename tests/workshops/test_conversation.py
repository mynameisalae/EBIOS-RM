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
        "c'est quoi un EDR ?": TurnResult(intent="question", reply="Un EDR surveille les postes."),
        "on a Defender": TurnResult(intent="answer", answer="Microsoft Defender", reply=""),
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


def test_vague_answer_is_not_recorded():
    # A bare "oui" to a question expecting a product -> insufficient, loop must not advance.
    runner = ScriptedTurnRunner({
        "oui": TurnResult(intent="insufficient", reply="Lequel exactement ? Précisez le produit."),
        "Defender": TurnResult(intent="answer", answer="Microsoft Defender", reply="Noté."),
    })
    ask, show, out = _io(["oui", "Defender"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.ask_followup(_q()) == "Microsoft Defender"
    assert runner.seen == ["oui", "Defender"]


def test_courtesy_question_in_reply_still_counts_as_answer():
    # A trailing "Autre chose ?" must not block a genuine answer (old '?' heuristic did).
    runner = ScriptedTurnRunner({
        "Defender": TurnResult(intent="answer", answer="Defender", reply="Noté. Autre chose ?"),
    })
    ask, show, out = _io(["Defender"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)
    assert hi.ask_followup(_q()) == "Defender"


def test_bang_prefix_forces_raw_answer_on_blocking_question():
    # Agent keeps pushing back on a CRITICAL question; auditor overrules (§2).
    runner = ScriptedTurnRunner({
        "on ne sait pas": TurnResult(intent="insufficient", reply="Précisez l'annuaire utilisé."),
    })
    ask, show, out = _io(["on ne sait pas", "!on ne sait pas"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.ask_followup(_q(blocking=True)) == "on ne sait pas"
    assert runner.seen == ["on ne sait pas"]  # forced answer never reaches the LLM


def test_override_is_advertised_after_repeated_pushback():
    stuck = TurnResult(intent="insufficient", reply="Précisez.")
    runner = ScriptedTurnRunner({"bof": stuck})
    ask, show, out = _io(["bof", "bof", "bof", "!rien de plus"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.ask_followup(_q(blocking=True)) == "rien de plus"
    assert any("préfixez '!'" in line for line in out)


def test_history_persists_across_questions():
    runner = ScriptedTurnRunner({
        "Defender": TurnResult(intent="answer", answer="Defender"),
        "et la question d'avant ?": TurnResult(intent="question", reply="C'était l'EDR."),
        "oui separe": TurnResult(intent="answer", answer="Wi-Fi invité séparé"),
    })
    ask, show, out = _io(["Defender", "et la question d'avant ?", "oui separe"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    hi.ask_followup(_q())
    hi.ask_followup(FollowUpQuestion("wifi", "Wi-Fi séparés ?", PriorityLevel.IMPORTANT, ""))
    # Second question still sees the first exchange.
    assert len(hi._history) == 6
    assert hi._history[0]["content"] == "Defender"


def test_review_flag_is_conversational():
    from ebios_rm.mission_context.ingestion import AnswerFlag

    runner = ScriptedTurnRunner({
        "je comprends pas": TurnResult(intent="question", reply="On veut un nombre de personnes."),
        "420": TurnResult(intent="answer", answer="420"),
    })
    ask, show, out = _io(["je comprends pas", "420"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)
    flag = AnswerFlag("taille_effectif", "Effectif total ?", "beaucoup", "unclear", "trop vague")

    assert hi.review_flag(flag) == "420"   # typo/question no longer stored as the value


def test_garbage_then_answer():
    runner = ScriptedTurnRunner({
        "asdf": TurnResult(intent="question", reply="Je n'ai pas compris. La question porte sur l'EDR."),
        "aucun EDR": TurnResult(intent="answer", answer="Aucun EDR déployé"),
    })
    ask, show, out = _io(["asdf", "aucun EDR"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.ask_followup(_q()) == "Aucun EDR déployé"
