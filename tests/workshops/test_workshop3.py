"""Fiche de test — Atelier 3, scenario-count gate (conception §17)."""

import pytest


@pytest.mark.skip(reason="pending workshop 3 implementation")
def test_scenario_count_thresholds():
    # estimate_cost_and_time(9)  -> 6 < N <= 12 -> options == ['run_anyway', 'merge', 'choose_subset', 'cancel']
    # estimate_cost_and_time(14) -> N > 12      -> options == ['merge', 'choose_subset', 'cancel']
    # assert 'run_anyway' not in options_for_14
    pass
