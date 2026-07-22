"""Fact provenance discipline (conception §5.1, §5.3)."""

import pytest
from pydantic import ValidationError

from ebios_rm.domain.enums import Confidence, FactStatus, Origin
from ebios_rm.domain.fact import Fact, validate_extraction


def test_declaration_fact_is_high_confidence_and_declared():
    fact = Fact.declaration("organisation_nom", "Clinique Test")
    assert fact.origin is Origin.DECLARATION
    assert fact.status is FactStatus.DECLARED
    assert fact.confidence is Confidence.HIGH


def test_extraction_without_source_quote_is_rejected_at_construction():
    with pytest.raises(ValidationError):
        Fact(
            field_name="edr_av_deploye",
            value="CrowdStrike Falcon",
            origin=Origin.EXTRACTION,
            source_quote="   ",  # blank -> invalid (§5.3)
            confidence=Confidence.HIGH,
            status=FactStatus.EXTRACTED,
        )


def test_extraction_with_source_quote_is_accepted():
    fact = Fact.extraction(
        "edr_av_deploye", "CrowdStrike Falcon",
        source_document="politique.pdf", source_quote="EDR: CrowdStrike Falcon déployé sur tous les postes",
        page=4,
    )
    assert validate_extraction(fact) is True
    assert fact.status is FactStatus.EXTRACTED


def test_assessment_requires_basis():
    with pytest.raises(ValidationError):
        Fact(
            field_name="maturite",
            value="faible",
            origin=Origin.ASSESSMENT,
            assessment_basis=[],  # empty -> invalid (§5.1)
            confidence=Confidence.LOW,
            status=FactStatus.ASSESSED,
        )
    ok = Fact.assessment("maturite", "faible", assessment_basis=["absence de MFA", "pas de sauvegarde hors ligne"])
    assert ok.confidence is Confidence.LOW


def test_validate_extraction_guard_for_externally_built_facts():
    # A declaration Fact is always valid under the extraction guard.
    assert validate_extraction(Fact.declaration("x", "y")) is True
