"""Les livrables propres à la méthode EBIOS RM : cartographie, chemins d'attaque, plan d'amélioration (PACS)."""

from __future__ import annotations

import pytest

from ebios_rm.reporting import livrables
from ebios_rm.reporting.mission_report import MissionReport, ReportSection, build_mission_report
from ebios_rm.reporting.report_agent import Statement

RISKS = [
    {"id": "R1", "gravite": "Grave", "vraisemblance": "V3", "niveau_risque": "Critique",
     "vraisemblance_residuelle": "V1", "niveau_risque_residuel": "Moyen", "option_traitement": "reduction",
     "acceptabilite_residuelle": "Tolérable sous contrôle"},
    {"id": "R2", "gravite": "Critique", "vraisemblance": "V2", "niveau_risque": "Élevé",
     "vraisemblance_residuelle": "V1", "niveau_risque_residuel": "Moyen", "option_traitement": "reduction",
     "acceptabilite_residuelle": "Tolérable sous contrôle"},
]
MEASURES = [
    {"id": "M-02", "axe": "protection", "libelle": "Chiffrer les données", "priorite": "P2", "echeance": "6 mois",
     "responsable": "DSI", "risques_ids": ["R1"]},
    {"id": "M-01", "axe": "gouvernance", "libelle": "Désigner un RSSI", "priorite": "P1", "echeance": "6 mois",
     "responsable": "Direction", "risques_ids": ["R1", "R2"]},
    {"id": "M-09", "axe": "gouvernance", "libelle": "  désigner un RSSI ", "priorite": "P1", "echeance": "6 mois",
     "responsable": "Direction", "risques_ids": ["R3"]},
]
W4 = {"scenarios": [
    {"id": "SO-01", "scenario_strategique_id": "SS-01", "retenu": False, "attack_path": []},
    {"id": "SO-02", "scenario_strategique_id": "SS-01", "retenu": True, "revised_risk_level": "Élevé", "resume": "Via le VPN.",
     "attack_path": [{"phase": "Rentrer", "technique_id": "T1078", "technique_name": "Valid Accounts", "description": "Compte volé"},
                     {"phase": "Exploiter", "technique_id": "", "technique_name": "", "description": "Sortie des données"}]},
]}


def test_the_risk_map_is_a_real_png_for_the_risks_given():
    png = livrables.risk_map_png(RISKS)
    assert png is not None and png[:8] == b"\x89PNG\r\n\x1a\n"


def test_no_risks_means_no_map():
    assert livrables.risk_map_png([]) is None


def test_a_risk_with_an_unknown_scale_value_does_not_break_the_map():
    odd = [{"id": "R9", "gravite": "Inconnue", "vraisemblance": "V9", "niveau_risque": "???"}]
    assert livrables.risk_map_png(odd) is not None


def test_the_risk_table_shows_before_and_after():
    row = livrables.risk_rows(RISKS)[0]
    assert row[0] == "R1" and row[2] == "Critique (V3)" and row[3] == "Moyen (V1)" and row[4] == "Reduction"


def test_the_plan_lists_each_measure_once_by_axis_then_priority():
    rows = livrables.pacs_rows(MEASURES)
    assert [r[0] for r in rows] == ["M-01 / M-09", "M-02"]       # same wording = one measure, governance first
    assert rows[0][6] == "R1, R2, R3"                              # the risks of both ids are merged
    assert rows[0][2] == "Gouvernance" and rows[1][2] == "Protection"


def test_only_the_retained_mode_of_each_strategic_scenario_is_shown_with_its_steps():
    blocks = livrables.attack_path_blocks(W4)
    assert len(blocks) == 1 and blocks[0]["title"].startswith("SS-01 — mode retenu SO-02")
    assert blocks[0]["steps"][0][2] == "T1078 Valid Accounts"
    assert blocks[0]["steps"][1][2] == "—"                         # a step without a technique stays honest


def _report(evidence: dict) -> MissionReport:
    return MissionReport("m", "Org", "2026-10-18T10:00:00+00:00",
                         (ReportSection("synthese", "Synthèse", (Statement(text="Deux risques.", sources=["w5.risques"]),)),),
                         (), (), 0, evidence=evidence)


def _text(document) -> str:
    cells = [c.text for t in document.tables for row in t.rows for c in row.cells]
    return "\n".join([p.text for p in document.paragraphs] + cells)


def test_the_report_carries_the_methods_deliverables_when_the_ateliers_are_approved():
    document = build_mission_report(_report({"w4": W4, "w5": {"risques": RISKS, "mesures": MEASURES, "cadre_suivi": {
        "comite": "Comité SMSI", "indicateurs": [{"id": "IND-01", "libelle": "Taux", "cible": "100 %", "frequence": "mensuelle"}]}}}))
    text = _text(document)
    for title in ("2. Cartographie des risques", "3. Chemins d'attaque retenus",
                  "4. Plan d'amélioration continue de la sécurité (PACS)", "5. Références des sources"):
        assert title in text
    assert "IND-01" in text and "Comité SMSI" in text and "Désigner un RSSI" in text
    assert len(document.inline_shapes) == 1                         # the risk map


def test_a_report_without_atelier_5_has_no_map_and_no_plan():
    text = _text(build_mission_report(_report({"w4": W4})))
    assert "Cartographie" not in text and "PACS" not in text
    assert "Chemins d'attaque retenus" in text and "3. Références des sources" in text   # numbering follows


def test_a_report_without_evidence_is_unchanged():
    text = _text(build_mission_report(_report({})))
    assert "Cartographie" not in text and "Chemins" not in text and "2. Références des sources" in text
