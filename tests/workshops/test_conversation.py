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


# --- skip must be typed explicitly; a stray Enter is never a decision (§8) ---

def test_blank_line_does_not_start_a_skip():
    runner = ScriptedTurnRunner({"Defender": TurnResult(intent="answer", answer="Defender")})
    ask, show, out = _io(["", "Defender"])          # Enter, then a real answer
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.ask_followup(_q()) == "Defender"      # blank re-prompted, no skip flow
    assert any("tapez 'skip'" in line for line in out)


def test_typed_skip_still_requires_a_reason():
    # Empty reason -> the skip is not accepted and the question comes back, so a
    # mistyped 'skip' is escapable by simply answering.
    runner = ScriptedTurnRunner({})
    ask, show, out = _io(["skip", "", "skip", "client injoignable"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    result = hi.ask_followup(_q())
    assert isinstance(result, SkipRequested)
    assert result.reason == "client injoignable"
    assert runner.seen == []                        # skip never reaches the LLM
    assert any("une vraie raison" in line for line in out)


def test_skip_is_refused_on_a_blocking_question():
    runner = ScriptedTurnRunner({"Paris": TurnResult(intent="answer", answer="Paris")})
    ask, show, out = _io(["skip", "Paris"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.ask_followup(_q(blocking=True)) == "Paris"
    assert any("ne peut pas être passée" in line for line in out)


# --- a real answer typed into the skip-reason box is not lost (live-run finding) ---

_LONG_ANSWER = ("Nous utilisons Microsoft Defender for Endpoint en version 7.12, déployé sur "
                "l'ensemble du parc, avec des mises à jour automatiques quotidiennes.")


def test_substantive_skip_reason_can_be_recorded_as_the_answer():
    runner = ScriptedTurnRunner({})
    ask, show, out = _io(["skip", _LONG_ANSWER, "o"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.ask_followup(_q()) == _LONG_ANSWER   # becomes a Fact, not a skip justification


def test_substantive_skip_reason_still_skips_when_refused():
    runner = ScriptedTurnRunner({})
    ask, show, out = _io(["skip", _LONG_ANSWER, "n"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    result = hi.ask_followup(_q())
    assert isinstance(result, SkipRequested) and result.reason == _LONG_ANSWER


def test_answer_or_skip_requires_an_explicit_choice():
    # Defaulting either way is silent: it discards a real answer, or files a skip
    # motive as one. Anything but oui/non re-asks (§2).
    runner = ScriptedTurnRunner({})
    ask, show, out = _io(["skip", _LONG_ANSWER, "", "peut-être", "non"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert isinstance(hi.ask_followup(_q()), SkipRequested)
    assert sum("décision explicite" in line for line in out) == 2


def test_short_skip_reason_is_never_second_guessed():
    runner = ScriptedTurnRunner({})
    ask, show, out = _io(["skip", "client injoignable"])   # no extra prompt consumed
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)
    assert isinstance(hi.ask_followup(_q()), SkipRequested)


def test_punctuation_only_justification_is_refused():
    runner = ScriptedTurnRunner({})
    ask, show, out = _io(["skip", ":::::", "skip", "8", "skip", "non applicable ici"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    result = hi.ask_followup(_q())
    assert isinstance(result, SkipRequested) and result.reason == "non applicable ici"


# --- blank presses must offer the same way out as conversational pushback ---

def test_repeated_blank_input_advertises_the_override():
    runner = ScriptedTurnRunner({})
    ask, show, out = _io(["", "", "", "!aucune information disponible"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.ask_followup(_q(blocking=True)) == "aucune information disponible"
    assert any("préfixez '!'" in line for line in out)


# --- a hand-typed contradiction resolution is plausibility-checked (§11) ---

def _contradiction():
    from ebios_rm.mission_context.validation import Contradiction

    return Contradiction(
        field_name="organisation_nom",
        declaration=Fact.declaration("organisation_nom", "Horizon Télésanté"),
        extraction=Fact.extraction("organisation_nom", "Horizon Telesante SAS",
                                   source_document="statuts.pdf", source_quote="Horizon Telesante SAS"),
    )


def test_implausible_typed_resolution_is_refused_then_corrected():
    runner = ScriptedTurnRunner({
        "C:\\Users\\aud\\Desktop\\notes.txt": TurnResult(
            intent="insufficient", reply="Cela ressemble à un chemin de fichier, pas à un nom."),
        "Horizon Télésanté SAS": TurnResult(intent="answer", answer="Horizon Télésanté SAS"),
    })
    ask, show, out = _io(["C:\\Users\\aud\\Desktop\\notes.txt", "Horizon Télésanté SAS"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.resolve_contradiction(_contradiction()) == "Horizon Télésanté SAS"


def test_typed_resolution_can_be_forced_through():
    runner = ScriptedTurnRunner({})
    ask, show, out = _io(["!Horizon"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.resolve_contradiction(_contradiction()) == "Horizon"
    assert runner.seen == []   # the override never reaches the LLM (§2)


def test_listed_choice_still_bypasses_the_check():
    runner = ScriptedTurnRunner({})
    ask, show, out = _io(["2"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.resolve_contradiction(_contradiction()) == "Horizon Telesante SAS"


# --- a turn can be an answer AND a follow-up (live-run finding) ---

def test_a_follow_up_is_actually_asked_instead_of_being_printed_and_lost():
    # The live run answered, the agent asked "et vos menaces principales ?" in the same
    # turn, and the loop advanced — the question appeared on screen with no prompt behind it.
    runner = ScriptedTurnRunner({
        "on a ISO 27001 et SOC 2": TurnResult(
            intent="answer_and_more", answer="ISO 27001 et SOC 2",
            reply="Noté. Vos hébergeurs sont-ils audités chaque année ?"),
        "oui, audit annuel": TurnResult(intent="answer", answer="audit annuel"),
    })
    ask, show, out = _io(["on a ISO 27001 et SOC 2", "oui, audit annuel"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    result = hi.ask_followup(_q())
    assert "ISO 27001 et SOC 2" in result and "audit annuel" in result   # both halves kept
    assert runner.seen == ["on a ISO 27001 et SOC 2", "oui, audit annuel"]


def test_endless_follow_ups_cannot_trap_the_auditor():
    always_more = TurnResult(intent="answer_and_more", answer="ok", reply="Et encore ?")
    runner = ScriptedTurnRunner({"ok": always_more})
    ask, show, out = _io(["ok"] * 10)
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    hi.ask_followup(_q())                       # returns rather than looping forever
    assert len(runner.seen) <= hi.MAX_PUSHBACKS + 1


def test_a_long_answer_is_recorded_in_the_auditors_own_words():
    # `answer` is the model's summary; a summary of a long answer drops most of it.
    long_answer = ("Nos serveurs de production sont à Tanger, les sauvegardes chiffrées "
                   "sont hébergées en Europe, et tout accès distant passe par le VPN.")
    runner = ScriptedTurnRunner({
        long_answer: TurnResult(intent="answer", answer="Tanger", reply="Noté."),
    })
    ask, show, out = _io([long_answer])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.ask_followup(_q()) == long_answer


def test_a_garbled_short_reply_still_benefits_from_normalisation():
    runner = ScriptedTurnRunner({
        "zes it is": TurnResult(intent="answer", answer="Oui, la MFA est en place"),
    })
    ask, show, out = _io(["zes it is"])
    hi = ConversationalHumanInterface(runner, io_in=ask, io_out=show)

    assert hi.ask_followup(_q()) == "Oui, la MFA est en place"
