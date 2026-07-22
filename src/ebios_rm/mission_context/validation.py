"""The three validation cases for intake vs. supplied documents (conception §11).

    | Case                     | Result                                           |
    | ------------------------ | ------------------------------------------------ |
    | Identical information    | Verified, high confidence                        |
    | Document-only            | Proposed to the auditor for simple confirmation  |
    | Contradiction            | Flagged; mandatory human resolution, never auto  |

A contradiction is NEVER resolved automatically (§6, §11): both values and their
origins are carried side by side and the mission cannot advance on that point
without an explicit human decision. The AI never assumes a missing value and
never ignores a contradiction (principe directeur, §2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ebios_rm.domain.enums import Confidence, FactStatus
from ebios_rm.domain.fact import Fact


def _normalize(value: object) -> object:
    """Comparison-normal form: trimmed lowercase strings, order-insensitive collections."""
    if isinstance(value, str):
        return value.strip().casefold()
    if isinstance(value, (list, tuple, set)):
        return frozenset(_normalize(v) for v in value)
    return value


def values_match(a: object, b: object) -> bool:
    return _normalize(a) == _normalize(b)


@dataclass
class Contradiction:
    """Two sources disagree on the same field (conception §11) — human resolution mandatory."""

    field_name: str
    declaration: Fact
    extraction: Fact


@dataclass
class ValidationResult:
    """Outcome of matching declaration Facts against extraction Facts (conception §11)."""

    verified: list[Fact] = field(default_factory=list)          # identical -> high confidence
    document_only: list[Fact] = field(default_factory=list)     # doc-only -> confirm, no needless question
    declaration_only: list[Fact] = field(default_factory=list)  # form value with no document counterpart
    contradictions: list[Contradiction] = field(default_factory=list)  # never auto-resolved

    @property
    def has_unresolved_contradictions(self) -> bool:
        return len(self.contradictions) > 0


def validate(declaration_facts: list[Fact], extraction_facts: list[Fact]) -> ValidationResult:
    """Sort every field into one of the three validation cases (conception §11).

    Contradictions are collected, never resolved here — resolution is the
    auditor's, driven later through the HumanInterface.
    """
    result = ValidationResult()
    decl_by_field = {f.field_name: f for f in declaration_facts}
    extr_by_field = {f.field_name: f for f in extraction_facts}

    for field_name, decl in decl_by_field.items():
        extr = extr_by_field.get(field_name)
        if extr is None:
            result.declaration_only.append(decl)
        elif values_match(decl.value, extr.value):
            # Identical: keep the declaration (highest confidence), mark verified.
            verified = decl.model_copy(update={"confidence": Confidence.HIGH})
            result.verified.append(verified)
        else:
            result.contradictions.append(
                Contradiction(field_name=field_name, declaration=decl, extraction=extr)
            )

    # Extraction facts with no declaration counterpart: propose for simple confirmation.
    for field_name, extr in extr_by_field.items():
        if field_name not in decl_by_field:
            result.document_only.append(extr)

    return result
