"""The three intake validation cases and the no-auto-resolve rule (conception §11)."""

from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.validation import validate


def _decl(field, value):
    return Fact.declaration(field, value)


def _extr(field, value):
    return Fact.extraction(field, value, source_document="doc.pdf", source_quote=f"{field}: {value}")


def test_identical_information_is_verified_high_confidence():
    result = validate([_decl("acces_distant_moyens", ["VPN", "MFA"])],
                      [_extr("acces_distant_moyens", ["MFA", "VPN"])])  # order-insensitive
    assert len(result.verified) == 1
    assert not result.has_unresolved_contradictions


def test_document_only_information_is_proposed_for_confirmation():
    result = validate([], [_extr("edr_av_deploye", "CrowdStrike Falcon")])
    assert len(result.document_only) == 1
    assert result.document_only[0].field_name == "edr_av_deploye"


def test_declaration_only_information_is_kept():
    result = validate([_decl("organisation_nom", "Clinique Test")], [])
    assert len(result.declaration_only) == 1


def test_contradiction_is_flagged_and_never_auto_resolved():
    result = validate([_decl("teletravail_autorise", "Non")],
                      [_extr("teletravail_autorise", "Politique VPN télétravail active")])
    assert result.has_unresolved_contradictions
    c = result.contradictions[0]
    assert c.declaration.value == "Non"
    assert c.extraction.value == "Politique VPN télétravail active"
    # Nothing verified or silently chosen — the mission cannot advance without a human decision.
    assert result.verified == []
