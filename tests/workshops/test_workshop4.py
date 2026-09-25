"""Fiche de test — Atelier 4, fan-out/fan-in (conception §18).

Everything runs against the pure functions of assessment.py; no test makes a
real LLM call. The assertions sit on the deterministic parts, because that is
where the methodology is enforced: the ATT&CK check, the baseline-gap review,
the likelihood/risk-level matrix, the coherence pass, and the quality checker.
"""

from __future__ import annotations

import pytest

from ebios_rm.domain.enums import Gravite, ImpactType, NiveauRisque, VraisemblanceInitiale, Origin, CategorieImpact, Pertinence, StatutSelection
from ebios_rm.domain.essential_asset import EssentialAsset, SupportAsset
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.domain.operational_scenario import (
    STATUT_A_ANALYSER,
    STATUT_A_REFAIRE,
    STATUT_A_REVISER,
    STATUT_ANALYSE,
    STATUT_CONFIRME,
    Anomaly,
    AttackStep,
    GapConsideration,
    NewBaselineGap,
    OperationalScenario,
)
from ebios_rm.domain.risk_source import ObjectifVise, RiskSource
from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.repositories.attack_repository import AttackCatalogue, AttackTechnique
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGapForW4, Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Output
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import (
    ACTION_CANCEL,
    ACTION_RUN,
    GateDecision,
    Workshop3Output,
)
from ebios_rm.workshops.workshop4_scenarios_operationnels.assessment import (
    apply_coherence,
    build_analysis,
    build_modes,
    dossier_voies,
    modes_beyond_cap,
    number_modes,
    remove_modes,
    select_driving,
    set_driving,
    build_coherence,
    confirm,
    finalize,
    is_weak_entry,
    normalise_tactic,
    pertinent_gap_ids,
    phase_of,
    read_impact_type,
    read_likelihood,
    read_technique_id,
    risk_level,
    run_quality_checks,
    send_back,
    tactics_of_category,
    unknown_technique_ids,
    validate_atelier3,
)
from ebios_rm.workshops.workshop4_scenarios_operationnels.prompts import analysis_prompt, modes_prompt
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import (
    COHERENCE_APPLIQUEE,
    REASON_MODE_AU_DELA_DU_PLAFOND,
    REASON_MODE_DOUBLON,
    REASON_MODE_ECARTE_PAR_AUDITEUR,
    REASON_MODE_SANS_ANCRAGE,
    REASON_MODE_VOIE_INCONNUE,
    STATUT_AVERTISSEMENT,
    VOIE_ACCES_DISTANT,
    VOIE_PERSONNE_POSTE,
    VOIE_SERVICE_EXPOSE,
    VOIES,
    ModeCandidateProposal,
    CONSTAT_DOUBLON,
    CONSTAT_REVISION,
    STATUT_ERREUR,
    STATUT_OK,
    AttackStepProposal,
    CoherenceFindingProposal,
    GapConsiderationProposal,
    NewBaselineGapProposal,
    ScenarioAnalysisProposal,
    Workshop4Input,
)

GAP_ID = "BG-a1b2c3"


# --- Small, self-contained fixtures --------------------------------------

def _catalogue() -> AttackCatalogue:
    """Two real-shaped techniques, enough to exercise the checks against a
    known catalogue without touching the real 21 Mo MITRE database."""
    return AttackCatalogue(
        version="ATT&CK-Latest (sha256 test000000)",
        techniques={
            "T1078": AttackTechnique("T1078", "Valid Accounts", ("initial-access", "persistence")),
            "T1021.001": AttackTechnique("T1021.001", "Remote Desktop Protocol", ("lateral-movement",)),
            "T1486": AttackTechnique("T1486", "Data Encrypted for Impact", ("impact",)),
        },
    )


def _gap(gap_id: str = GAP_ID, *, categories=("initial_access",)) -> BaselineGapForW4:
    return BaselineGapForW4(gap_id=gap_id, weakness="Absence de MFA sur les accès distants",
                             risk_categories=list(categories))


def _w4_input(*, baseline_gaps=None, biens_supports=None) -> Workshop4Input:
    return Workshop4Input(
        organisation_nom="Clinique Test", secteur_activite="Santé",
        baseline_gaps=baseline_gaps or [_gap()],
        biens_supports=biens_supports or [
            SupportAsset(id="BS-1", nom="SIH", description="Système d'information hospitalier",
                         type_support="application", biens_essentiels_supportes=["BE-1"],
                         origin=Origin.ASSESSMENT, derived_from_fact_fields=["x"]),
        ],
    )


def _valid_proposal(**overrides) -> ScenarioAnalysisProposal:
    base = dict(
        resume="Accès via un compte valide, puis chiffrement des données.",
        attack_path=[
            AttackStepProposal(tactic="initial-access", technique_id="T1078", technique_name="Valid Accounts",
                                description="Connexion avec des identifiants valides.",
                                bien_support_id="BS-1", justification="Aucune MFA en place."),
            AttackStepProposal(tactic="impact", technique_id="T1486", technique_name="Data Encrypted for Impact",
                                description="Chiffrement des données du SIH.",
                                bien_support_id="BS-1", justification="Objectif du scénario."),
        ],
        baseline_gaps_considered=[
            GapConsiderationProposal(gap_id=GAP_ID, impact_type="increases_likelihood",
                                      impact_on_scenario="Facilite l'accès initial."),
        ],
        likelihood_revision_reason="Vecteur confirmé par le contexte.",
        revised_likelihood="V4",
    )
    base.update(overrides)
    return ScenarioAnalysisProposal(**base)


def _pending(**overrides) -> OperationalScenario:
    base = dict(
        id="SO-01", scenario_strategique_id="SS-01", source_risque_id="SR-01", objectif_vise_id="OV-01",
        gravite=Gravite.CRITIQUE, vraisemblance_initiale=VraisemblanceInitiale.V1,
    )
    base.update(overrides)
    return OperationalScenario(**base)


# --- phase_of / normalise_tactic / tactics_of_category ---------------------

def test_phase_of_maps_known_tactics():
    assert phase_of("initial-access") == "Rentrer"
    assert phase_of("impact") == "Exploiter"
    assert phase_of("reconnaissance") == "Connaître"


def test_phase_of_unknown_tactic_is_empty():
    assert phase_of("no-such-tactic") == ""


def test_normalise_tactic_folds_separators_and_case():
    assert normalise_tactic("Initial Access") == "initial-access"
    assert normalise_tactic("initial_access") == "initial-access"
    assert normalise_tactic(" Initial-Access ") == "initial-access"


def test_tactics_of_category_handles_the_split_defense_evasion():
    assert tactics_of_category("defense_evasion") == ("stealth", "defense-impairment")


def test_tactics_of_category_defaults_to_dash_form():
    assert tactics_of_category("lateral_movement") == ("lateral-movement",)


def test_pertinent_gap_ids_matches_on_tactic():
    gaps = [_gap("BG-01", categories=("initial_access",)), _gap("BG-02", categories=("impact",))]
    ids = pertinent_gap_ids(gaps, ["initial-access"])
    assert ids == ["BG-01"]


# --- unknown_technique_ids / is_weak_entry (the two originally-planned cases) --

def test_unknown_technique_ids_flags_what_the_base_never_returned():
    cited = {"T1078": [1], "T9999.999": [2]}
    result = unknown_technique_ids(cited, ["T1078", "T1486"])
    assert result == ["T9999.999"]


def test_unknown_technique_ids_empty_when_everything_matches():
    cited = {"T1078": [1]}
    assert unknown_technique_ids(cited, ["T1078"]) == []


def test_is_weak_entry_flags_empty_impact_even_on_no_impact():
    entry = GapConsiderationProposal(gap_id=GAP_ID, impact_type="no_impact", impact_on_scenario="")
    assert is_weak_entry(entry) is True


def test_is_weak_entry_accepts_a_real_sentence():
    entry = GapConsiderationProposal(gap_id=GAP_ID, impact_type="no_impact",
                                      impact_on_scenario="Sans effet : ce gap ne concerne pas cette voie d'accès.")
    assert is_weak_entry(entry) is False


# --- read_technique_id / read_likelihood / read_impact_type -----------------

def test_read_technique_id_extracts_a_single_id_with_prose():
    tid, readable = read_technique_id("T1566.001 Spearphishing Attachment")
    assert (tid, readable) == ("T1566.001", True)


def test_read_technique_id_two_ids_in_one_field_is_unreadable():
    tid, readable = read_technique_id("T1566.001 ou T1078")
    assert (tid, readable) == (None, False)


def test_read_technique_id_none_marker_reads_as_no_technique():
    assert read_technique_id("aucune") == (None, True)


def test_read_likelihood_reads_v3_with_trailing_prose():
    assert read_likelihood("V3 (très vraisemblable)") == VraisemblanceInitiale.V3


def test_read_likelihood_range_is_not_a_value():
    assert read_likelihood("V2-V3") is None


def test_read_impact_type_accepts_dash_or_underscore():
    assert read_impact_type("increases-likelihood") == ImpactType.INCREASES_LIKELIHOOD
    assert read_impact_type("increases_likelihood") == ImpactType.INCREASES_LIKELIHOOD


def test_read_impact_type_unknown_value_is_none():
    assert read_impact_type("hors sujet total") is None


# --- risk_level: the gravité x vraisemblance matrix -------------------------

def test_risk_level_none_without_a_likelihood():
    assert risk_level(Gravite.CRITIQUE, None) is None


def test_risk_level_critique_x_v4_is_critique():
    assert risk_level(Gravite.CRITIQUE, VraisemblanceInitiale.V4) == NiveauRisque.CRITIQUE


def test_risk_level_minimale_x_v1_is_faible():
    assert risk_level(Gravite.MINIMALE, VraisemblanceInitiale.V1) == NiveauRisque.FAIBLE


# --- validate_atelier3: the atelier-3 output must hold up -------------------

def _minimal_w1() -> Workshop1Output:
    from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap, ControlReference
    return Workshop1Output(
        biens_essentiels=[EssentialAsset(id="BE-1", nom="Dossier patient", description="d",
                                          nature="information", processus_metier_associes=["p"],
                                          origin=Origin.ASSESSMENT, derived_from_fact_fields=["x"])],
        evenements_redoutes=[FearedEvent(id="ER-1", description="d", bien_essentiel_id="BE-1",
                                          categorie_impact=CategorieImpact.FONCTIONNEMENT, gravite=Gravite.CRITIQUE,
                                          origin=Origin.ASSESSMENT, derived_from_fact_fields=["x"])],
        # Un écart présent : "liste vide" (déjà testable ailleurs) et "socle
        # complet sans écart" doivent rester deux cas distincts pour ce test.
        baseline_gaps_full=[BaselineGap(gap_id=GAP_ID, weakness="Absence de MFA",
                                         controls=[ControlReference(framework="ANSSI_hygiene", control_id="H-21")],
                                         risk_categories=["initial_access"])],
    )


def _minimal_w2() -> Workshop2Output:
    return Workshop2Output(
        sources_risque=[RiskSource(id="SR-01", categorie_id="c", categorie_libelle="c",
                                    nom="Groupe", statut=StatutSelection.RETENU,
                                    justification="j", derived_from_fact_fields=["x"])],
        objectifs_vises=[ObjectifVise(id="OV-01", finalite_id="f", finalite_libelle="f",
                                       description="d", biens_essentiels_vises=["BE-1"],
                                       statut=StatutSelection.RETENU, justification="j",
                                       derived_from_fact_fields=["x"])],
    )


def _scenario(**overrides) -> StrategicScenario:
    base = dict(id="SS-01", source_risque_id="SR-01", objectif_vise_id="OV-01", couple_id="CPL-01",
                resume="r", justification="j", biens_essentiels_ids=["BE-1"],
                evenements_redoutes_ids=["ER-1"], gravite=Gravite.CRITIQUE, pertinence=Pertinence.ELEVE)
    base.update(overrides)
    return StrategicScenario(**base)


def test_validate_atelier3_accepts_a_consistent_list():
    w3 = Workshop3Output(scenarios=[_scenario()], gate_decision=GateDecision(action=ACTION_RUN))
    alerts = validate_atelier3(w3, _minimal_w2(), _minimal_w1())
    assert alerts == []


def test_validate_atelier3_flags_unknown_source_risque():
    w3 = Workshop3Output(scenarios=[_scenario(source_risque_id="SR-99")], gate_decision=GateDecision(action=ACTION_RUN))
    alerts = validate_atelier3(w3, _minimal_w2(), _minimal_w1())
    assert any("SR-99" in a.probleme for a in alerts)


def test_validate_atelier3_flags_gate_not_run():
    w3 = Workshop3Output(scenarios=[_scenario()], gate_decision=GateDecision(action=ACTION_CANCEL))
    alerts = validate_atelier3(w3, _minimal_w2(), _minimal_w1())
    assert any(a.reference == "point_de_comptage" for a in alerts)


def test_validate_atelier3_flags_empty_scenario_list():
    w3 = Workshop3Output(scenarios=[], gate_decision=GateDecision(action=ACTION_RUN))
    alerts = validate_atelier3(w3, _minimal_w2(), _minimal_w1())
    assert any(a.reference == "atelier3" for a in alerts)


# --- build_analysis: one sub-agent answer -> a checked scenario ------------

def test_build_analysis_accepts_a_clean_proposal():
    analysed, ecartes = build_analysis(_valid_proposal(), _pending(), _w4_input(), _catalogue())
    assert analysed.statut == STATUT_ANALYSE
    assert analysed.revised_likelihood == VraisemblanceInitiale.V4
    assert analysed.revised_risk_level == NiveauRisque.CRITIQUE
    assert not analysed.blocking_anomalies
    assert ecartes == []


def test_build_analysis_drops_an_unknown_technique_id_keeps_the_step():
    proposal = _valid_proposal(attack_path=[
        AttackStepProposal(tactic="initial-access", technique_id="T9999.999", technique_name="Invented",
                            description="Une action réelle, un identifiant faux.",
                            bien_support_id="BS-1", justification="j"),
    ])
    analysed, _ = build_analysis(proposal, _pending(), _w4_input(), _catalogue())
    assert analysed.attack_path[0].technique_id is None
    assert analysed.attack_path[0].description  # the action itself survives
    assert any(a.code == "technique_inconnue" for a in analysed.anomalies)


def test_build_analysis_flags_tactic_inconsistent_with_the_cited_technique():
    proposal = _valid_proposal(attack_path=[
        AttackStepProposal(tactic="initial-access", technique_id="T1021.001", technique_name="Remote Desktop Protocol",
                            description="Déplacement latéral mal étiqueté.", bien_support_id="BS-1", justification="j"),
    ])
    analysed, _ = build_analysis(proposal, _pending(), _w4_input(), _catalogue())
    anomaly = next(a for a in analysed.anomalies if a.code == "tactique_incoherente")
    assert not anomaly.bloquante  # signalé, mais non bloquant


def test_build_analysis_flags_empty_step_description():
    proposal = _valid_proposal(attack_path=[
        AttackStepProposal(tactic="initial-access", technique_id="T1078", technique_name="Valid Accounts",
                            description="", bien_support_id="BS-1", justification="j"),
    ])
    analysed, _ = build_analysis(proposal, _pending(), _w4_input(), _catalogue())
    assert any(a.code == "etape_sans_description" for a in analysed.anomalies)


def test_build_analysis_flags_missing_rentrer_and_exploiter_phases():
    proposal = _valid_proposal(attack_path=[
        AttackStepProposal(tactic="lateral-movement", technique_id="T1021.001", technique_name="Remote Desktop Protocol",
                            description="Déplacement latéral seul, sans entrée ni impact.",
                            bien_support_id="BS-1", justification="j"),
    ])
    analysed, _ = build_analysis(proposal, _pending(), _w4_input(), _catalogue())
    codes = {a.code for a in analysed.anomalies}
    assert "phase_absente" in codes


def test_build_analysis_moves_an_entry_on_an_untransmitted_gap_to_ecartes():
    proposal = _valid_proposal(baseline_gaps_considered=[
        GapConsiderationProposal(gap_id="BG-inconnu", impact_type="no_impact", impact_on_scenario="x"),
    ])
    analysed, ecartes = build_analysis(proposal, _pending(), _w4_input(), _catalogue())
    assert len(ecartes) == 1
    assert ecartes[0].type == "entree_ecart"
    assert any(a.code == "ecart_inconnu" for a in analysed.anomalies)


def test_build_analysis_flags_weak_gap_entry():
    proposal = _valid_proposal(baseline_gaps_considered=[
        GapConsiderationProposal(gap_id=GAP_ID, impact_type="no_impact", impact_on_scenario=""),
    ])
    analysed, _ = build_analysis(proposal, _pending(), _w4_input(), _catalogue())
    assert any(a.code == "impact_vide" for a in analysed.anomalies)


def test_build_analysis_flags_missing_revision_reason():
    proposal = _valid_proposal(likelihood_revision_reason="")
    analysed, _ = build_analysis(proposal, _pending(), _w4_input(), _catalogue())
    assert any(a.code == "motif_revision_absent" for a in analysed.anomalies)


def test_build_analysis_flags_a_strong_likelihood_jump_non_blocking():
    # V1 -> V4 : plus d'un niveau d'écart (conception : à examiner, pas bloquant).
    proposal = _valid_proposal(revised_likelihood="V4")
    analysed, _ = build_analysis(proposal, _pending(vraisemblance_initiale=VraisemblanceInitiale.V1),
                                  _w4_input(), _catalogue())
    anomaly = next(a for a in analysed.anomalies if a.code == "revision_forte")
    assert not anomaly.bloquante


def test_build_analysis_new_gap_without_fact_anchor_is_set_aside():
    proposal = _valid_proposal(new_baseline_gap_identified=NewBaselineGapProposal(
        weakness="Un écart inventé", justification="j", derived_from_fact_fields=["champ_inexistant"]))
    analysed, ecartes = build_analysis(proposal, _pending(), _w4_input(), _catalogue())
    assert analysed.new_baseline_gap_identified is None
    assert any(e.type == "nouvel_ecart" for e in ecartes)


def test_build_analysis_increments_iterations_and_traces_the_replaced_analysis():
    previous = _pending(iterations=1, resume="Ancienne analyse.", motifs_auditeur=["Chemin trop vague."])
    analysed, ecartes = build_analysis(_valid_proposal(), previous, _w4_input(), _catalogue())
    assert analysed.iterations == 2
    assert ecartes[0].raison == "analyse_remplacee"


# --- confirm / send_back: the auditor's review ------------------------------

def test_confirm_sets_the_chosen_scenarios_to_confirme():
    output = _confirm_output([_pending(statut=STATUT_ANALYSE)])
    confirmed = confirm(output, ["SO-01"])
    assert confirmed.scenarios[0].statut == STATUT_CONFIRME


def test_send_back_requires_a_non_empty_reason():
    output = _confirm_output([_pending(statut=STATUT_ANALYSE)])
    try:
        send_back(output, ["SO-01"], "   ", STATUT_A_REVISER)
        assert False, "should have raised"
    except ValueError:
        pass


def test_send_back_voids_the_coherence_review():
    from ebios_rm.workshops.workshop4_scenarios_operationnels.models import CoherenceReview
    output = _confirm_output([_pending(statut=STATUT_ANALYSE)])
    output = output.model_copy(update={"coherence": CoherenceReview(decision="sans_constat")})
    reopened = send_back(output, ["SO-01"], "Chemin incomplet.", STATUT_A_REFAIRE)
    assert reopened.coherence is None
    assert reopened.scenarios[0].statut == STATUT_A_REFAIRE
    assert reopened.scenarios[0].motifs_auditeur == ["Chemin incomplet."]


from ebios_rm.workshops.workshop4_scenarios_operationnels.models import Workshop4Output  # noqa: E402


def _confirm_output(scenarios) -> Workshop4Output:
    return Workshop4Output(scenarios=scenarios)


# --- build_coherence / apply_coherence --------------------------------------

def test_build_coherence_keeps_a_valid_revision_finding():
    scenarios = [_pending(id="SO-01", revised_likelihood=VraisemblanceInitiale.V2),
                 _pending(id="SO-02", revised_likelihood=VraisemblanceInitiale.V2)]
    proposal = CoherenceFindingProposal(
        type=CONSTAT_REVISION, scenario_ids=["SO-01", "SO-02"],
        explication="Même vecteur, le second devrait être révisé à la hausse aussi.",
        scenario_a_reviser="SO-02", vraisemblance_proposee="V4",
    )
    findings, ecartes = build_coherence([proposal], scenarios)
    assert len(findings) == 1
    assert ecartes == []


def test_build_coherence_sets_aside_a_finding_naming_one_scenario_only():
    scenarios = [_pending(id="SO-01")]
    proposal = CoherenceFindingProposal(type=CONSTAT_DOUBLON, scenario_ids=["SO-01"], explication="x")
    findings, ecartes = build_coherence([proposal], scenarios)
    assert findings == []
    assert len(ecartes) == 1


def test_build_coherence_revision_proposing_the_same_value_is_invalid():
    scenarios = [_pending(id="SO-01", revised_likelihood=VraisemblanceInitiale.V2),
                 _pending(id="SO-02", revised_likelihood=VraisemblanceInitiale.V2)]
    proposal = CoherenceFindingProposal(
        type=CONSTAT_REVISION, scenario_ids=["SO-01", "SO-02"], explication="x",
        scenario_a_reviser="SO-02", vraisemblance_proposee="V2",  # deja V2 : rien a reviser
    )
    findings, ecartes = build_coherence([proposal], scenarios)
    assert findings == []
    assert len(ecartes) == 1


def test_apply_coherence_updates_the_named_scenario_only():
    from ebios_rm.workshops.workshop4_scenarios_operationnels.models import CoherenceFinding, CoherenceReview
    scenarios = [_pending(id="SO-01", gravite=Gravite.CRITIQUE, revised_likelihood=VraisemblanceInitiale.V2),
                 _pending(id="SO-02", gravite=Gravite.CRITIQUE, revised_likelihood=VraisemblanceInitiale.V2)]
    review = CoherenceReview(constats=[CoherenceFinding(
        type=CONSTAT_REVISION, scenario_ids=["SO-01", "SO-02"], explication="x",
        scenario_a_reviser="SO-02", vraisemblance_proposee="V4")])
    output = Workshop4Output(scenarios=scenarios, coherence=review)
    applied = apply_coherence(output)
    by_id = {s.id: s for s in applied.scenarios}
    assert by_id["SO-02"].revised_likelihood == VraisemblanceInitiale.V4
    assert by_id["SO-01"].revised_likelihood == VraisemblanceInitiale.V2  # non nomme, inchange
    assert applied.coherence.decision == COHERENCE_APPLIQUEE


# --- finalize / run_quality_checks ------------------------------------------

def test_finalize_recomputes_risk_level_after_a_manual_edit():
    scenario = _pending(statut=STATUT_CONFIRME, revised_likelihood=VraisemblanceInitiale.V1,
                         attack_path=[AttackStep(tactic="initial-access", technique_id="T1078",
                                                  description="d")])
    output = Workshop4Output(scenarios=[scenario])
    final = finalize(output, _catalogue())
    # gravité CRITIQUE x V1 -> Moyen ; verifie que le niveau est bien recalcule
    assert final.scenarios[0].revised_risk_level == risk_level(Gravite.CRITIQUE, VraisemblanceInitiale.V1)
    assert final.scenarios[0].attack_path[0].technique_name == "Valid Accounts"


def test_run_quality_checks_reports_valid_on_a_clean_output():
    scenario = _pending(
        statut=STATUT_CONFIRME, revised_likelihood=VraisemblanceInitiale.V4,
        revised_risk_level=NiveauRisque.CRITIQUE, likelihood_revision_reason="Motif réel.",
        attack_path=[
            AttackStep(phase="Rentrer", tactic="initial-access", technique_id="T1078", description="d"),
            AttackStep(phase="Exploiter", tactic="impact", technique_id="T1486", description="d"),
        ],
        baseline_gaps_considered=[GapConsideration(gap_id=GAP_ID, impact_type=ImpactType.INCREASES_LIKELIHOOD,
                                                     impact_on_scenario="Facilite l'accès.")],
    )
    w4_input = _w4_input()
    w4_input = w4_input.model_copy(update={"scenarios": [_ss_for(scenario)]})
    output = Workshop4Output(scenarios=[scenario], coherence=None)
    report = run_quality_checks(w4_input, output, _catalogue())
    statuses = {c.controle: c.statut for c in report.checks}
    assert statuses["Techniques ATT&CK"] == STATUT_OK
    assert statuses["Vraisemblance et niveau de risque"] == STATUT_OK


def test_run_quality_checks_flags_a_scenario_still_pending():
    scenario = _pending(statut=STATUT_A_ANALYSER)
    w4_input = _w4_input().model_copy(update={"scenarios": [_ss_for(scenario)]})
    output = Workshop4Output(scenarios=[scenario])
    report = run_quality_checks(w4_input, output, _catalogue())
    review_check = next(c for c in report.checks if c.controle == "Revue de l'auditeur")
    assert review_check.statut == STATUT_ERREUR


def _ss_for(scenario: OperationalScenario) -> StrategicScenario:
    return StrategicScenario(
        id=scenario.scenario_strategique_id, source_risque_id=scenario.source_risque_id,
        objectif_vise_id=scenario.objectif_vise_id, couple_id="CPL-01", resume="r", justification="j",
        gravite=scenario.gravite, vraisemblance_initiale=scenario.vraisemblance_initiale,
    )


# --- Étape 22a : les modes opératoires d'un scénario stratégique (§18) -------
# La méthode ne fixe aucun nombre : un scénario stratégique porte autant de modes
# opératoires que le dossier offre de voies d'entrée, tous sont développés, et le
# plus vraisemblable porte le risque.

def _candidate(**overrides) -> ModeCandidateProposal:
    base = dict(
        libelle="Par le VPN sans MFA des portables",
        voie=VOIE_ACCES_DISTANT,
        point_entree="BS-1",
        justification="Le dossier décrit un VPN sans authentification multifacteur.",
        derived_from_fact_fields=["acces_distant_moyens"],
    )
    base.update(overrides)
    return ModeCandidateProposal(**base)


def _enumeration_input() -> Workshop4Input:
    return _w4_input().model_copy(update={
        "contexte": {"acces_distant_moyens": "VPN sans MFA", "exposition_internet": "portail public"},
    })


def _mode(id_: str, likelihood, **overrides) -> OperationalScenario:
    base = dict(id=id_, scenario_strategique_id="SS-01", source_risque_id="SR-01",
                objectif_vise_id="OV-01", gravite=Gravite.CRITIQUE,
                vraisemblance_initiale=VraisemblanceInitiale.V2, statut=STATUT_ANALYSE,
                revised_likelihood=likelihood, variante=f"mode {id_}", voie=VOIE_ACCES_DISTANT)
    base.update(overrides)
    return OperationalScenario(**base)


def test_a_mode_without_a_cited_context_field_is_set_aside():
    kept, ecartes = build_modes(_scenario(), [_candidate(derived_from_fact_fields=["invente"])],
                                _enumeration_input())
    assert kept == []
    assert ecartes[0].raison == REASON_MODE_SANS_ANCRAGE and ecartes[0].raison_label


def test_a_mode_on_an_unknown_voie_is_set_aside():
    kept, ecartes = build_modes(_scenario(), [_candidate(voie="par magie")], _enumeration_input())
    assert kept == [] and ecartes[0].raison == REASON_MODE_VOIE_INCONNUE


def test_two_modes_entering_the_same_way_at_the_same_place_are_one():
    kept, ecartes = build_modes(
        _scenario(),
        [_candidate(),
         _candidate(libelle="Encore le VPN"),
         _candidate(libelle="Doublon assume", doublon_de="Par le VPN sans MFA des portables")],
        _enumeration_input())
    assert [m.variante for m in kept] == ["Par le VPN sans MFA des portables"]
    assert [e.raison for e in ecartes] == [REASON_MODE_DOUBLON, REASON_MODE_DOUBLON]


def test_several_ways_in_give_several_modes_to_develop():
    kept, ecartes = build_modes(
        _scenario(),
        [_candidate(),
         _candidate(libelle="Par le portail public", voie=VOIE_SERVICE_EXPOSE, point_entree="portail",
                    derived_from_fact_fields=["exposition_internet"]),
         _candidate(libelle="Par un poste piege", voie=VOIE_PERSONNE_POSTE, point_entree="postes",
                    derived_from_fact_fields=[GAP_ID])],
        _enumeration_input())
    assert len(kept) == 3 and not ecartes
    assert {m.voie for m in kept} == {VOIE_ACCES_DISTANT, VOIE_SERVICE_EXPOSE, VOIE_PERSONNE_POSTE}
    assert all(m.statut == STATUT_A_ANALYSER and m.gravite is Gravite.CRITIQUE for m in kept)
    assert number_modes(kept, start=3)[0].id == "SO-03"      # numbering continues across scenarios


def test_dossier_voies_reads_the_context_not_the_model():
    assert set(dossier_voies(_enumeration_input())) == {VOIE_ACCES_DISTANT, VOIE_SERVICE_EXPOSE}


def test_the_cap_is_a_guard_and_what_it_drops_keeps_its_reason():
    modes = number_modes([
        OperationalScenario(id="", scenario_strategique_id="SS-01", source_risque_id="SR-01",
                            objectif_vise_id="OV-01", variante=f"mode {i}", voie=VOIE_ACCES_DISTANT)
        for i in range(8)
    ])
    output = Workshop4Output(scenarios=modes)
    assert modes_beyond_cap(output, 6) == ["SO-07", "SO-08"]

    trimmed = remove_modes(output, ["SO-07", "SO-08"], REASON_MODE_AU_DELA_DU_PLAFOND, "plafond")
    assert [s.id for s in trimmed.scenarios] == [f"SO-{n:02d}" for n in range(1, 7)]
    assert {e.raison for e in trimmed.elements_ecartes} == {REASON_MODE_AU_DELA_DU_PLAFOND}
    assert all(e.raison_label for e in trimmed.elements_ecartes)


def test_a_developed_mode_is_never_dropped_that_way():
    output = Workshop4Output(scenarios=[_pending(statut=STATUT_ANALYSE)])
    assert remove_modes(output, ["SO-01"], REASON_MODE_ECARTE_PAR_AUDITEUR, "x").scenarios


# --- Étape 29a : le mode retenu porte le risque ------------------------------

def test_the_most_likely_mode_drives_the_risk():
    modes = select_driving([_mode("SO-01", VraisemblanceInitiale.V2),
                            _mode("SO-02", VraisemblanceInitiale.V4),
                            _mode("SO-03", VraisemblanceInitiale.V3)])
    assert [m.id for m in modes if m.retenu] == ["SO-02"]
    assert "V4" in next(m for m in modes if m.retenu).motif_selection
    assert "SO-02" in next(m for m in modes if m.id == "SO-01").motif_selection


def test_a_tie_is_broken_on_evidence_not_on_order():
    exploited = [GapConsideration(gap_id=GAP_ID, impact_type=ImpactType.INCREASES_LIKELIHOOD,
                                  impact_on_scenario="Facilite l'entrée.")]
    modes = select_driving([
        _mode("SO-01", VraisemblanceInitiale.V3, anomalies=[Anomaly(code="x", message="m")]),
        _mode("SO-02", VraisemblanceInitiale.V3, baseline_gaps_considered=exploited),
    ])
    assert [m.id for m in modes if m.retenu] == ["SO-02"]


def test_a_mode_not_developed_yet_never_drives():
    modes = select_driving([_mode("SO-01", None, statut=STATUT_A_ANALYSER),
                            _mode("SO-02", VraisemblanceInitiale.V1)])
    assert [m.id for m in modes if m.retenu] == ["SO-02"]


def test_the_auditor_choice_outranks_the_computation():
    modes = select_driving([_mode("SO-01", VraisemblanceInitiale.V2),
                            _mode("SO-02", VraisemblanceInitiale.V4)])
    output = set_driving(Workshop4Output(scenarios=modes), "SO-01", "Le VPN est le chemin réel ici.")
    assert [m.id for m in output.scenarios if m.retenu] == ["SO-01"]

    kept = select_driving(output.scenarios)          # recomputing must not undo it
    assert [m.id for m in kept if m.retenu] == ["SO-01"]
    assert "auditeur" in next(m for m in kept if m.id == "SO-01").motif_selection


def test_designating_a_mode_needs_a_reason_and_a_real_id():
    output = Workshop4Output(scenarios=[_mode("SO-01", VraisemblanceInitiale.V2)])
    with pytest.raises(ValueError):
        set_driving(output, "SO-01", "   ")
    with pytest.raises(ValueError):
        set_driving(output, "SO-99", "motif valable")


def test_quality_checks_cover_the_modes_and_the_selection():
    driving = _mode("SO-01", VraisemblanceInitiale.V3, statut=STATUT_CONFIRME,
                    attack_path=[AttackStep(tactic="initial-access", phase="Rentrer", description="entree")],
                    likelihood_revision_reason="motif",
                    revised_risk_level=risk_level(Gravite.CRITIQUE, VraisemblanceInitiale.V3))
    w4_input = _enumeration_input().model_copy(update={"scenarios": [_ss_for(driving)]})
    output = Workshop4Output(scenarios=select_driving([driving]))
    report = run_quality_checks(w4_input, output, _catalogue())
    statuses = {c.controle: c.statut for c in report.checks}
    assert statuses["Couverture"] == STATUT_OK                            # one mode, and it drives
    assert statuses["Sélection du mode retenu"] == STATUT_OK
    assert statuses["Voies d'entrée explorées"] == STATUT_AVERTISSEMENT   # nobody took the exposed service
    assert statuses["Écarts du socle exploités"] == STATUT_AVERTISSEMENT  # the gap carries no mode


def test_quality_checks_flag_a_scenario_with_no_retained_mode():
    mode = _mode("SO-01", VraisemblanceInitiale.V3, statut=STATUT_CONFIRME, retenu=False)
    w4_input = _enumeration_input().model_copy(update={"scenarios": [_ss_for(mode)]})
    report = run_quality_checks(w4_input, Workshop4Output(scenarios=[mode]), _catalogue())
    coverage = next(c for c in report.checks if c.controle == "Couverture")
    assert coverage.statut == STATUT_ERREUR and "retenu" in coverage.message


# --- The prompts say what the code enforces ---------------------------------

def test_the_enumeration_prompt_asks_for_no_count():
    w4_input = _enumeration_input().model_copy(update={"scenarios": [_scenario()]})
    prompt = modes_prompt(w4_input, _scenario())
    assert "autant qu'il y en a dans le" in prompt
    assert all(voie in prompt for voie in VOIES)
    assert "T1078" not in prompt                       # no ATT&CK catalogue at this stage


def test_the_analysis_prompt_names_the_mode_and_forbids_the_others():
    w4_input = _enumeration_input().model_copy(update={"scenarios": [_scenario()]})
    pending = _pending(variante="Par le VPN sans MFA", voie=VOIE_ACCES_DISTANT,
                       variante_justification="BS-1 — VPN sans MFA (acces_distant_moyens)")
    prompt = analysis_prompt(w4_input, pending, _catalogue())
    assert "<mode_operatoire>" in prompt and "Par le VPN sans MFA" in prompt
    assert "ne les décris pas" in prompt
