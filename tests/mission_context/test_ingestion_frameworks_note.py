"""The model chooses referentials from the list this installation can load (§12.5)."""

from ebios_rm.mission_context.ingestion_agent import _frameworks_note
from ebios_rm.mission_context.questionnaire import all_questions

_QUESTIONS = list(all_questions())
_FRAMEWORKS_Q = [q for q in _QUESTIONS if q.id == "applicable_frameworks"]


def test_the_note_lists_every_loadable_plugin():
    from ebios_rm.plugins.registry import discover_frameworks

    note = _frameworks_note(_FRAMEWORKS_Q)
    for plugin in discover_frameworks():
        assert plugin.id in note        # read from the plugin folder, never hardcoded
        assert plugin.name in note


def test_only_the_batch_carrying_the_question_pays_for_it():
    others = [q for q in _QUESTIONS if q.id != "applicable_frameworks"]
    assert _frameworks_note(others[:12]) == ""


def test_unlisted_referentials_are_kept_verbatim_not_invented():
    # HDS has no plugin. It must reach the controls gate as itself, not be bent onto
    # a loadable id, and the model must not add ids the client never named.
    note = _frameworks_note(_FRAMEWORKS_Q)
    assert "tels quels" in note
    assert "N'ajoute jamais un id que le client n'a pas désigné" in note
