"""Fiche de test — Atelier 5, traitement du risque (conception §19).

Everything runs against hand-built MitigationCatalogue objects; no test opens
the real ATT&CK database (that lives in test_attack_repository.py) and no
test makes a real LLM call. The assertions sit on the deterministic parts:
the ATT&CK-mitigation check, the priority vocabulary, the RGPD-scope filter,
and the quality checker.
"""

from __future__ import annotations

from ebios_rm.domain.enums import (
    CategorieImpact,
    Gravite,
    ImpactType,
    NiveauRisque,
    Origin,
    PrioriteMesure,
    VraisemblanceInitiale,
)
from ebios_rm.domain.essential_asset import EssentialAsset
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.domain.operational_scenario import AttackStep, GapConsideration, OperationalScenario
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.attack_repository import Mitigation, MitigationCatalogue
from ebios_rm.workshops.common import AtelierDataError
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap, ControlReference, Workshop1Output
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import Workshop4Output
from ebios_rm.workshops.workshop5_traitement_risque.assessment import (
    build_mesure,
    read_priorite,
    run_quality_checks,
    validate_atelier4,
)
from ebios_rm.workshops.workshop5_traitement_risque.models import (
    REASON_MITIGATION_INCONNUE,
    REASON_PROPOSITION_VIDE,
    REASON_SCENARIO_INCONNU,
    MesureProposal,
    Workshop5Input,
)
from ebios_rm.workshops.workshop5_traitement_risque.workshop import (
    build_workshop5_input,
    cited_technique_ids,
    run_workshop5,
)

GAP_RGPD = "BG-rgpd32"
GAP_ADMIN = "BG-rgpd30"


# --- Small, self-contained fixtures ------------------------------------------

def _catalogue() -> MitigationCatalogue:
    return MitigationCatalogue({
        "T1078": (Mitigation("M1032", "Multi-factor Authentication"),
                  Mitigation("M1018", "User Account Management")),
        "T1486": (Mitigation("M1053", "Data Backup"),),
    })


def _scenario(**overrides) -> OperationalScenario:
    base = dict(
        id="SO-01", scenario_strategique_id="SS-01", source_risque_id="SR-01", objectif_vise_id="OV-01",
        gravite=Gravite.CRITIQUE, revised_likelihood=VraisemblanceInitiale.V4,
        revised_risk_level=NiveauRisque.CRITIQUE,
        attack_path=[AttackStep(tactic="initial-access", technique_id="T1078", description="Accès via identifiants")],
    )
    base.update(overrides)
    return OperationalScenario(**base)


def _w5_input(**overrides) -> Workshop5Input:
    base = dict(organisation_nom="Clinique Test", secteur_activite="Santé", scenarios=[_scenario()])
    base.update(overrides)
    return Workshop5Input(**base)


def _proposal(**overrides) -> MesureProposal:
    base = dict(
        description="Activer la double authentification sur le VPN",
        scenarios_associes=["SO-01"], mitigation_ids_attck=["M1032"],
        cout="Faible", efficacite="Bloque l'accès initial", delai="Immédiat", priorite="Élevée",
    )
    base.update(overrides)
    return MesureProposal(**base)


# --- read_priorite ------------------------------------------------------------

def test_read_priorite_exact_value():
    assert read_priorite("Élevée") == PrioriteMesure.ELEVEE


def test_read_priorite_with_surrounding_prose():
    assert read_priorite("priorité moyenne, à planifier") == PrioriteMesure.MOYENNE


def test_read_priorite_case_and_accent_insensitive():
    assert read_priorite("elevee") == PrioriteMesure.ELEVEE


def test_read_priorite_faible():
    assert read_priorite("Faible") == PrioriteMesure.FAIBLE


def test_read_priorite_invalid_value_is_none():
    assert read_priorite("Haute") is None


def test_read_priorite_empty_or_none_is_none():
    assert read_priorite("") is None
    assert read_priorite(None) is None


# --- validate_atelier4 --------------------------------------------------------

def test_validate_atelier4_accepts_consistent_scenarios():
    gap = BaselineGap(gap_id="BG-01", weakness="w", risk_categories=["initial_access"])
    scenario = _scenario(baseline_gaps_considered=[
        GapConsideration(gap_id="BG-01", impact_type=ImpactType.INCREASES_LIKELIHOOD, impact_on_scenario="x")])
    assert validate_atelier4([scenario], [gap]) == []


def test_validate_atelier4_flags_empty_scenario_list():
    alerts = validate_atelier4([], [])
    assert any(a.reference == "atelier4" for a in alerts)


def test_validate_atelier4_flags_duplicate_scenario_ids():
    alerts = validate_atelier4([_scenario(), _scenario()], [])
    assert any("double" in a.probleme for a in alerts)


def test_validate_atelier4_flags_untransmitted_gap_reference():
    scenario = _scenario(baseline_gaps_considered=[
        GapConsideration(gap_id="BG-inconnu", impact_type=ImpactType.NO_IMPACT, impact_on_scenario="x")])
    alerts = validate_atelier4([scenario], [])  # aucun écart transmis
    assert any("BG-inconnu" in a.probleme for a in alerts)
    assert not any(a.bloquant for a in alerts)  # signalé, non bloquant


# --- build_mesure --------------------------------------------------------------

def test_build_mesure_accepts_a_clean_proposal():
    mesure, ecartes = build_mesure(1, _proposal(), _w5_input(), _catalogue())
    assert mesure.id == "MT-01"
    assert mesure.priorite == PrioriteMesure.ELEVEE
    assert mesure.mitigation_ids_attck == ["M1032"]
    assert mesure.anomalies == []
    assert ecartes == []


def test_build_mesure_drops_unreal_mitigation_keeps_the_measure():
    proposal = _proposal(mitigation_ids_attck=["M1032", "M9999"])
    mesure, ecartes = build_mesure(1, proposal, _w5_input(), _catalogue())
    assert mesure is not None
    assert mesure.mitigation_ids_attck == ["M1032"]  # le vrai id survit
    assert any(a.code == "mitigation_inconnue" for a in mesure.anomalies)
    assert len(ecartes) == 1
    assert ecartes[0].raison == REASON_MITIGATION_INCONNUE


def test_build_mesure_drops_unknown_scenario_reference_keeps_the_measure():
    proposal = _proposal(scenarios_associes=["SO-01", "SO-99"])
    mesure, ecartes = build_mesure(1, proposal, _w5_input(), _catalogue())
    assert mesure.scenarios_associes == ["SO-01"]
    assert any(a.code == "scenario_inconnu" for a in mesure.anomalies)
    assert ecartes[0].raison == REASON_SCENARIO_INCONNU


def test_build_mesure_invalid_priorite_is_kept_with_anomaly_not_dropped():
    proposal = _proposal(priorite="Haute")
    mesure, ecartes = build_mesure(1, proposal, _w5_input(), _catalogue())
    assert mesure is not None  # gardée, pas rejetée en bloc
    assert mesure.priorite is None
    assert any(a.code == "priorite_invalide" for a in mesure.anomalies)
    assert ecartes == []


def test_build_mesure_flags_missing_criteria():
    proposal = _proposal(cout="", efficacite="", delai="Immédiat")
    mesure, _ = build_mesure(1, proposal, _w5_input(), _catalogue())
    anomaly = next(a for a in mesure.anomalies if a.code == "critere_manquant")
    assert "coût" in anomaly.message and "efficacité" in anomaly.message


def test_build_mesure_flags_missing_description():
    proposal = _proposal(description="")
    mesure, _ = build_mesure(1, proposal, _w5_input(), _catalogue())
    assert mesure is not None  # ancrée par un scénario, donc gardée
    assert any(a.code == "description_absente" for a in mesure.anomalies)


def test_build_mesure_flags_measure_with_no_anchor_non_blocking():
    proposal = _proposal(scenarios_associes=[], mitigation_ids_attck=[])
    mesure, _ = build_mesure(1, proposal, _w5_input(), _catalogue())
    anomaly = next(a for a in mesure.anomalies if a.code == "mesure_sans_ancrage")
    assert not anomaly.bloquante


def test_build_mesure_wholly_empty_proposal_is_set_aside():
    proposal = _proposal(description="", scenarios_associes=[], mitigation_ids_attck=[])
    mesure, ecartes = build_mesure(1, proposal, _w5_input(), _catalogue())
    assert mesure is None
    assert len(ecartes) == 1
    assert ecartes[0].raison == REASON_PROPOSITION_VIDE


def test_build_mesure_socle_wide_measure_with_no_anchor_but_real_description_is_kept():
    # Une mesure qui traite un écart général du socle (pas un chemin d'attaque
    # précis) : pas de scénario ni de mitigation, mais une vraie description.
    proposal = _proposal(description="Publier une politique de mots de passe pour tout le SI",
                         scenarios_associes=[], mitigation_ids_attck=[])
    mesure, ecartes = build_mesure(1, proposal, _w5_input(), _catalogue())
    assert mesure is not None
    assert ecartes == []


# --- run_quality_checks --------------------------------------------------------

def test_quality_checks_valid_on_a_clean_output():
    mesure, _ = build_mesure(1, _proposal(), _w5_input(), _catalogue())
    report = run_quality_checks(_w5_input(), [mesure], _catalogue())
    assert report.statut == "valide"


def test_quality_checks_flags_uncovered_scenario():
    scenario2 = _scenario(id="SO-02")
    w5_input = _w5_input(scenarios=[_scenario(), scenario2])
    mesure, _ = build_mesure(1, _proposal(), w5_input, _catalogue())  # ne couvre que SO-01
    report = run_quality_checks(w5_input, [mesure], _catalogue())
    coverage = next(c for c in report.checks if c.controle == "Couverture")
    assert "SO-02" in coverage.message


def test_quality_checks_flags_incomplete_criteria():
    mesure, _ = build_mesure(1, _proposal(cout=""), _w5_input(), _catalogue())
    report = run_quality_checks(_w5_input(), [mesure], _catalogue())
    check = next(c for c in report.checks if c.controle == "Critères d'arbitrage")
    assert check.statut == "erreur"


def test_quality_checks_flags_unrated_priority():
    mesure, _ = build_mesure(1, _proposal(priorite="Haute"), _w5_input(), _catalogue())
    report = run_quality_checks(_w5_input(), [mesure], _catalogue())
    check = next(c for c in report.checks if c.controle == "Priorité")
    assert check.statut == "erreur"


def test_quality_checks_flags_scenario_with_considered_gap_but_no_measure():
    scenario = _scenario(baseline_gaps_considered=[
        GapConsideration(gap_id="BG-01", impact_type=ImpactType.INCREASES_LIKELIHOOD, impact_on_scenario="x")])
    w5_input = _w5_input(scenarios=[scenario])
    report = run_quality_checks(w5_input, [], _catalogue())  # aucune mesure du tout
    check = next(c for c in report.checks if c.controle == "Écarts du socle rattachés à un scénario")
    assert check.statut == "erreur"
    assert "SO-01" in check.message


# --- build_workshop5_input / cited_technique_ids -------------------------------

def _w1_with_gaps() -> Workshop1Output:
    return Workshop1Output(
        biens_essentiels=[EssentialAsset(id="BE-1", nom="Dossier patient", description="d", nature="information",
                                          processus_metier_associes=["p"], origin=Origin.ASSESSMENT,
                                          derived_from_fact_fields=["x"])],
        baseline_gaps_full=[
            BaselineGap(gap_id=GAP_RGPD, weakness="Absence de MFA",
                        controls=[ControlReference(framework="RGPD", control_id="Article-32")],
                        risk_categories=["credential_access", "exfiltration"]),  # comme le vrai RGPD-Art32
            BaselineGap(gap_id=GAP_ADMIN, weakness="Absence de registre des traitements",
                        controls=[ControlReference(framework="RGPD", control_id="Article-30")],
                        risk_categories=[]),  # purement administratif
        ],
    )


def test_build_workshop5_input_keeps_gap_with_real_risk_category():
    mc = MissionContext(organisation_nom="Clinique Test", secteur_activite="Santé", applicable_frameworks=["RGPD"])
    w4 = Workshop4Output(scenarios=[_scenario()])
    w5_input = build_workshop5_input(mc, _w1_with_gaps(), w4)
    assert [g.gap_id for g in w5_input.baseline_gaps] == [GAP_RGPD]


def test_build_workshop5_input_excludes_administrative_rgpd_entry():
    mc = MissionContext(organisation_nom="Clinique Test", secteur_activite="Santé", applicable_frameworks=["RGPD"])
    w4 = Workshop4Output(scenarios=[_scenario()])
    w5_input = build_workshop5_input(mc, _w1_with_gaps(), w4)
    assert GAP_ADMIN not in [g.gap_id for g in w5_input.baseline_gaps]


def test_build_workshop5_input_keeps_the_full_control_reference():
    # Contrairement à l'atelier 4, l'atelier 5 doit voir framework/control_id.
    mc = MissionContext(organisation_nom="Clinique Test", secteur_activite="Santé", applicable_frameworks=["RGPD"])
    w4 = Workshop4Output(scenarios=[_scenario()])
    w5_input = build_workshop5_input(mc, _w1_with_gaps(), w4)
    gap = w5_input.baseline_gaps[0]
    assert gap.controls[0].framework == "RGPD"
    assert gap.controls[0].control_id == "Article-32"


def test_cited_technique_ids_collects_across_all_scenarios():
    s1 = _scenario(id="SO-01", attack_path=[AttackStep(tactic="initial-access", technique_id="T1078", description="d")])
    s2 = _scenario(id="SO-02", attack_path=[
        AttackStep(tactic="impact", technique_id="T1486", description="d"),
        AttackStep(tactic="execution", technique_id=None, description="sans technique"),
    ])
    ids = cited_technique_ids(_w5_input(scenarios=[s1, s2]))
    assert ids == {"T1078", "T1486"}


# --- run_workshop5: end to end, no network -------------------------------------

class _FakeRunner:
    def __init__(self, batch):
        self._batch = batch

    def propose_mesures(self, w5_input, mitigations):
        return self._batch


class _FakeAttackRepo:
    def __init__(self, catalogue: MitigationCatalogue) -> None:
        self._catalogue = catalogue

    def mitigation_catalogue(self, technique_ids):
        return self._catalogue


def test_run_workshop5_end_to_end():
    from ebios_rm.workshops.workshop5_traitement_risque.models import MesuresBatch

    w1 = _w1_with_gaps()
    w4 = Workshop4Output(scenarios=[_scenario(baseline_gaps_considered=[
        GapConsideration(gap_id=GAP_RGPD, impact_type=ImpactType.INCREASES_LIKELIHOOD, impact_on_scenario="x")])])
    mc = MissionContext(organisation_nom="Clinique Test", secteur_activite="Santé", applicable_frameworks=["RGPD"])
    w5_input = build_workshop5_input(mc, w1, w4)

    runner = _FakeRunner(MesuresBatch(mesures=[_proposal()]))
    repo = _FakeAttackRepo(_catalogue())

    output = run_workshop5(w5_input, runner, repo, w4, w1)

    assert len(output.mesures) == 1
    assert output.mesures[0].priorite == PrioriteMesure.ELEVEE
    assert output.quality_report.statut == "valide"


def test_run_workshop5_raises_on_blocking_atelier4_alert():
    from ebios_rm.workshops.workshop5_traitement_risque.models import MesuresBatch

    w1 = Workshop1Output()  # aucun écart transmis
    w4 = Workshop4Output(scenarios=[])  # aucun scénario -> alerte bloquante
    mc = MissionContext(organisation_nom="Clinique Test", secteur_activite="Santé", applicable_frameworks=[])
    w5_input = build_workshop5_input(mc, w1, w4)

    runner = _FakeRunner(MesuresBatch(mesures=[]))
    repo = _FakeAttackRepo(_catalogue())

    try:
        run_workshop5(w5_input, runner, repo, w4, w1)
        assert False, "aurait dû lever AtelierDataError"
    except AtelierDataError as exc:
        assert exc.atelier == 4
