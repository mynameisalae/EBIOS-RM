"""Shared LLM-call plumbing for every Agno-backed runner (conception §3.2).

All runners face the same problem: a free/cheap model intermittently returns an
API error or unparseable text instead of the requested schema, and Agno hands
that back as a raw string on ``response.content``. Every runner therefore needs
the same retry-with-backoff, the same type check, and the same progress output.
This module holds that loop once.
"""

from __future__ import annotations

import json
import time
from typing import Callable, TypeVar

from pydantic import BaseModel

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
    raise StructuredCallFailed(
        f"Model did not return {schema.__name__} for {what} after {max_attempts} attempts. "
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
