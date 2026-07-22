"""Two-way clarification — the auditor asks, the agent answers, grounded (conception §2)."""

from fakes import FakeClarificationRunner

from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.clarification import clarification_repl
from ebios_rm.mission_context.mission_context import MissionContext


def _context() -> MissionContext:
    return MissionContext(
        organisation_nom="Clinique Test",
        secteur_activite="Santé",
        applicable_frameworks=["RGPD"],
        facts=[
            Fact.declaration("hebergement", "hybride"),
            Fact.declaration("edr_av_deploye", "Microsoft Defender"),
        ],
    )


def _scripted_io(questions: list[str]):
    """io_in that yields each question then '' to end; io_out that captures lines."""
    it = iter(questions + [""])
    out: list[str] = []
    return (lambda _prompt: next(it)), out.append, out


def test_repl_answers_grounded_question_and_cites_facts():
    ask, show, out = _scripted_io(["Quel est l'hebergement ?"])
    transcript = clarification_repl(FakeClarificationRunner(), _context(), io_in=ask, io_out=show)

    assert len(transcript) == 1
    q, ans = transcript[0]
    assert ans.answered is True
    assert "hybride" in ans.answer
    assert ans.based_on_facts == ["hebergement"]
    # The citation is surfaced to the auditor.
    assert any("fondé sur" in line and "hebergement" in line for line in out)


def test_repl_reports_when_information_is_absent():
    ask, show, out = _scripted_io(["Quel est le budget sécurité ?"])  # not in context
    transcript = clarification_repl(FakeClarificationRunner(), _context(), io_in=ask, io_out=show)

    _, ans = transcript[0]
    assert ans.answered is False
    assert any("absente du contexte" in line for line in out)  # never invents (§2)


def test_repl_loops_until_empty_line():
    ask, show, out = _scripted_io([
        "Quel est l'hebergement ?",
        "Quel edr_av_deploye est déployé ?",
    ])
    runner = FakeClarificationRunner()
    transcript = clarification_repl(runner, _context(), io_in=ask, io_out=show)

    assert len(transcript) == 2
    assert runner.calls == ["Quel est l'hebergement ?", "Quel edr_av_deploye est déployé ?"]
