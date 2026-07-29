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
    """Sources disagree on the same field (conception §11) — human resolution mandatory.

    ``declaration`` is the questionnaire's value when there is one. Two supplied
    documents can also disagree while the form says nothing about the field; then
    ``declaration`` is the first document's Fact and ``sources`` names them all, so
    the disagreement is still put to the auditor rather than being decided by
    whichever document happened to be read last.
    """

    field_name: str
    declaration: Fact
    extraction: Fact
    others: list[Fact] = field(default_factory=list)  # further disagreeing documents, if any

    @property
    def has_declaration(self) -> bool:
        """False when the form never answered this field and only documents disagree."""
        return self.declaration.source_document is None


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

    # Grouped, not keyed: several documents can answer the same field, and a dict would
    # keep only the last one read — two documents flatly disagreeing would then pass as
    # a single quiet fact, which is precisely what §11 forbids.
    extr_by_field: dict[str, list[Fact]] = {}
    for f in extraction_facts:
        extr_by_field.setdefault(f.field_name, []).append(f)

    for field_name, decl in decl_by_field.items():
        extractions = extr_by_field.get(field_name, [])
        disagreeing = [e for e in extractions if not values_match(decl.value, e.value)]
        if not extractions:
            result.declaration_only.append(decl)
        elif not disagreeing:
            # Every document agrees with the form: keep the declaration, mark verified.
            result.verified.append(decl.model_copy(update={"confidence": Confidence.HIGH}))
        else:
            result.contradictions.append(Contradiction(
                field_name=field_name, declaration=decl,
                extraction=disagreeing[0], others=disagreeing[1:],
            ))

    for field_name, extractions in extr_by_field.items():
        if field_name in decl_by_field:
            continue
        first = extractions[0]
        disagreeing = [e for e in extractions[1:] if not values_match(first.value, e.value)]
        if disagreeing:
            # The form says nothing, and the documents do not agree with each other.
            result.contradictions.append(Contradiction(
                field_name=field_name, declaration=first,
                extraction=disagreeing[0], others=disagreeing[1:],
            ))
        else:
            result.document_only.append(first)

    return result
