"""Final human gate on a workshop result (conception §2, §8)."""

from ebios_rm.mission_context.clarification import _is_stop
from ebios_rm.workshops.workshop1_cadrage.human_interface import approve_workshop


def _io(inputs: list[str]):
    it = iter(inputs)
    out: list[str] = []
    return (lambda _p: next(it)), out.append, out


def test_approval_yes():
    ask, show, _ = _io(["oui"])
    assert approve_workshop("l'atelier 1", io_in=ask, io_out=show) == (True, "")


def test_rejection_requires_non_empty_reason():
    ask, show, out = _io(["non", "", "scénarios incomplets"])
    approved, reason = approve_workshop("l'atelier 1", io_in=ask, io_out=show)
    assert approved is False
    assert reason == "scénarios incomplets"
    assert any("une vraie raison" in line for line in out)


def test_unclear_choice_reprompts():
    ask, show, out = _io(["peut-être", "oui"])
    assert approve_workshop("l'atelier 1", io_in=ask, io_out=show)[0] is True
    assert any("décision explicite" in line for line in out)


def test_stop_phrases_end_clarification_without_llm_call():
    assert _is_stop("non merci") and _is_stop("Stop.") and _is_stop("aucune question")
    assert not _is_stop("est-ce qu'il manque autre chose ?")
