"""New framework plugins must be discoverable with zero code change (conception §12.5)."""

import pytest


@pytest.mark.skip(reason="pending plugins.registry implementation")
def test_default_four_frameworks_are_discovered():
    # discovered = list_available_frameworks()
    # assert {"ISO27001", "ANSSI_hygiene", "RGPD", "NIST"} <= {f.id for f in discovered}
    pass
