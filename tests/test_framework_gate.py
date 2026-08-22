"""An unmatched declaration can be identified as a referential already loaded (§2, §12.5)."""

import importlib.util
from pathlib import Path

import pytest

from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.mission_context import assemble_from_facts
from ebios_rm.repositories.mission_repository import MissionRepository, connect

_CLI_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_workshop1_from_docs.py"


@pytest.fixture
def cli():
    spec = importlib.util.spec_from_file_location("cli_gate", _CLI_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo():
    conn = connect(":memory:")
    yield MissionRepository(conn)
    conn.close()


class _Ref:
    def __init__(self, loaded):
        self._loaded = loaded

    def loaded_frameworks(self):
        return list(self._loaded)

    def get_baseline_controls(self, framework):
        return [object()] if framework in self._loaded else []


def _context(frameworks):
    return assemble_from_facts([
        Fact.declaration("organisation_nom", "ACME"),
        Fact.declaration("secteur_activite", "Finance"),
        Fact.declaration("applicable_frameworks", frameworks),
    ])


def _io(answers):
    it = iter(answers)
    out = []
    return (lambda _p="": next(it)), (lambda t: out.append(t)), out


def test_a_name_written_differently_is_mapped_onto_its_plugin(cli, repo):
    mid = repo.create_mission("M", ["ISO 27001"])
    mc = _context(["ISO 27001", "RGPD"])
    ask, show, _ = _io(["1"])                       # "yes, that is ISO27001"

    updated = cli._map_onto_loaded(repo, mid, mc, _Ref(["ISO27001", "RGPD"]), ["ISO 27001"],
                                   io_in=ask, io_out=show)

    assert updated.applicable_frameworks == ["ISO27001", "RGPD"]
    assert any(d.action_taken == "frameworks_mapped" for d in repo.decisions(mid))


def test_declining_the_mapping_changes_nothing(cli, repo):
    # HDS has no plugin at all: it must stay declared and reach the withdraw/stop gate.
    mid = repo.create_mission("M", ["HDS"])
    mc = _context(["HDS", "RGPD"])
    ask, show, _ = _io([""])                        # no, none of these

    updated = cli._map_onto_loaded(repo, mid, mc, _Ref(["ISO27001", "RGPD"]), ["HDS"],
                                   io_in=ask, io_out=show)

    assert updated.applicable_frameworks == ["HDS", "RGPD"]
    assert not repo.decisions(mid)


def test_mapping_a_duplicate_does_not_declare_it_twice(cli, repo):
    mid = repo.create_mission("M", ["RGPD (règlement)", "RGPD"])
    mc = _context(["RGPD (règlement)", "RGPD"])
    ask, show, _ = _io(["1"])

    updated = cli._map_onto_loaded(repo, mid, mc, _Ref(["RGPD"]), ["RGPD (règlement)"],
                                   io_in=ask, io_out=show)

    assert updated.applicable_frameworks == ["RGPD"]
