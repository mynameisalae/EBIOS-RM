"""Le banc d'essai de fidélité : ce que le contrôle attrape, mesuré sur des phrases dont on connaît la vérité."""

from __future__ import annotations

from ebios_rm.reporting import fidelity

STATE = {
    "w5": {
        "risques": [
            {"id": "R1", "niveau_risque": "Critique", "niveau_risque_residuel": "Moyen", "gravite": "Grave"},
            {"id": "R2", "niveau_risque": "Élevé", "niveau_risque_residuel": "Moyen", "gravite": "Grave"},
        ],
        "mesures": [{"id": "M-01", "priorite": "P1"}, {"id": "M-02", "priorite": "P2"}],
    },
    "w4": {"scenarios": [{"id": "SO-01", "scenario_strategique_id": "SS-01", "retenu": True}]},
}


def _by_category() -> dict[str, fidelity.Row]:
    return {row.category: row for row in fidelity.run(STATE)}


def test_every_exact_sentence_is_accepted_and_every_corruption_with_a_catchable_flaw_is_refused():
    rows = _by_category()
    assert rows["fidèle"].rate == 1.0 and rows["fidèle"].total == 5          # 2 risks + 2 measures + 1 mode
    for category in ("identifiant inventé", "identifiant d'un autre objet", "source inventée", "source absente",
                     "source trop vague", "niveau inventé", "niveau échangé (champ cité)"):
        assert rows[category].rate == 1.0, category


def test_the_limit_of_the_check_is_measured_not_hidden():
    row = _by_category()["niveau échangé (objet cité)"]
    assert row.known_limit is True and row.rate == 0.0 and row.total == 2


def test_the_table_states_the_overall_rate_outside_the_known_limit():
    table = fidelity.to_markdown(fidelity.run(STATE))
    assert "(limite connue)" in table and "Hors limite connue" in table and "(100%)" in table


def test_a_mission_with_no_data_yields_no_rows():
    assert fidelity.run({}) == []
