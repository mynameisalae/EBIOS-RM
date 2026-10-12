"""save_workshop_output / load_workshop_output — the generic pair used for
ateliers 2 to 5, so we don't duplicate save_w1_output/load_w1_output four times
(conception §10.2, §12.6)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from ebios_rm.orchestrator import mission_state
from ebios_rm.repositories.mission_repository import MissionRepository, connect


@pytest.fixture
def repo():
    conn = connect(":memory:")
    yield MissionRepository(conn)
    conn.close()


class _FakeAtelierOutput(BaseModel):
    couples_sr_ov: list[str] = []


def test_generic_save_and_load_roundtrip(repo):
    mid = repo.create_mission("M", ["RGPD"])
    output = _FakeAtelierOutput(couples_sr_ov=["SR1-OV1", "SR2-OV1"])

    version = mission_state.save_workshop_output(repo, mid, mission_state.WORKSHOP_2, output)
    assert version == 1

    loaded = mission_state.load_workshop_output(repo, mid, mission_state.WORKSHOP_2, _FakeAtelierOutput)
    assert loaded == output


def test_generic_load_returns_none_when_absent(repo):
    mid = repo.create_mission("M", ["RGPD"])
    assert mission_state.load_workshop_output(repo, mid, mission_state.WORKSHOP_3, _FakeAtelierOutput) is None


def test_generic_save_creates_new_version_each_call(repo):
    mid = repo.create_mission("M", ["RGPD"])
    mission_state.save_workshop_output(repo, mid, mission_state.WORKSHOP_2, _FakeAtelierOutput(couples_sr_ov=["a"]))
    v2 = mission_state.save_workshop_output(repo, mid, mission_state.WORKSHOP_2, _FakeAtelierOutput(couples_sr_ov=["b"]))
    assert v2 == 2
    loaded = mission_state.load_workshop_output(repo, mid, mission_state.WORKSHOP_2, _FakeAtelierOutput)
    assert loaded.couples_sr_ov == ["b"]


def test_workshops_are_isolated_from_each_other(repo):
    mid = repo.create_mission("M", ["RGPD"])
    mission_state.save_workshop_output(repo, mid, mission_state.WORKSHOP_2, _FakeAtelierOutput(couples_sr_ov=["w2"]))
    mission_state.save_workshop_output(repo, mid, mission_state.WORKSHOP_3, _FakeAtelierOutput(couples_sr_ov=["w3"]))

    w2 = mission_state.load_workshop_output(repo, mid, mission_state.WORKSHOP_2, _FakeAtelierOutput)
    w3 = mission_state.load_workshop_output(repo, mid, mission_state.WORKSHOP_3, _FakeAtelierOutput)
    assert w2.couples_sr_ov == ["w2"]
    assert w3.couples_sr_ov == ["w3"]


def test_workshop_1_dedicated_functions_still_work(repo):
    """Untouched by this change — same names, same behavior as before."""
    from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output

    mid = repo.create_mission("M", ["RGPD"])
    output = Workshop1Output()
    mission_state.save_w1_output(repo, mid, output)
    loaded = mission_state.load_w1_output(repo, mid)
    assert loaded == output
