"""Human edits on a workshop output — the auditor corrects, with provenance (conception §2, §8).

Rejection asks the agent to redo; an edit is the other tool: the auditor fixes one
value directly (a gravité, a weakness wording, a wrong asset) without spending an
LLM call and without disturbing the rest of the output.

Every edit is recorded inside the output under ``human_edits``: what changed, from
what, to what, by whom, when, and why. Without that trail a changed gravité in an
audit report is unattributable — the justification is mandatory (§8), and the
report agent (§20) reads these entries to show what the auditor overrode.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

EDITS_KEY = "human_edits"


class EditError(ValueError):
    """The requested edit does not address an existing value, or lacks a justification."""


def _split(path: str) -> list[str]:
    parts = [p for p in path.split(".") if p]
    if not parts:
        raise EditError("Chemin vide.")
    return parts


def _resolve(container: Any, parts: list[str]) -> tuple[Any, str | int]:
    """Walk to the parent of the target and return (parent, key). List indices are numeric parts."""
    current = container
    for part in parts[:-1]:
        current = _child(current, part)
    return current, _key(current, parts[-1])


def _key(container: Any, part: str) -> str | int:
    if isinstance(container, list):
        if not part.lstrip("-").isdigit():
            raise EditError(f"Index de liste attendu, reçu « {part} ».")
        index = int(part)
        if not -len(container) <= index < len(container):
            raise EditError(f"Index hors limites : {part}.")
        return index
    if isinstance(container, dict):
        if part not in container:
            raise EditError(f"Champ inconnu : « {part} ».")
        return part
    raise EditError(f"Impossible de descendre dans « {part} ».")


def _child(container: Any, part: str) -> Any:
    return container[_key(container, part)]


def get_value(output: dict, path: str) -> Any:
    parent, key = _resolve(output, _split(path))
    return parent[key]


def apply_edit(
    output: dict, path: str, new_value: Any, *, justification: str, edited_by: str = "auditor"
) -> dict:
    """Return a copy of ``output`` with ``path`` set to ``new_value`` and the edit recorded.

    The path must already exist — an edit corrects a value the agent produced, it
    never invents a new field (that would be an unsourced assertion, §2).
    """
    if not justification or not justification.strip():
        raise EditError("Une justification non vide est obligatoire pour toute modification (§8).")

    edited = _deep_copy(output)
    parent, key = _resolve(edited, _split(path))
    old_value = parent[key]
    parent[key] = new_value

    edited.setdefault(EDITS_KEY, []).append({
        "path": path,
        "old_value": old_value,
        "new_value": new_value,
        "edited_by": edited_by,
        "edited_at": datetime.now(timezone.utc).isoformat(),
        "justification": justification.strip(),
    })
    return edited


def _deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_copy(v) for v in value]
    return value
