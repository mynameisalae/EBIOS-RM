"""MANUAL_LLM: the answer file must satisfy the schema, exactly like a model reply."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from ebios_rm.agent_runtime import manual_call, run_structured


class Reply(BaseModel):
    verdict: str
    score: int


def test_manual_call_reads_a_valid_response(tmp_path, monkeypatch):
    monkeypatch.setenv("MANUAL_LLM_DIR", str(tmp_path))
    (tmp_path / "001_essai.response.json").write_text(
        '{"verdict": "conforme", "score": 3}', encoding="utf-8"
    )

    result = manual_call("prompt", Reply, what="essai", progress=lambda _: None, poll=0)

    assert result == Reply(verdict="conforme", score=3)
    written = (tmp_path / "001_essai.prompt.md").read_text(encoding="utf-8")
    assert "prompt" in written and '"score"' in written  # schema is handed to the human


def test_manual_mode_never_calls_the_model(tmp_path, monkeypatch):
    monkeypatch.setenv("MANUAL_LLM", "1")
    monkeypatch.setenv("MANUAL_LLM_DIR", str(tmp_path))
    (tmp_path / "001_essai.response.json").write_text(
        '{"verdict": "ecart", "score": 1}', encoding="utf-8"
    )

    def explode():
        raise AssertionError("MANUAL_LLM must not build an Agno agent")

    result = run_structured(explode, "prompt", Reply, what="essai", progress=lambda _: None)

    assert result.verdict == "ecart"


def test_invalid_response_is_rejected_not_coerced(tmp_path, monkeypatch):
    monkeypatch.setenv("MANUAL_LLM_DIR", str(tmp_path))
    answer = tmp_path / "001_essai.response.json"
    answer.write_text('{"verdict": "conforme"}', encoding="utf-8")  # score missing

    # poll=0 with a single bad file: it is deleted, then the loop spins — so stop at
    # the first rejection rather than waiting forever.
    seen: list[str] = []

    def progress(line):
        seen.append(line)
        if "invalide" in line:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        manual_call("prompt", Reply, what="essai", progress=progress, poll=0)
    assert not answer.exists()
