"""New framework plugins must be discoverable with zero code change (conception §12.4, §12.5)."""

from ebios_rm.plugins.registry import default_suggested_frameworks, discover_frameworks


def test_default_four_frameworks_are_discovered():
    ids = {p.id for p in discover_frameworks()}
    assert {"ISO27001", "ANSSI_hygiene", "RGPD", "NIST"} <= ids


def test_template_folder_is_ignored():
    ids = {p.id for p in discover_frameworks()}
    assert "CHANGE_ME" not in ids  # _template scaffold is skipped


def test_rgpd_declares_legal_impact_provisions():
    by_id = {p.id: p for p in discover_frameworks()}
    assert by_id["RGPD"].has_legal_impact_provisions is True
    assert by_id["ISO27001"].has_legal_impact_provisions is False


def test_all_four_are_default_suggested():
    assert set(default_suggested_frameworks()) == {"ISO27001", "ANSSI_hygiene", "RGPD", "NIST"}
