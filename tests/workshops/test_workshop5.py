"""Fiche de test — Atelier 5, traitement du risque (conception §19; méthode atelier 5).

Everything runs against the pure functions of assessment.py and workshop.py; no test
makes a real LLM call. The assertions sit where the methodology is enforced in code:
the risk map inherited from the ateliers before it, the acceptability scale, the checks
on every proposed measure (a real axis, something real to act on, only ATT&CK
mitigation ids the base returned, no duplicate), the priority rule, the bounds on the
residual re-evaluation — a measure lowers the vraisemblance, never the gravité — the
formal acceptance, and the quality checker.
"""

from __future__ import annotations

import pytest

from ebios_rm.domain.enums import (
    Acceptabilite,
    AxeMesure,
    CategorieImpact,
    Gravite,
    NiveauRisque,
    OptionTraitement,
    Origin,
    Priorite,
    VraisemblanceInitiale,
)
from ebios_rm.domain.essential_asset import EssentialAsset, SupportAsset
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.domain.operational_scenario import AttackStep, OperationalScenario
from ebios_rm.domain.risk_scenario import MesureSecurite
from ebios_rm.domain.risk_source import ObjectifVise, RiskSource
from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.repositories.attack_repository import AttackMitigation
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap, ControlReference
from ebios_rm.workshops.workshop5_traitement_risque.assessment import (
    MAX_EFFET_MESURE,
    accept_residuel,
    acceptabilite_of,
    apply_formulations,
    apply_residuel,
    build_cadre,
    build_mesures,
    build_risques,
    couverture_er,
    er_graves_non_couverts,
    keep_initial_residuel,
    link_mesures,
    option_proposee,
    priorite_of,
    read_axe,
    remove_mesures,
    run_quality_checks,
    set_traitement,
    validate_atelier4,
)
from ebios_rm.workshops.workshop5_traitement_risque.models import (
    ACTIVITE_FORMULATION,
    REASON_MESURE_AXE_INCONNU,
    REASON_MESURE_DOUBLON,
    REASON_MESURE_ECARTEE_PAR_AUDITEUR,
    REASON_MESURE_RISQUE_INCONNU,
    REASON_MESURE_SANS_LIEN,
    REASON_RESIDUEL_AGGRAVE,
    REASON_RESIDUEL_INCONNU,
    REASON_RESIDUEL_SANS_MESURE,
    STATUT_AVERTISSEMENT,
    STATUT_ERREUR,
    IndicatorProposal,
    MeasureProposal,
    ResidualProposal,
    RiskFormulationProposal,
    Workshop5Input,
    Workshop5Output,
)
from ebios_rm.workshops.workshop5_traitement_risque.prompts import mesures_prompt
from ebios_rm.workshops.workshop5_traitement_risque.workshop import (
    assemble_output,
    initial_output,
    techniques_citees,
)

GAP_ID = "BG-a1b2c3"


# --- Small, self-contained fixtures --------------------------------------

def _mode(
    mode_id: str,
    scenario_id: str,
    *,
    retenu: bool = False,
    gravite: Gravite = Gravite.CRITIQUE,
    revised: VraisemblanceInitiale | None = VraisemblanceInitiale.V3,
    evenements: tuple[str, ...] = ("ER-1",),
    techniques: tuple[str, ...] = ("T1078", "T1486"),
) -> OperationalScenario:
    return OperationalScenario(
        id=mode_id,
        scenario_strategique_id=scenario_id,
        source_risque_id="SR-01",
        objectif_vise_id="OV-01",
        variante=f"Mode {mode_id}",
        voie="acces_distant",
        retenu=retenu,
        gravite=gravite,
        vraisemblance_initiale=VraisemblanceInitiale.V2,
        revised_likelihood=revised,
        biens_essentiels_ids=["BE-1"],
        evenements_redoutes_ids=list(evenements),
        attack_path=[
            AttackStep(tactic="initial-access", technique_id=t, technique_name=f"Technique {t}",
                       description=f"Étape {n} du mode {mode_id}", bien_support_id="BS-1",
                       justification="Aucune MFA en place.")
            for n, t in enumerate(techniques, 1)
        ],
    )


def _gap(gap_id: str = GAP_ID) -> BaselineGap:
    return BaselineGap(
        gap_id=gap_id,
        weakness="Absence de MFA sur les accès distants",
        controls=[ControlReference(framework="ISO27001", control_id="A.5.17")],
        risk_categories=["initial_access"],
        evidence_quote="Le VPN n'exige qu'un mot de passe.",
    )


def _scenario(scenario_id: str, gravite: Gravite) -> StrategicScenario:
    return StrategicScenario(
        id=scenario_id, source_risque_id="SR-01", objectif_vise_id="OV-01",
        couple_id=f"C-{scenario_id}", resume=f"Route du scénario {scenario_id}",
        justification="Plausible dans ce contexte.", parties_prenantes=["Prestataire d'infogérance"],
        biens_essentiels_ids=["BE-1"], evenements_redoutes_ids=["ER-1"], gravite=gravite,
    )


def _feared(event_id: str, gravite: Gravite) -> FearedEvent:
    return FearedEvent(id=event_id, description=f"Événement {event_id}", bien_essentiel_id="BE-1",
                       categorie_impact=CategorieImpact.FONCTIONNEMENT, gravite=gravite,
                       origin=Origin.ASSESSMENT)


def _w5_input(*, modes=None, scenarios=None, evenements=None, baseline_gaps=None) -> Workshop5Input:
    """SS-01 critique with two modes (one retained), SS-02 grave with one."""
    return Workshop5Input(
        organisation_nom="Clinique Test",
        secteur_activite="Santé",
        contexte={"maturite_securite": "faible", "seuil_acceptation_risque": "Élevé inacceptable"},
        modes_operatoires=modes if modes is not None else [
            _mode("SO-01", "SS-01", retenu=True),
            _mode("SO-02", "SS-01", revised=VraisemblanceInitiale.V2),
            _mode("SO-03", "SS-02", retenu=True, gravite=Gravite.GRAVE,
                  revised=VraisemblanceInitiale.V1, evenements=("ER-3",)),
        ],
        scenarios_strategiques=scenarios if scenarios is not None else [
            _scenario("SS-01", Gravite.CRITIQUE), _scenario("SS-02", Gravite.GRAVE),
        ],
        sources_risque=[RiskSource(id="SR-01", categorie_id="CAT-1", nom="Concurrent",
                                   justification="Secteur concurrentiel.")],
        objectifs_vises=[ObjectifVise(id="OV-01", finalite_id="F-1", description="Obtenir le fichier patients",
                                      justification="Valeur marchande.")],
        biens_essentiels=[EssentialAsset(id="BE-1", nom="Dossier patient", description="Données de soin",
                                         nature="information", origin=Origin.ASSESSMENT,
                                         derived_from_fact_fields=["x"])],
        biens_supports=[SupportAsset(id="BS-1", nom="SIH", description="Système d'information hospitalier",
                                     type_support="application", biens_essentiels_supportes=["BE-1"],
                                     origin=Origin.ASSESSMENT, derived_from_fact_fields=["x"])],
        evenements_redoutes=evenements if evenements is not None else [
            _feared("ER-1", Gravite.CRITIQUE), _feared("ER-2", Gravite.GRAVE), _feared("ER-4", Gravite.MINIMALE),
        ],
        baseline_gaps=baseline_gaps if baseline_gaps is not None else [_gap()],
    )


def _mitigations() -> dict[str, list[AttackMitigation]]:
    return {
        "T1078": [AttackMitigation("M1032", "Multi-factor Authentication", "Exiger un second facteur.")],
        "T1486": [AttackMitigation("M1053", "Data Backup", "Sauvegardes régulières hors ligne.")],
    }


def _output(w5_input: Workshop5Input | None = None) -> Workshop5Output:
    """The risk map as activity 5-1 builds it, before anyone decides anything."""
    return initial_output(w5_input or _w5_input(), "ATT&CK-Latest (sha256 test000000)")


def _measure_proposal(**overrides) -> MeasureProposal:
    base = dict(
        axe="protection", thematique="authentification et contrôle d'accès",
        libelle="Déployer l'authentification multifacteur sur les accès distants",
        description="MFA sur le VPN et les interfaces d'administration.",
        risques_ids=["R1"], modes_ids=["SO-01"], etapes_visees=["SO-01 étape 1"], gap_ids=[GAP_ID],
        mitigation_ids_attck=["M1032"], origine="atelier4_vulnerabilite",
        freins="Validation de la direction des soins.", cout_complexite="++",
        charge_estimee="20 j/h", echeance="6 mois",
        justification="Casse l'étape d'accès initial du mode retenu.", effet_vraisemblance=1,
    )
    base.update(overrides)
    return MeasureProposal(**base)


def _with_plan(**proposal_overrides):
    """A treated risk map: options decided, one measure retained."""
    w5_input = _w5_input()
    output = _output(w5_input)
    output = set_traitement(output, "R1", OptionTraitement.REDUCTION, "Risque inacceptable en l'état.")
    output = set_traitement(output, "R2", OptionTraitement.MAINTIEN, "Tolérable, suivi en comité.")
    mesures, ecartes = build_mesures([_measure_proposal(**proposal_overrides)], output, w5_input,
                                     _mitigations())
    output = link_mesures(output.model_copy(update={"mesures": mesures, "elements_ecartes": ecartes}))
    return w5_input, output


# --- validate_atelier4: atelier 5 alerts, it never repairs -------------------

def test_validate_atelier4_accepts_one_retained_mode_per_scenario():
    w5_input = _w5_input()
    assert validate_atelier4(w5_input.modes_operatoires, ["SS-01", "SS-02"]) == []


def test_validate_atelier4_flags_a_scenario_without_a_retained_mode():
    modes = [_mode("SO-01", "SS-01"), _mode("SO-02", "SS-01")]
    alerts = validate_atelier4(modes, ["SS-01"])
    assert [a.reference for a in alerts] == ["SS-01"]
    assert "0 mode(s) retenu(s)" in alerts[0].probleme


def test_validate_atelier4_flags_a_retained_mode_without_revised_likelihood():
    modes = [_mode("SO-01", "SS-01", retenu=True, revised=None)]
    alerts = validate_atelier4(modes, ["SS-01"])
    assert [a.reference for a in alerts] == ["SO-01"]


def test_validate_atelier4_flags_a_mode_on_an_unknown_strategic_scenario():
    alerts = validate_atelier4([_mode("SO-09", "SS-99", retenu=True)], ["SS-01"])
    assert any(a.reference == "SO-09" for a in alerts)


def test_initial_output_refuses_a_blocking_atelier4(monkeypatch):
    from ebios_rm.workshops.common import AtelierDataError
    w5_input = _w5_input(modes=[_mode("SO-01", "SS-01", retenu=True, revised=None)],
                         scenarios=[_scenario("SS-01", Gravite.CRITIQUE)])
    w5_input = w5_input.model_copy(update={
        "alertes_atelier4": validate_atelier4(w5_input.modes_operatoires, ["SS-01"])})
    with pytest.raises(AtelierDataError):
        initial_output(w5_input, "ATT&CK-test")


# --- 5-1: the risk map is inherited, never re-judged -------------------------

def test_build_risques_inherits_gravite_and_the_retained_mode_likelihood():
    risques = build_risques(_w5_input())
    assert [r.id for r in risques] == ["R1", "R2"]
    r1 = risques[0]
    assert (r1.scenario_strategique_id, r1.mode_retenu_id) == ("SS-01", "SO-01")
    assert (r1.gravite, r1.vraisemblance) == (Gravite.CRITIQUE, VraisemblanceInitiale.V3)
    assert r1.niveau_risque is NiveauRisque.CRITIQUE
    assert r1.acceptabilite is Acceptabilite.INACCEPTABLE


def test_build_risques_carries_the_alternative_modes_with_the_risk():
    r1 = build_risques(_w5_input())[0]
    assert r1.modes_alternatifs_ids == ["SO-02"]


def test_build_risques_orders_worst_first():
    risques = build_risques(_w5_input())
    assert [(r.id, r.niveau_risque) for r in risques] == [
        ("R1", NiveauRisque.CRITIQUE), ("R2", NiveauRisque.MOYEN)]


def test_build_risques_skips_a_scenario_whose_retained_mode_has_no_likelihood():
    w5_input = _w5_input(modes=[_mode("SO-01", "SS-01", retenu=True, revised=None)],
                         scenarios=[_scenario("SS-01", Gravite.CRITIQUE)])
    assert build_risques(w5_input) == []


def test_acceptabilite_follows_the_scale():
    assert acceptabilite_of(NiveauRisque.FAIBLE) is Acceptabilite.ACCEPTABLE
    assert acceptabilite_of(NiveauRisque.MOYEN) is Acceptabilite.TOLERABLE
    assert acceptabilite_of(NiveauRisque.ELEVE) is Acceptabilite.INACCEPTABLE
    assert acceptabilite_of(NiveauRisque.CRITIQUE) is Acceptabilite.INACCEPTABLE
    assert acceptabilite_of(None) is None


def test_apply_formulations_takes_the_wording_and_nothing_else():
    output = _output()
    formulated = apply_formulations(output.risques, [
        RiskFormulationProposal(risque_id="r1", libelle="Un concurrent obtient le fichier patients."),
        RiskFormulationProposal(risque_id="R2", libelle="   "),
    ])
    assert formulated[0].libelle == "Un concurrent obtient le fichier patients."
    assert formulated[0].niveau_risque is output.risques[0].niveau_risque
    assert formulated[1].libelle == ""          # blank wording changes nothing


def test_initial_output_marks_nothing_as_done_before_the_model_is_asked():
    assert ACTIVITE_FORMULATION not in _output().activites_faites


# --- 5-1: the completeness pass on atelier 1's feared events -----------------

def test_couverture_er_says_which_feared_events_a_risk_carries():
    w5_input = _w5_input()
    couverture = couverture_er(w5_input, build_risques(w5_input))
    by_id = {c.evenement_redoute_id: c for c in couverture}
    assert by_id["ER-1"].risques_ids == ["R1"]
    assert by_id["ER-2"].risques_ids == [] and by_id["ER-2"].couvert is False


def test_er_graves_non_couverts_keeps_only_the_serious_ones():
    w5_input = _w5_input()
    uncovered = er_graves_non_couverts(couverture_er(w5_input, build_risques(w5_input)))
    assert [c.evenement_redoute_id for c in uncovered] == ["ER-2"]   # ER-4 is minimale


# --- 5-2: the auditor decides, the scale only proposes -----------------------

def test_option_proposee_points_at_reduction_unless_acceptable():
    risques = build_risques(_w5_input())
    assert option_proposee(risques[0]) is OptionTraitement.REDUCTION
    acceptable = risques[1].model_copy(update={"acceptabilite": Acceptabilite.ACCEPTABLE})
    assert option_proposee(acceptable) is OptionTraitement.MAINTIEN


def test_set_traitement_requires_a_real_justification():
    output = _output()
    with pytest.raises(ValueError):
        set_traitement(output, "R1", OptionTraitement.REDUCTION, "  ::  ")


def test_set_traitement_refuses_an_unknown_risk():
    with pytest.raises(ValueError):
        set_traitement(_output(), "R99", OptionTraitement.REDUCTION, "Motif valable.")


def test_set_traitement_records_the_decision_on_that_risk_only():
    output = set_traitement(_output(), "R1", OptionTraitement.PARTAGE, "Couvert par le contrat d'assurance.")
    assert output.risques[0].option_traitement is OptionTraitement.PARTAGE
    assert output.risques[0].justification_traitement == "Couvert par le contrat d'assurance."
    assert output.risques[1].option_traitement is None


# --- 5-3: every measure is checked before it enters the plan -----------------

def test_read_axe_accepts_the_four_axes_and_refuses_the_rest():
    assert read_axe("Protection") is AxeMesure.PROTECTION
    assert read_axe("defense") is AxeMesure.DEFENSE
    assert read_axe("résilience organisationnelle") is AxeMesure.RESILIENCE  # accents and prose folded
    assert read_axe("cyber") is None
    assert read_axe("") is None


def test_build_mesures_keeps_a_grounded_measure_and_only_real_attck_ids():
    _w5, output = _with_plan(mitigation_ids_attck=["M1032", "M9999"])
    mesure = output.mesures[0]
    assert mesure.id == "M-01"
    assert mesure.axe is AxeMesure.PROTECTION
    assert mesure.mitigation_ids_attck == ["M1032"]           # M9999 never came out of the base
    assert mesure.gap_ids == [GAP_ID] and mesure.modes_ids == ["SO-01"]


def test_build_mesures_rejects_an_unknown_axis_with_its_reason():
    w5_input = _w5_input()
    output = _output(w5_input)
    mesures, ecartes = build_mesures([_measure_proposal(axe="cyber")], output, w5_input, _mitigations())
    assert mesures == []
    assert [e.raison for e in ecartes] == [REASON_MESURE_AXE_INCONNU]


def test_build_mesures_rejects_a_measure_that_acts_on_nothing():
    w5_input = _w5_input()
    output = _output(w5_input)
    mesures, ecartes = build_mesures(
        [_measure_proposal(risques_ids=[], modes_ids=[], gap_ids=[])], output, w5_input, _mitigations())
    assert mesures == []
    assert [e.raison for e in ecartes] == [REASON_MESURE_SANS_LIEN]


def test_build_mesures_names_an_invented_risk_id_as_such():
    w5_input = _w5_input()
    output = _output(w5_input)
    mesures, ecartes = build_mesures(
        [_measure_proposal(risques_ids=["R42"], modes_ids=[], gap_ids=[])], output, w5_input, _mitigations())
    assert mesures == [] and [e.raison for e in ecartes] == [REASON_MESURE_RISQUE_INCONNU]


def test_build_mesures_drops_a_measure_said_twice():
    w5_input = _w5_input()
    output = _output(w5_input)
    mesures, ecartes = build_mesures(
        [_measure_proposal(), _measure_proposal(description="Reformulée autrement.")],
        output, w5_input, _mitigations())
    assert len(mesures) == 1
    assert [e.raison for e in ecartes] == [REASON_MESURE_DOUBLON]


def test_build_mesures_caps_the_claimed_effect_and_the_cost_vocabulary():
    w5_input = _w5_input()
    output = _output(w5_input)
    mesures, _ = build_mesures([_measure_proposal(effet_vraisemblance=4, cout_complexite="énorme")],
                               output, w5_input, _mitigations())
    assert mesures[0].effet_vraisemblance == MAX_EFFET_MESURE
    assert mesures[0].cout_complexite == ""


def test_build_mesures_numbers_by_axis_in_the_plan_order():
    w5_input = _w5_input()
    output = _output(w5_input)
    mesures, _ = build_mesures([
        _measure_proposal(axe="resilience", libelle="Tester la restauration des sauvegardes"),
        _measure_proposal(axe="gouvernance", libelle="Sensibiliser les agents au hameçonnage"),
    ], output, w5_input, _mitigations())
    assert [(m.id, m.axe) for m in mesures] == [
        ("M-01", AxeMesure.GOUVERNANCE), ("M-02", AxeMesure.RESILIENCE)]


def test_priorite_is_the_risk_level_first_then_the_cost():
    risques = build_risques(_w5_input())          # R1 critique, R2 moyen
    cheap = MesureSecurite(id="M-01", axe=AxeMesure.PROTECTION, libelle="m", risques_ids=["R1"],
                           cout_complexite="+")
    costly = cheap.model_copy(update={"cout_complexite": "+++"})
    assert priorite_of(cheap, risques) is Priorite.P1
    assert priorite_of(costly, risques) is Priorite.P2
    assert priorite_of(cheap.model_copy(update={"risques_ids": ["R2"]}), risques) is Priorite.P2
    assert priorite_of(cheap.model_copy(update={"risques_ids": []}), risques) is Priorite.P3


def test_priorite_uses_the_modes_when_the_measure_names_no_risk():
    risques = build_risques(_w5_input())
    via_mode = MesureSecurite(id="M-01", axe=AxeMesure.PROTECTION, libelle="m", modes_ids=["SO-01"],
                              cout_complexite="+")
    assert priorite_of(via_mode, risques) is Priorite.P1


def test_link_mesures_writes_each_risk_measure_list_from_the_measures():
    _w5, output = _with_plan()
    assert output.risques[0].mesures_ids == ["M-01"]
    assert output.risques[1].mesures_ids == []


def test_link_mesures_also_links_through_an_alternative_mode():
    w5_input = _w5_input()
    output = _output(w5_input)
    mesures, _ = build_mesures([_measure_proposal(risques_ids=[], modes_ids=["SO-02"])],
                               output, w5_input, _mitigations())
    linked = link_mesures(output.model_copy(update={"mesures": mesures}))
    assert linked.risques[0].mesures_ids == ["M-01"]   # SO-02 is an alternative mode of R1


def test_remove_mesures_keeps_the_reason_and_relinks():
    _w5, output = _with_plan()
    pruned = remove_mesures(output, ["M-01"], REASON_MESURE_ECARTEE_PAR_AUDITEUR, "Déjà couvert par un projet.")
    assert pruned.mesures == []
    assert pruned.risques[0].mesures_ids == []
    assert [e.raison for e in pruned.elements_ecartes] == [REASON_MESURE_ECARTEE_PAR_AUDITEUR]
    assert pruned.elements_ecartes[0].detail == "Déjà couvert par un projet."


def test_mesures_prompt_shows_only_the_mitigations_the_base_returned():
    w5_input = _w5_input()
    output = _output(w5_input)
    prompt = mesures_prompt(w5_input, output, output.risques, _mitigations())
    assert "M1032" in prompt and "M1053" in prompt and "M9999" not in prompt
    assert "authentification et contrôle d'accès" in prompt      # the plan's own vocabulary


def test_mesures_prompt_carries_the_auditor_rejection_reasons_on_a_relaunch():
    w5_input = _w5_input()
    output = _output(w5_input)
    prompt = mesures_prompt(w5_input, output, output.risques, _mitigations(),
                            ["Aucune mesure sur la sauvegarde."])
    assert "Aucune mesure sur la sauvegarde." in prompt


def test_techniques_citees_gathers_every_mode_not_only_the_retained_one():
    assert techniques_citees(_w5_input()) == ["T1078", "T1486"]


# --- 5-4: the residual risk, and what code refuses --------------------------

def test_apply_residuel_lowers_the_likelihood_and_recomputes_the_level():
    _w5, output = _with_plan(effet_vraisemblance=1)
    evaluated, ecartes = apply_residuel(output, [
        ResidualProposal(risque_id="R1", vraisemblance_residuelle="V2",
                         motif="M-01 casse l'étape d'accès initial du mode retenu."),
    ])
    r1 = evaluated.risques[0]
    assert ecartes == []
    assert r1.vraisemblance_residuelle is VraisemblanceInitiale.V2
    assert r1.gravite is Gravite.CRITIQUE                      # gravité never moves
    assert r1.niveau_risque_residuel is NiveauRisque.ELEVE
    assert r1.acceptabilite_residuelle is Acceptabilite.INACCEPTABLE


def test_apply_residuel_refuses_a_likelihood_that_rises():
    _w5, output = _with_plan()
    evaluated, ecartes = apply_residuel(output, [
        ResidualProposal(risque_id="R1", vraisemblance_residuelle="V4", motif="Le plan change peu de choses."),
    ])
    assert evaluated.risques[0].vraisemblance_residuelle is None
    assert [e.raison for e in ecartes] == [REASON_RESIDUEL_AGGRAVE]


def test_apply_residuel_refuses_a_drop_with_no_measure_on_that_risk():
    _w5, output = _with_plan()
    # R2 carries no measure, so nothing in the plan can justify a lower likelihood.
    output = output.model_copy(update={"risques": [
        output.risques[0],
        output.risques[1].model_copy(update={"vraisemblance": VraisemblanceInitiale.V3}),
    ]})
    evaluated, ecartes = apply_residuel(output, [
        ResidualProposal(risque_id="R2", vraisemblance_residuelle="V1", motif="Le plan y contribue."),
    ])
    assert evaluated.risques[1].vraisemblance_residuelle is None
    assert [e.raison for e in ecartes] == [REASON_RESIDUEL_SANS_MESURE]


def test_apply_residuel_bounds_the_drop_by_what_the_measures_claim():
    _w5, output = _with_plan(effet_vraisemblance=1)
    evaluated, _ = apply_residuel(output, [
        ResidualProposal(risque_id="R1", vraisemblance_residuelle="V1",
                         motif="Toutes les voies sont fermées."),
    ])
    r1 = evaluated.risques[0]
    assert r1.vraisemblance_residuelle is VraisemblanceInitiale.V2   # V3 - 1 level, not V1
    assert "borné" in r1.motif_residuel


def test_apply_residuel_needs_a_reason():
    _w5, output = _with_plan()
    evaluated, ecartes = apply_residuel(output, [
        ResidualProposal(risque_id="R1", vraisemblance_residuelle="V2", motif="  "),
    ])
    assert evaluated.risques[0].vraisemblance_residuelle is None
    assert len(ecartes) == 1


def test_apply_residuel_sets_aside_an_unknown_risk():
    _w5, output = _with_plan()
    _evaluated, ecartes = apply_residuel(output, [
        ResidualProposal(risque_id="R42", vraisemblance_residuelle="V1", motif="Un motif."),
    ])
    assert [e.raison for e in ecartes] == [REASON_RESIDUEL_INCONNU]


def test_keep_initial_residuel_leaves_an_untreated_risk_where_it_was():
    _w5, output = _with_plan()
    kept = keep_initial_residuel(output)
    r2 = kept.risques[1]
    assert r2.vraisemblance_residuelle is r2.vraisemblance
    assert r2.niveau_risque_residuel is r2.niveau_risque
    assert "Aucune mesure retenue" in r2.motif_residuel


def test_accept_residuel_names_who_accepts_and_refuses_an_empty_name():
    _w5, output = _with_plan()
    accepted = accept_residuel(output, ["R1"], "Mme la directrice générale")
    assert accepted.risques[0].accepte_par == "Mme la directrice générale"
    assert accepted.risques[1].accepte_par == ""
    with pytest.raises(ValueError):
        accept_residuel(output, ["R1"], " ")


# --- 5-5: the monitoring framework ------------------------------------------

def test_build_cadre_keeps_only_indicators_that_measure_something():
    _w5, output = _with_plan()
    cadre, ecartes = build_cadre([
        IndicatorProposal(libelle="Taux de comptes couverts par la MFA", type_valeur="taux",
                          cible="100 % des accès distants", frequence="trimestrielle",
                          mesures_ids=["M-01", "M-99"]),
        IndicatorProposal(libelle="Amélioration de la posture", type_valeur="ressenti", cible=""),
    ], output, comite="Comité sécurité semestriel", cycles="12 mois", prochaine_revue="2026-03")
    assert [i.id for i in cadre.indicateurs] == ["IND-01"]
    assert cadre.indicateurs[0].mesures_ids == ["M-01"]          # M-99 is not in the plan
    assert cadre.comite == "Comité sécurité semestriel"
    assert len(ecartes) == 1


# --- The quality checker ----------------------------------------------------

def _checks(report) -> dict[str, tuple[str, str]]:
    return {c.controle: (c.statut, c.message) for c in report.checks}


def _complete_plan():
    """A plan the checker should pass: decided, measured, evaluated, accepted, followed."""
    w5_input = _w5_input(evenements=[_feared("ER-1", Gravite.CRITIQUE), _feared("ER-3", Gravite.GRAVE)])
    output = initial_output(w5_input, "ATT&CK-test")
    output = apply_formulations(output.risques, [
        RiskFormulationProposal(risque_id="R1", libelle="Un concurrent obtient le fichier patients."),
        RiskFormulationProposal(risque_id="R2", libelle="Un concurrent perturbe la prise en charge."),
    ])
    output = Workshop5Output(risques=output, couverture_er=couverture_er(w5_input, output))
    output = set_traitement(output, "R1", OptionTraitement.REDUCTION, "Inacceptable en l'état.")
    output = set_traitement(output, "R2", OptionTraitement.MAINTIEN, "Tolérable, suivi en comité.")
    mesures, _ = build_mesures([
        _measure_proposal(modes_ids=["SO-01", "SO-02"], cout_complexite="+"),
    ], output, w5_input, _mitigations())
    output = link_mesures(output.model_copy(update={"mesures": mesures}))
    output, _ = apply_residuel(output, [
        ResidualProposal(risque_id="R1", vraisemblance_residuelle="V2",
                         motif="M-01 casse l'étape d'accès initial des deux modes."),
    ])
    output = keep_initial_residuel(output)
    output = accept_residuel(output, ["R1", "R2"], "Mme la directrice générale")
    cadre, _ = build_cadre([IndicatorProposal(libelle="Taux de comptes MFA", type_valeur="taux",
                                             cible="100 %", frequence="trimestrielle", mesures_ids=["M-01"])],
                           output, comite="Comité sécurité semestriel", cycles="12 mois")
    return w5_input, output.model_copy(update={"cadre_suivi": cadre})


def test_quality_report_is_clean_on_a_complete_plan():
    w5_input, output = _complete_plan()
    final = assemble_output(w5_input, output)
    errors = [c.controle for c in final.quality_report.checks if c.statut == STATUT_ERREUR]
    assert errors == []
    assert final.quality_report.statut in {"valide", STATUT_AVERTISSEMENT}


def test_quality_report_flags_an_uncovered_serious_feared_event_as_an_error():
    w5_input, output = _complete_plan()
    w5_input = w5_input.model_copy(update={
        "evenements_redoutes": [*w5_input.evenements_redoutes, _feared("ER-9", Gravite.CRITIQUE)]})
    report = run_quality_checks(w5_input, assemble_output(w5_input, output))
    statut, message = _checks(report)["Couverture des événements redoutés"]
    assert statut == STATUT_ERREUR and "ER-9" in message


def test_quality_report_flags_an_unacceptable_risk_kept_as_it_is():
    w5_input, output = _complete_plan()
    kept = output.model_copy(update={"risques": [
        output.risques[0].model_copy(update={"option_traitement": OptionTraitement.MAINTIEN}),
        output.risques[1],
    ]})
    statut, message = _checks(run_quality_checks(w5_input, kept))["Stratégie de traitement"]
    assert statut == STATUT_ERREUR and "R1" in message


def test_quality_report_flags_a_residual_risk_nobody_accepted():
    w5_input, output = _complete_plan()
    unaccepted = output.model_copy(update={"risques": [
        r.model_copy(update={"accepte_par": ""}) for r in output.risques]})
    statut, message = _checks(run_quality_checks(w5_input, unaccepted))["Risques résiduels"]
    assert statut == STATUT_ERREUR and "non accepté" in message


def test_quality_report_flags_a_reduced_risk_with_no_measure():
    w5_input, output = _complete_plan()
    stripped = output.model_copy(update={"mesures": [], "risques": [
        r.model_copy(update={"mesures_ids": []}) for r in output.risques]})
    statut, message = _checks(run_quality_checks(w5_input, stripped))["Plan de traitement"]
    assert statut == STATUT_ERREUR and "R1" in message


def test_quality_report_warns_on_a_baseline_gap_no_measure_closes():
    w5_input, output = _complete_plan()
    other_gap = _gap("BG-999")
    w5_input = w5_input.model_copy(update={"baseline_gaps": [*w5_input.baseline_gaps, other_gap]})
    statut, message = _checks(run_quality_checks(w5_input, output))["Écarts du socle traités"]
    assert statut == STATUT_AVERTISSEMENT and "BG-999" in message


def test_quality_report_warns_when_an_alternative_mode_is_left_open():
    w5_input, output = _complete_plan()
    only_retained = output.model_copy(update={"mesures": [
        output.mesures[0].model_copy(update={"modes_ids": ["SO-01"]})]})
    statut, message = _checks(run_quality_checks(w5_input, only_retained))["Modes alternatifs traités"]
    assert statut == STATUT_AVERTISSEMENT and "SO-02" in message


def test_assemble_output_rederives_the_coverage_and_the_links():
    w5_input, output = _complete_plan()
    tampered = output.model_copy(update={"couverture_er": [], "risques": [
        r.model_copy(update={"mesures_ids": ["M-42"]}) for r in output.risques]})
    final = assemble_output(w5_input, tampered)
    assert [c.evenement_redoute_id for c in final.couverture_er] == ["ER-1", "ER-3"]
    assert final.risques[0].mesures_ids == ["M-01"]
