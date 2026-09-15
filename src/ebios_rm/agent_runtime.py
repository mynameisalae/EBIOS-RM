"""Shared LLM-call plumbing for every Agno-backed runner (conception §3.2).

All runners face the same problem: a free/cheap model intermittently returns an
API error or unparseable text instead of the requested schema, and Agno hands
that back as a raw string on ``response.content``. Every runner therefore needs
the same retry-with-backoff, the same type check, and the same progress output.
This module holds that loop once.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

from ebios_rm.domain.fact import Fact

T = TypeVar("T", bound=BaseModel)


class StructuredCallFailed(RuntimeError):
    """The model could not return the requested schema after every attempt.

    Raised rather than returned so a failed call is never mistaken for a
    methodology outcome (no gaps found, a clean verdict, an empty question list).
    """


# Every LLM call in the project goes through run_structured, so token accounting is
# wired here once. The sink is set by the CLI to persist per mission; unset (default)
# it is a no-op, keeping the library usable without a database.
TokenSink = Callable[[int, int, str], None]
_token_sink: TokenSink | None = None


def set_token_sink(sink: TokenSink | None) -> None:
    """Route token counts (input, output, model) of every call to ``sink``."""
    global _token_sink
    _token_sink = sink


def _record_tokens(response: object) -> None:
    """Report this call's token usage; never let accounting break a run."""
    if _token_sink is None:
        return
    try:
        metrics = getattr(response, "metrics", None)
        if metrics is None:
            return
        model = getattr(getattr(response, "model", None), "id", None) or str(
            getattr(response, "model", "") or "unknown"
        )
        _token_sink(
            int(getattr(metrics, "input_tokens", 0) or 0),
            int(getattr(metrics, "output_tokens", 0) or 0),
            model,
        )
    except Exception:  # noqa: BLE001 — telemetry must never break the audit run
        pass


def manual_call(
    prompt: str,
    schema: type[T],
    *,
    what: str,
    progress: Callable[[str], None] = print,
    poll: float = 2.0,
) -> T:
    """MANUAL_LLM=1 — a human plays the model, via two files per call.

    The prompt and the exact schema are written to ``<what>.prompt.md``; the run
    blocks until a matching ``.response.json`` validates against that schema. For
    running the workshop with no API credit: the audit trail is unaffected, since
    every answer still has to satisfy the same pydantic model.
    """
    directory = Path(os.environ.get("MANUAL_LLM_DIR", "data/manual"))
    directory.mkdir(parents=True, exist_ok=True)
    # Numbered from what the directory already holds, not from a process counter: a
    # relaunched run continues the series instead of overwriting 001 again.
    seq = len(list(directory.glob("*.prompt.md"))) + 1
    # Accents folded before the slug, not dropped by it: « scénarios stratégiques »
    # became "sc-narios-strat-giques", and the human answering has to type that name.
    plain = unicodedata.normalize("NFKD", what.lower())
    slug = re.sub(r"[^a-z0-9]+", "-", "".join(c for c in plain if not unicodedata.combining(c)))
    stem = f"{seq:03d}_{slug.strip('-')[:40]}"
    request, answer = directory / f"{stem}.prompt.md", directory / f"{stem}.response.json"

    request.write_text(
        f"# {what}\n\n## Réponse attendue — JSON conforme à ce schéma\n\n```json\n"
        f"{json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)}\n```\n\n"
        f"## Prompt\n\n{prompt}\n",
        encoding="utf-8",
    )
    progress(f"   [MANUEL] {request}")
    progress(f"   [MANUEL] en attente de {answer.name} (Ctrl+C pour arrêter)")
    while True:
        if answer.exists():
            try:
                return schema.model_validate_json(answer.read_text(encoding="utf-8"))
            except (ValidationError, ValueError) as exc:
                # Removed before anything else: a rejected answer must not survive the
                # message that announces its rejection, or it is read again as valid.
                answer.unlink()
                progress(f"   [MANUEL] réponse invalide : {str(exc)[:300]}")
                progress(f"   [MANUEL] corrigez {answer.name} — nouvelle lecture dans {poll}s")
        time.sleep(poll)


def run_structured(
    agent_factory: Callable[[], object],
    prompt: str,
    schema: type[T],
    *,
    what: str,
    max_attempts: int = 4,
    base_delay: float = 3.0,
    progress: Callable[[str], None] = print,
) -> T:
    """Run one structured call, retrying transient failures with backoff.

    ``agent_factory`` builds a fresh Agno Agent per attempt (they are cheap and
    not safely reusable across failures). Token usage of every attempt — including
    failed ones, which are paid for too — goes to the configured sink.
    """
    if os.environ.get("MANUAL_LLM"):
        return manual_call(prompt, schema, what=what, progress=progress)
    progress(f"   {what}...")
    last: object = None
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            progress(f"   ... nouvel essai {attempt}/{max_attempts} ({what})")
        try:
            response = agent_factory().run(prompt)
            _record_tokens(response)
            content = response.content
        except Exception as exc:  # noqa: BLE001 — Agno/network errors are heterogeneous
            last = exc
        else:
            if isinstance(content, schema):
                return content
            last = content  # raw string: API error or parse failure — retry
        if attempt < max_attempts:
            time.sleep(base_delay * attempt)
    raise _failed(schema, what, max_attempts, last)


async def arun_structured(
    agent_factory: Callable[[], object],
    prompt: str,
    schema: type[T],
    *,
    what: str,
    max_attempts: int = 4,
    base_delay: float = 3.0,
    progress: Callable[[str], None] = print,
) -> T:
    """Async twin of run_structured, for the atelier 4 fan-out (conception §3.1, §18).

    Same retries, type check and token accounting — awaited, so N sub-agents wait on
    the network together, and every token record is still written from the one
    thread that owns the mission database.

    Under MANUAL_LLM the answer file is awaited synchronously, on purpose: one human
    answers one prompt at a time, and prompt files are numbered by counting the
    directory, which concurrent writers would race on.
    """
    if os.environ.get("MANUAL_LLM"):
        return manual_call(prompt, schema, what=what, progress=progress)
    progress(f"   {what}...")
    last: object = None
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            progress(f"   ... nouvel essai {attempt}/{max_attempts} ({what})")
        try:
            response = await agent_factory().arun(prompt)
            _record_tokens(response)
            content = response.content
        except Exception as exc:  # noqa: BLE001 — Agno/network errors are heterogeneous
            last = exc
        else:
            if isinstance(content, schema):
                return content
            last = content
        if attempt < max_attempts:
            await asyncio.sleep(base_delay * attempt)
    raise _failed(schema, what, max_attempts, last)


def _failed(schema: type[BaseModel], what: str, attempts: int, last: object) -> StructuredCallFailed:
    return StructuredCallFailed(
        f"Model did not return {schema.__name__} for {what} after {attempts} attempts. "
        f"Last result: {str(last)[:300]!r}"
    )


def facts_as_json(facts: list[Fact], *, with_origin: bool = False) -> str:
    """Serialise Facts for a prompt: the known field_name -> value view."""
    if with_origin:
        payload = [
            {"field_name": f.field_name, "value": f.value, "origin": f.origin.value}
            for f in facts
        ]
    else:
        payload = {f.field_name: f.value for f in facts if f.value not in (None, "")}
    return json.dumps(payload, ensure_ascii=False, indent=2)
