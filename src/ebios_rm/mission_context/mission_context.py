"""Mission Context — the single source of truth (conception §11, §14).

No workshop ever operates on a raw PDF, DOCX, or the raw form. Everything flows
through this pipeline:

    filled questionnaire + supplied documents
        -> extraction (source_quote mandatory)
        -> validation (identical / document-only / contradiction)
        -> Mission Context (one object, entirely composed of validated Facts)
        -> Workshop 1

This module owns the pure end of that pipeline: assembling the final validated
Fact set into a MissionContext. The interactive middle (confirmation,
contradiction resolution, follow-up questions) is driven by intake_ingestion
through the HumanInterface, because those are the auditor's decisions (§2).
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import FactStatus
from ebios_rm.domain.fact import Fact


class MissionContext(BaseModel):
    """The consolidated, validated-Fact view handed to Workshop 1 (conception §11, §14)."""

    organisation_nom: str
    secteur_activite: str
    applicable_frameworks: list[str]
    facts: list[Fact] = Field(default_factory=list)
    documents_fournis: list[str] = Field(default_factory=list)

    def get(self, field_name: str) -> Fact | None:
        """The single Fact for a field, if present."""
        for fact in self.facts:
            if fact.field_name == field_name:
                return fact
        return None

    def value(self, field_name: str) -> object | None:
        fact = self.get(field_name)
        return fact.value if fact is not None else None

    def facts_by_status(self, status: FactStatus) -> list[Fact]:
        return [f for f in self.facts if f.status is status]

    @property
    def has_unresolved(self) -> bool:
        """True while any Fact still needs a human decision before workshops may consume it."""
        blocking = {FactStatus.CONTRADICTION, FactStatus.EXTRACTED, FactStatus.ASSESSED, FactStatus.MISSING}
        return any(f.status in blocking for f in self.facts)


_DEFAULT_FRAMEWORKS = ["ISO27001", "ANSSI_hygiene", "RGPD", "NIST"]


def _parse_frameworks(value: object) -> list[str]:
    """Normalise a frameworks answer (list, or comma/semicolon-separated text) to a list."""
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        parts = [p.strip() for chunk in value.split(";") for p in chunk.split(",")]
        return [p for p in parts if p]
    return []


def tokens(text: str) -> set[str]:
    """Accent-free lowercase word/number tokens: « Norme ISO 27001 » -> {norme, iso, 27001}.

    Shared with the expert review, which keys its question ids on the same set so
    case, accents, punctuation and word order cannot pass as a new question.
    """
    plain = unicodedata.normalize("NFKD", text.casefold())
    return set(re.findall(r"[a-z]+|\d+", "".join(c for c in plain if not unicodedata.combining(c))))


@lru_cache(maxsize=1)
def _known_framework_ids() -> tuple[str, ...]:
    """Loadable plugin ids — read once, the plugin folder does not change mid-run."""
    from ebios_rm.plugins.registry import discover_frameworks  # local import: avoids a cycle

    return tuple(p.id for p in discover_frameworks())


def _canonical_frameworks(parts: list[str], known_ids: tuple[str, ...] | None = None) -> list[str]:
    """Map free-text framework mentions onto the plugin ids that can actually be loaded (§12.5).

    A real answer names a referential in prose (« Norme ISO 27001 », « ISO/IEC
    27001:2022 »); the plugin id is ISO27001. Without this every such mention
    reports as an unloaded framework even when its controls are right there.
    Matching is by tokens, so word order and punctuation do not matter, and
    ISO 27005 never matches ISO 27001.

    A mention matching no plugin is kept verbatim: it stops the workshop at the
    controls gate, where the auditor loads it or withdraws it with a reason (§2).
    """
    known = {pid: tokens(pid) for pid in (known_ids or _known_framework_ids())}
    out: list[str] = []
    for part in parts:
        part_tokens = tokens(part)
        matched = [pid for pid, toks in known.items() if toks and toks <= part_tokens]
        # Keep only the most specific match: « NIST 800-53 » satisfies both NIST and a
        # future NIST80053 plugin, and returning both would declare two referentials
        # where the auditor named one.
        matched = [p for p in matched if not any(known[p] < known[o] for o in matched)]
        out.extend(matched or [part])
    return list(dict.fromkeys(out))


def assemble_from_facts(facts: list[Fact]) -> MissionContext:
    """Build a MissionContext from a validated Fact set keyed by questionnaire id.

    The identity fields are read from the Facts themselves (conception §11, §11.1).
    """
    values = {f.field_name: f.value for f in facts if f.value not in (None, "")}
    documents = _parse_frameworks(values.get("documents_fournis"))  # reuse the list normaliser
    return MissionContext(
        organisation_nom=str(values.get("organisation_nom") or "Organisation non renseignée"),
        secteur_activite=str(values.get("secteur_activite") or "Secteur non renseigné"),
        applicable_frameworks=(
            _canonical_frameworks(_parse_frameworks(values.get("applicable_frameworks")))
            or list(_DEFAULT_FRAMEWORKS)
        ),
        facts=facts,
        documents_fournis=documents,
    )
