"""Shared pytest fixtures — in-memory reference DB, an example intake form, and a
fake Workshop 1 agent runner so the orchestration is tested without any LLM."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from ebios_rm.db.loader import build_reference_db
from ebios_rm.mission_context.intake_form import OrgContextForm
from ebios_rm.repositories.reference_repository import BaselineControl, ReferenceRepository

DEV_SEED = Path(__file__).resolve().parents[1] / "data" / "dev_seed" / "baseline_controls.dev.json"


@pytest.fixture
def dev_controls() -> list[dict]:
    return json.loads(DEV_SEED.read_text(encoding="utf-8"))


@pytest.fixture
def reference_conn(dev_controls) -> sqlite3.Connection:
    conn = build_reference_db(":memory:", extra_controls=dev_controls)
    yield conn
    conn.close()


@pytest.fixture
def reference_repo(reference_conn) -> ReferenceRepository:
    return ReferenceRepository(reference_conn)


@pytest.fixture
def example_form() -> OrgContextForm:
    return OrgContextForm(
        organisation_nom="Clinique Test",
        secteur_activite="Santé",
        taille_effectif=100,
        perimetre_geographique=["France"],
        systeme_information_resume="SIH hébergé, accès distant VPN.",
        hebergement="hybride",
        teletravail_autorise=True,
        acces_distant_moyens=["VPN"],
        edr_av_deploye=None,           # empty -> Important follow-up
        sauvegarde_strategie=None,     # empty -> Important follow-up
        donnees_personnelles_traitees=True,
        categories_donnees_personnelles=["patients"],
        incidents_securite_passes=None,
        audits_anterieurs=None,
        fournisseurs_tiers_critiques=["Hébergeur HDS"],
        applicable_frameworks=["ANSSI_hygiene", "RGPD", "NIST"],
        processus_metier_critiques=["Prise en charge des patients"],
        documents_fournis=None,
    )
