"""Shared pytest fixtures — in-memory reference DB, an example intake form, and a
fake Workshop 1 agent runner so the orchestration is tested without any LLM."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from ebios_rm.db.loader import build_reference_db
from ebios_rm.repositories.reference_repository import BaselineControl, ReferenceRepository

DEV_SEED = Path(__file__).resolve().parents[1] / "data" / "dev_seed" / "baseline_controls.dev.json"


@pytest.fixture
def dev_controls() -> list[dict]:
    return json.loads(DEV_SEED.read_text(encoding="utf-8"))


@pytest.fixture
def reference_conn(dev_controls) -> sqlite3.Connection:
    # Tests run on the fixed sample set only, never the real plugin controls,
    # so they stay deterministic as referential text is added.
    conn = build_reference_db(":memory:", extra_controls=dev_controls, include_plugins=False)
    yield conn
    conn.close()


@pytest.fixture
def reference_repo(reference_conn) -> ReferenceRepository:
    return ReferenceRepository(reference_conn)
