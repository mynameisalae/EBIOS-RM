"""Reference repository queries against the dev seed (conception §12.1, §12.3, §15.1)."""


def test_get_baseline_controls_by_framework(reference_repo):
    rgpd = reference_repo.get_baseline_controls("RGPD")
    ids = {c.control_id for c in rgpd}
    assert {"RGPD-Art32", "RGPD-Art33", "RGPD-Art83"} <= ids


def test_security_vs_legal_split(reference_repo):
    by_id = {c.control_id: c for c in reference_repo.get_baseline_controls("RGPD")}
    # Security control feeds workshop 4 (non-empty covers_risk_category, no legal_impact_type).
    assert by_id["RGPD-Art32"].covers_risk_category != []
    assert by_id["RGPD-Art32"].legal_impact_type is None
    # Legal-only provisions: empty covers_risk_category, legal_impact_type set (§12.3).
    assert by_id["RGPD-Art83"].covers_risk_category == []
    assert by_id["RGPD-Art83"].is_legal_provision


def test_legal_impact_provisions_across_declared_frameworks(reference_repo):
    provisions = reference_repo.get_legal_impact_provisions(["ANSSI_hygiene", "RGPD", "NIST"])
    ids = {p.control_id for p in provisions}
    # Only the legal-typed RGPD rows come back; security controls are excluded.
    assert ids == {"RGPD-Art33", "RGPD-Art83"}


def test_legal_impact_provisions_empty_when_no_frameworks(reference_repo):
    assert reference_repo.get_legal_impact_provisions([]) == []
