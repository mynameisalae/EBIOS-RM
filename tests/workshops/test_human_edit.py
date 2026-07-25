"""Auditor edits on a workshop output, with mandatory justification (phase C, §2, §8)."""

import pytest

from ebios_rm.workshops.workshop1_cadrage.human_edit import EditError, apply_edit, get_value


def _output() -> dict:
    return {
        "evenements_redoutes": [
            {"id": "ER-1", "description": "Fuite de données", "gravite": "Grave"},
            {"id": "ER-2", "description": "Indisponibilité", "gravite": "Significative"},
        ],
        "baseline_gaps_full": [{"gap_id": "BG-1", "weakness": "Pas de MFA"}],
        "unverified_controls": ["RGPD-Art33"],
    }


def test_edit_changes_the_value_and_records_the_trail():
    edited = apply_edit(_output(), "evenements_redoutes.0.gravite", "Critique",
                        justification="impact patients sous-évalué")

    assert get_value(edited, "evenements_redoutes.0.gravite") == "Critique"
    trail = edited["human_edits"]
    assert len(trail) == 1
    entry = trail[0]
    assert entry["path"] == "evenements_redoutes.0.gravite"
    assert entry["old_value"] == "Grave" and entry["new_value"] == "Critique"
    assert entry["justification"] == "impact patients sous-évalué"
    assert entry["edited_by"] == "auditor" and entry["edited_at"]


def test_edit_does_not_mutate_the_original():
    original = _output()
    apply_edit(original, "evenements_redoutes.0.gravite", "Critique", justification="x")
    assert original["evenements_redoutes"][0]["gravite"] == "Grave"
    assert "human_edits" not in original


def test_justification_is_mandatory():
    for empty in ("", "   "):
        with pytest.raises(EditError):
            apply_edit(_output(), "evenements_redoutes.0.gravite", "Critique", justification=empty)


def test_unknown_path_is_rejected():
    with pytest.raises(EditError):
        apply_edit(_output(), "evenements_redoutes.0.inexistant", "x", justification="raison")
    with pytest.raises(EditError):
        apply_edit(_output(), "champ_inconnu", "x", justification="raison")


def test_out_of_range_index_is_rejected():
    with pytest.raises(EditError):
        apply_edit(_output(), "evenements_redoutes.9.gravite", "Critique", justification="raison")


def test_successive_edits_accumulate_in_order():
    data = apply_edit(_output(), "evenements_redoutes.0.gravite", "Critique", justification="premier")
    data = apply_edit(data, "baseline_gaps_full.0.weakness", "Pas de MFA sur le VPN",
                      justification="formulation imprécise")

    assert [e["path"] for e in data["human_edits"]] == [
        "evenements_redoutes.0.gravite", "baseline_gaps_full.0.weakness"]
    assert get_value(data, "baseline_gaps_full.0.weakness") == "Pas de MFA sur le VPN"


def test_edited_output_still_validates_as_workshop_output():
    from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output

    base = Workshop1Output().model_dump(mode="json")
    base["unverified_controls"] = ["RGPD-Art33"]
    edited = apply_edit(base, "unverified_controls.0", "RGPD-Art32", justification="mauvais article")

    restored = Workshop1Output.model_validate(edited)
    assert restored.unverified_controls == ["RGPD-Art32"]
    assert restored.human_edits[0]["justification"] == "mauvais article"
