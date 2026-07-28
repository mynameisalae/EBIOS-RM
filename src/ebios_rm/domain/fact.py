"""The Fact model — every assertion about the audited organization (conception §5, §14).

Scope rule (§5.2): only a field that asserts something about the audited
organization (infrastructure, control, history, policy) becomes a Fact.
Internal bookkeeping data (technical ids, timestamps) stays a plain value.

Provenance discipline is enforced here, not left to the caller:
- origin == extraction  -> source_quote must be present and non-empty (§5.3);
  any extraction without a citation is invalidated by code before it ever
  reaches the auditor.
- origin == assessment  -> assessment_basis must be non-empty (§5.1).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from ebios_rm.domain.enums import Confidence, FactStatus, Origin


class Fact(BaseModel):
    """A single provenance-tracked assertion about the organization (conception §5.1)."""

    field_name: str
    value: Any
    origin: Origin

    # Extraction provenance
    source_document: str | None = None
    source_quote: str | None = None  # MANDATORY and non-empty when origin == extraction (§5.3)
    page: int | None = None

    # Assessment provenance
    assessment_basis: list[str] | None = None  # mandatory when origin == assessment (§5.1)

    confidence: Confidence
    status: FactStatus
    validated_by: str | None = None
    validated_at: str | None = None
    # Non-empty reason attached to a Skip or Reject (universal justification rule, §8).
    justification: str | None = None
    # The follow-up question this Fact answers, when it came from one. An expert
    # question's field_name is an opaque hash, so without the text nothing — neither
    # the auditor nor the reviewing agent after a resume — can tell what was asked.
    question: str | None = None

    @model_validator(mode="after")
    def _enforce_provenance(self) -> "Fact":
        if self.origin is Origin.EXTRACTION:
            if self.source_quote is None or not self.source_quote.strip():
                raise ValueError(
                    "A Fact of origin 'extraction' must carry a non-empty source_quote "
                    "(conception §5.3)."
                )
        if self.origin is Origin.ASSESSMENT:
            if not self.assessment_basis:
                raise ValueError(
                    "A Fact of origin 'assessment' must carry a non-empty assessment_basis "
                    "(conception §5.1)."
                )
        return self

    # --- Constructors, one per origin, so callers cannot forget the provenance rules ---

    @classmethod
    def declaration(
        cls,
        field_name: str,
        value: Any,
        *,
        confidence: Confidence = Confidence.HIGH,
        validated_by: str | None = None,
        validated_at: str | None = None,
        question: str | None = None,
    ) -> "Fact":
        """A value entered directly by the auditor in the intake form (§4, §11.1) — highest confidence."""
        return cls(
            field_name=field_name,
            value=value,
            origin=Origin.DECLARATION,
            confidence=confidence,
            status=FactStatus.DECLARED,
            validated_by=validated_by,
            validated_at=validated_at,
            question=question,
        )

    @classmethod
    def extraction(
        cls,
        field_name: str,
        value: Any,
        *,
        source_document: str,
        source_quote: str,
        page: int | None = None,
        confidence: Confidence = Confidence.HIGH,
    ) -> "Fact":
        """A value the AI found in a supplied document (§4) — source_quote is mandatory (§5.3)."""
        return cls(
            field_name=field_name,
            value=value,
            origin=Origin.EXTRACTION,
            source_document=source_document,
            source_quote=source_quote,
            page=page,
            confidence=confidence,
            status=FactStatus.EXTRACTED,
        )

    @classmethod
    def assessment(
        cls,
        field_name: str,
        value: Any,
        *,
        assessment_basis: list[str],
        confidence: Confidence = Confidence.LOW,
    ) -> "Fact":
        """A value the AI reasoned/inferred from other Facts (§4) — assessment_basis mandatory (§5.1)."""
        return cls(
            field_name=field_name,
            value=value,
            origin=Origin.ASSESSMENT,
            assessment_basis=assessment_basis,
            confidence=confidence,
            status=FactStatus.ASSESSED,
        )


def validate_extraction(fact: Fact) -> bool:
    """Reject any extraction Fact without a non-empty citation (conception §5.3).

    The Fact model already refuses to construct such a Fact, so this mirrors the
    conception's explicit guard for callers that build Facts by other means
    (e.g. raw LLM output not yet passed through the model).
    """
    if fact.origin is Origin.EXTRACTION:
        return bool(fact.source_quote and fact.source_quote.strip())
    return True
