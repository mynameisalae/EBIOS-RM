"""Fiche de test — Rapport de mission (conception §20.1, §20.2, §20.3).

The report is model-written, so what is tested here is everything around the model:
what it is allowed to read, the gate every statement must pass, and the document.
A scripted runner stands in for the model — no call, no cost.
"""

from __future__ import annotations

import pytest

from ebios_rm.repositories.mission_repository import MissionRepository, connect
from ebios_rm.reporting.mission_report import (
    SCALES,
    build_mission_report,
    build_snapshot,
    check_statement,
    write_mission_report,
)
from ebios_rm.reporting.report_agent import SectionDraft, Statement

FIXED_DATE = "2026-10-10T00:00:00+00:00"

STATE = {
    "organisation": {"nom": "Clinique Test"},
    "echelles": dict(SCALES),
    "w5": {
        "risques": [
            {"id": "R1", "niveau_risque": "Critique", "vraisemblance": "V3", "vraisemblance_residuelle": "V2",
             "mode_retenu_id": "SO-02"},
            {"id": "R2", "niveau_risque": "Élevé", "vraisemblance": "V3", "vraisemblance_residuelle": "V2",
             "mode_retenu_id": "SO-04"},
        ],
        "mesures": [{"id": "M-03", "libelle": "Second facteur", "mitigation_ids_attck": ["M1032"]}],
    },
}


def _s(text: str, *sources: str) -> Statement:
    return Statement(text=text, sources=list(sources))


# --- the gate ---------------------------------------------------------------------

def test_a_statement_resting_on_real_fields_stands():
    ok = _s("Le risque R1 est de niveau Critique.", "w5.risques.0.niveau_risque")
    assert check_statement(ok, STATE) is None


def test_an_identifier_is_vouched_for_by_the_object_that_holds_the_cited_field():
    # R1 and SO-02 sit in the same object as the cited field.
    ok = _s("R1 repose sur le mode SO-02.", "w5.risques.0.mode_retenu_id")
    assert check_statement(ok, STATE) is None


def test_a_list_can_be_cited_to_count_or_enumerate():
    assert check_statement(_s("Deux risques sont retenus : R1 et R2.", "w5.risques"), STATE) is None


def test_the_object_a_step_belongs_to_vouches_for_its_identifier():
    state = {"w4": {"scenarios": [{"id": "SO-02", "attack_path": [{"technique_id": "T1078", "description": "d"}]}]}}
    ok = _s("Le mode SO-02 commence par T1078.", "w4.scenarios.0.attack_path.0.technique_id")
    assert check_statement(ok, state) is None
    assert "SO-09" in check_statement(
        _s("Le mode SO-09 commence par T1078.", "w4.scenarios.0.attack_path.0.technique_id"), state)


def test_bracket_paths_are_understood():
    ok = _s("R1 est Critique.", "w5.risques[0].niveau_risque")
    assert check_statement(ok, STATE) is None


@pytest.mark.parametrize("statement, why", [
    (_s("", "w5.risques.0.id"), "texte vide"),
    (_s("R1 est Critique."), "aucune source"),
    (_s("R1 est Critique.", "w5.risques.7.niveau_risque"), "introuvable"),
    (_s("R1 est Critique.", "w5.risques.0.champ_inexistant"), "introuvable"),
    (_s("Tout va bien.", "w5"), "trop vague"),
    (_s("La mesure M-99 résout tout.", "w5.risques.0.niveau_risque"), "M-99"),
    (_s("R2 est Élevé.", "w5.risques.0.niveau_risque"), "R2"),
    (_s("La vraisemblance monte à V4.", "w5.risques.0.vraisemblance"), "V4"),
    (_s("La technique T1078 est utilisée.", "w5.risques.0.id"), "T1078"),
])
def test_the_gate_refuses_what_the_citations_do_not_hold_up(statement, why):
    reason = check_statement(statement, STATE)
    assert reason is not None and why in reason


# --- what the report may read -------------------------------------------------------

@pytest.fixture
def repo() -> MissionRepository:
    return MissionRepository(connect(":memory:"))


def _approve(repo, mid, atelier, output):
    version = repo.save_output(mid, atelier, output)
    repo.set_version_status(mid, atelier, version, "approved")
    return version


def test_only_approved_current_versions_are_read(repo):
    mid = repo.create_mission("Clinique Test", [])
    _approve(repo, mid, 5, {"risques": [{"id": "R1"}]})
    repo.save_output(mid, 2, {"couples": []})                      # never approved
    _approve(repo, mid, 3, {"scenarios": [{"id": "SS-01"}]})
    repo.save_output(mid, 3, {"scenarios": [{"id": "SS-09"}]})     # a newer, unapproved version

    snapshot = build_snapshot(repo, mid)

    assert snapshot.approved == (5,)
    assert "w5" in snapshot.state and "w2" not in snapshot.state and "w3" not in snapshot.state
    assert "non approuvée" in snapshot.not_approved[2]
    assert "version 2 non approuvée" in snapshot.not_approved[3]   # the approved v1 is not enough
    assert snapshot.not_approved[1] == "aucune version enregistrée"


def test_the_organisation_comes_from_the_mission_context(repo):
    mid = repo.create_mission("Clinique Test", [])
    repo.save_output(mid, 0, {"organisation_nom": "Clinique du Parc", "secteur_activite": "Santé",
                              "applicable_frameworks": ["RGPD"], "facts": [{"field_name": "secret"}]})

    organisation = build_snapshot(repo, mid).state["organisation"]

    assert organisation == {"nom": "Clinique du Parc", "secteur_activite": "Santé", "referentiels": ["RGPD"]}


def test_atelier_4_contributes_confirmed_scenarios_without_working_notes(repo):
    mid = repo.create_mission("Clinique Test", [])
    _approve(repo, mid, 4, {"scenarios": [
        {"id": "SO-01", "statut": "confirme", "resume": "r", "likelihood_revision_reason": "note interne",
         "baseline_gaps_considered": [{"gap_id": "BG-1"}],
         "attack_path": [{"phase": "Rentrer", "tactic": "initial-access", "technique_id": "T1078",
                          "technique_name": "Valid Accounts", "description": "d", "justification": "interne",
                          "vraisemblance_action": "V3"}]},
        {"id": "SO-02", "statut": "a_reviser", "resume": "pas prêt"},
    ]})

    w4 = build_snapshot(repo, mid).state["w4"]

    assert [s["id"] for s in w4["scenarios"]] == ["SO-01"]
    scenario = w4["scenarios"][0]
    assert "likelihood_revision_reason" not in scenario and "baseline_gaps_considered" not in scenario
    assert "justification" not in scenario["attack_path"][0]
    assert scenario["attack_path"][0]["technique_id"] == "T1078"


def test_atelier_1_keeps_the_weakness_but_not_the_control_provenance(repo):
    mid = repo.create_mission("Clinique Test", [])
    _approve(repo, mid, 1, {
        "biens_essentiels": [{"id": "BE-1", "nom": "Dossier patient", "origin": "assessment",
                              "derived_from_fact_fields": ["x"]}],
        "baseline_gaps_full": [{"gap_id": "BG-1", "weakness": "Pas de MFA", "risk_categories": ["credential_access"],
                                "controls": [{"framework": "ISO27001", "control_id": "A.5.17"}]}],
        "unverified_controls": [{"control_id": "A.8.2"}],
    })

    w1 = build_snapshot(repo, mid).state["w1"]

    assert w1["baseline_gaps_full"] == [{"gap_id": "BG-1", "weakness": "Pas de MFA"}]
    assert "unverified_controls" not in w1
    assert w1["biens_essentiels"] == [{"id": "BE-1", "nom": "Dossier patient"}]


def test_noise_is_not_handed_to_the_model(repo):
    mid = repo.create_mission("Clinique Test", [])
    _approve(repo, mid, 5, {"risques": [], "quality_report": {"checks": []}, "elements_ecartes": [],
                            "human_edits": [], "alertes_atelier4": [], "attck_version": "x", "activites_faites": []})

    assert set(build_snapshot(repo, mid).state["w5"]) == {"risques"}


# --- writing the report ---------------------------------------------------------------

class ScriptedRunner:
    """Answers each section from a script. Without a script for the correction round it gives every refusal up."""

    def __init__(self, drafts: dict[str, list[Statement]], revisions: dict[str, list[Statement]] | None = None) -> None:
        self.drafts = drafts
        self.revisions = revisions or {}
        self.received: dict[str, dict] = {}
        self.refusals_seen: dict[str, list] = {}

    def write_section(self, spec, state):
        self.received[spec.key] = state
        return SectionDraft(statements=self.drafts.get(spec.key, []))

    def revise_section(self, spec, state, refused):
        self.refusals_seen[spec.key] = refused
        return SectionDraft(statements=self.revisions.get(spec.key, []))


@pytest.fixture
def mission(repo):
    mid = repo.create_mission("Clinique Test", [])
    repo.save_output(mid, 0, {"organisation_nom": "Clinique du Parc", "secteur_activite": "Santé",
                              "applicable_frameworks": []})
    _approve(repo, mid, 1, {"biens_essentiels": [{"id": "BE-1", "nom": "Dossier patient"}]})
    _approve(repo, mid, 5, {"risques": [{"id": "R1", "niveau_risque": "Critique", "vraisemblance_residuelle": "V2"}]})
    return mid


def test_each_section_receives_only_its_own_ateliers_plus_context(repo, mission):
    runner = ScriptedRunner({})

    write_mission_report(build_snapshot(repo, mission), runner, generated_at=FIXED_DATE)

    assert set(runner.received) == {"synthese", "perimetre", "traitement"}   # 2, 3, 4 not approved: not asked
    assert set(runner.received["perimetre"]) == {"organisation", "echelles", "w1"}
    assert set(runner.received["traitement"]) == {"organisation", "echelles", "w5"}


def test_refused_statements_the_model_gives_up_are_recorded_with_their_reason(repo, mission):
    runner = ScriptedRunner({"traitement": [
        _s("R1 est de niveau Critique.", "w5.risques.0.niveau_risque"),
        _s("La mesure M-42 règle tout.", "w5.risques.0.niveau_risque"),
        _s("Aucune source."),
    ]})

    report = write_mission_report(build_snapshot(repo, mission), runner, generated_at=FIXED_DATE)

    section = next(s for s in report.sections if s.key == "traitement")
    assert [st.text for st in section.statements] == ["R1 est de niveau Critique."]
    assert [(r.text, r.reason) for r in report.rejected] == [
        ("La mesure M-42 règle tout.", "abandonnée après refus — « M-42 » ne figure pas dans les champs cités"),
        ("Aucune source.", "abandonnée après refus — aucune source citée"),
    ]
    assert [r.reason.split(" ")[0] for r in runner.refusals_seen["traitement"]] == ["«", "aucune"]  # model was told why


def test_a_refused_statement_rewritten_with_proper_citations_is_kept(repo, mission):
    runner = ScriptedRunner(
        {"traitement": [_s("R1 vaut V2 après traitement.", "cadre.mal.cite")]},
        revisions={"traitement": [_s("R1 vaut V2 après traitement.", "w5.risques.0.vraisemblance_residuelle")]},
    )

    report = write_mission_report(build_snapshot(repo, mission), runner, generated_at=FIXED_DATE)

    section = next(s for s in report.sections if s.key == "traitement")
    assert [st.sources for st in section.statements] == [["w5.risques.0.vraisemblance_residuelle"]]
    assert report.rejected == () and report.corrected == 1


def test_a_rewrite_that_still_fails_is_refused_for_good(repo, mission):
    runner = ScriptedRunner(
        {"traitement": [_s("R1 vaut V2.", "cadre.mal.cite")]},
        revisions={"traitement": [_s("R1 vaut V2.", "toujours.faux")]},
    )

    report = write_mission_report(build_snapshot(repo, mission), runner, generated_at=FIXED_DATE)

    assert [(r.sources, r.reason) for r in report.rejected] == [(("toujours.faux",), "source introuvable : toujours.faux")]
    assert report.corrected == 0


def test_no_correction_round_is_paid_for_when_nothing_was_refused(repo, mission):
    runner = ScriptedRunner({"traitement": [_s("R1 est Critique.", "w5.risques.0.niveau_risque")]})

    write_mission_report(build_snapshot(repo, mission), runner, generated_at=FIXED_DATE)

    assert runner.refusals_seen == {}


def test_a_section_where_nothing_survives_is_reported_as_skipped(repo, mission):
    runner = ScriptedRunner({"perimetre": [_s("Rien de valide.", "w1.inexistant.0.id")]})

    report = write_mission_report(build_snapshot(repo, mission), runner, generated_at=FIXED_DATE)

    assert "perimetre" not in {s.key for s in report.sections}
    assert ("Périmètre et enjeux", "aucune affirmation vérifiée") in [(s.title, s.reason) for s in report.skipped]


def test_unapproved_ateliers_are_skipped_with_their_reason(repo, mission):
    report = write_mission_report(build_snapshot(repo, mission), ScriptedRunner({}), generated_at=FIXED_DATE)

    reasons = {s.title: s.reason for s in report.skipped}
    assert reasons["Sources de risque"] == "atelier 2 : aucune version enregistrée"


# --- the document ----------------------------------------------------------------------

def _report(repo, mission):
    runner = ScriptedRunner({
        "synthese": [_s("Un risque est retenu : R1.", "w5.risques.0.id")],
        "perimetre": [_s("Le bien essentiel BE-1 est le dossier patient.", "w1.biens_essentiels.0.nom")],
        "traitement": [_s("R1 vaut V2 après traitement (échelle V1 à V4).",
                          "w5.risques.0.vraisemblance_residuelle", "echelles.vraisemblance")],
    })
    return write_mission_report(build_snapshot(repo, mission), runner, generated_at=FIXED_DATE)


def test_the_document_numbers_each_statement_and_lists_its_sources_at_the_end(repo, mission):
    doc = build_mission_report(_report(repo, mission))

    lines = [p.text for p in doc.paragraphs]
    assert "1. Synthèse" in lines and "2. Périmètre et enjeux" in lines and "3. Traitement du risque" in lines
    assert "Un risque est retenu : R1. [1]" in lines                      # the reference sits right after the sentence
    assert "Le bien essentiel BE-1 est le dossier patient. [2]" in lines
    assert any(line.endswith(". Références des sources") for line in lines)   # numbered after the method's deliverables
    assert "[1]  w5.risques.0.id" in lines                                # … and is resolved in the reference list
    assert "[3]  w5.risques.0.vraisemblance_residuelle, echelles.vraisemblance" in lines
    assert not any(line.startswith("Sources :") for line in lines)        # no clutter under each sentence


def test_reference_numbers_are_small_gold_superscripts(repo, mission):
    doc = build_mission_report(_report(repo, mission))

    paragraph = next(p for p in doc.paragraphs if p.text == "Un risque est retenu : R1. [1]")
    marker = paragraph.runs[-1]
    assert marker.text == " [1]" and marker.font.superscript is True


def test_the_cover_names_the_organisation_and_nobody_else(repo, mission):
    lines = [p.text for p in build_mission_report(_report(repo, mission)).paragraphs]

    assert "RAPPORT DE MISSION  ·  ANALYSE DE RISQUE EBIOS RM" in lines
    assert "Clinique du Parc" in lines
    assert "Projet OGSBC  ·  Rapport de mission  ·  Octobre 2026" in lines
    assert not any(name in "\n".join(lines) for name in ("ENCADRANT", "Jamal", "AGOUJIM"))


def test_the_levels_are_given_with_their_scales(repo, mission):
    doc = build_mission_report(_report(repo, mission))

    scales = next(t for t in doc.tables if t.rows[0].cells[0].text == "Échelle")
    assert [(r.cells[0].text, r.cells[1].text) for r in scales.rows[1:]] == [
        ("Gravité", SCALES["gravite"]), ("Vraisemblance", SCALES["vraisemblance"]),
        ("Niveau de risque", SCALES["niveau_risque"]),
    ]


def test_sections_left_out_are_announced_not_hidden(repo, mission):
    doc = build_mission_report(_report(repo, mission))

    notes = [p.text for p in doc.paragraphs if p.text.startswith("Sections non incluses")]
    assert len(notes) == 1
    assert "Sources de risque (atelier 2 : aucune version enregistrée)" in notes[0]


def test_a_refused_statement_never_reaches_the_document(repo, mission):
    runner = ScriptedRunner({"traitement": [
        _s("R1 est Critique.", "w5.risques.0.niveau_risque"),
        _s("La mesure M-42 règle tout.", "w5.risques.0.niveau_risque"),
    ]})
    report = write_mission_report(build_snapshot(repo, mission), runner, generated_at=FIXED_DATE)

    text = "\n".join(p.text for p in build_mission_report(report).paragraphs)

    assert "M-42" not in text
    assert len(report.rejected) == 1


def test_unknown_mission_is_refused(repo):
    with pytest.raises(ValueError):
        build_snapshot(repo, "n-existe-pas")


# --- levels claimed in a sentence --------------------------------------------------------

LEVEL_STATE = {"w5": {"risques": [{"id": "R1", "niveau_risque": "Critique", "niveau_risque_residuel": "Moyen", "gravite": "Grave"}]}}


@pytest.mark.parametrize("text", [
    "Le risque R1 est au niveau critique avant traitement.",
    "Le niveau de risque de R1 est critique, puis moyen après traitement.",
    "La gravité de R1 est grave.",
])
def test_a_level_present_in_the_cited_object_passes(text):
    assert check_statement(_s(text, "w5.risques.0"), LEVEL_STATE) is None


@pytest.mark.parametrize("text, level", [
    ("Le risque R1 est au niveau faible.", "faible"),
    ("Le niveau de risque de R1 est élevé.", "élevé"),
    ("La gravité de R1 est minimale.", "minimale"),
])
def test_a_level_the_cited_data_never_states_is_refused(text, level):
    reason = check_statement(_s(text, "w5.risques.0"), LEVEL_STATE)
    assert reason == f"niveau « {level} » absent des champs cités"


def test_ordinary_words_that_are_not_level_claims_are_left_alone():
    # « moyen » here is a means, not a level: no « niveau » or « gravité » announces it.
    assert check_statement(_s("R1 passe par un moyen discret.", "w5.risques.0"), LEVEL_STATE) is None


def test_when_the_level_field_itself_is_cited_the_sentence_must_say_what_it_says():
    # niveau_risque is Critique, niveau_risque_residuel is Moyen: swapping them is caught when the exact field is cited…
    swapped = _s("Le risque R1 est au niveau moyen avant traitement.", "w5.risques.0.niveau_risque")
    assert check_statement(swapped, LEVEL_STATE) == "niveau « moyen » différent du champ cité"
    both = _s("Le risque R1 passe du niveau critique au niveau moyen.",
              "w5.risques.0.niveau_risque", "w5.risques.0.niveau_risque_residuel")
    assert check_statement(both, LEVEL_STATE) is None
    # …and stays a known limit when only the whole object is cited (both levels are in it).
    assert check_statement(_s("Le risque R1 est au niveau moyen avant traitement.", "w5.risques.0"), LEVEL_STATE) is None
