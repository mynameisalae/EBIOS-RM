"""Fiche de test — Atelier 3, scénarios stratégiques et point de comptage (conception §17).

Everything runs against fakes; no test makes a real LLM call. The assertions sit
on the deterministic parts, because that is where the methodology is enforced: the
input contract, the scenario filter, the ratings carried from the earlier ateliers,
the critique pass, the count gate and its thresholds, and the quality checker.
"""

from __future__ import annotations

import pytest
from fakes import FakeWorkshop3Runner, ScriptedHuman

from ebios_rm.domain.enums import (
    CategorieImpact,
    Gravite,
    Origin,
    Pertinence,
    StatutSelection,
    VraisemblanceInitiale,
)
from ebios_rm.domain.essential_asset import EssentialAsset, SupportAsset
from ebios_rm.domain.fact import Fact
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.domain.risk_source import CoupleSROV, ObjectifVise, RiskSource
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.services.cost_estimation_service import estimate_cost_and_time
from ebios_rm.workshops.workshop1_cadrage.models import (
    BaselineGap,
    ControlReference,
    UnverifiedControl,
    Workshop1Output,
)
from ebios_rm.workshops.workshop2_sources_risque.models import (
    ElementEcarte as W2ElementEcarte,
)
from ebios_rm.workshops.workshop2_sources_risque.models import (
    Workshop2Output,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.assessment import (
    apply_critique,
    build_scenarios,
    choose_subset,
    merge_scenarios,
    run_quality_checks,
    validate_atelier2,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import (
    REASON_COUPLE_INCONNU,
    REASON_DOUBLON,
    REASON_FUSIONNE,
    REASON_HORS_SOUS_ENSEMBLE,
    REASON_NON_TRAITE,
    REASON_PARTIE_PRENANTE_INCONNUE,
    REASON_QUASI_DOUBLON,
    REASON_SANS_ANCRAGE_CONTEXTE,
    REASON_SANS_JUSTIFICATION,
    STATUT_ERREUR,
    CritiqueVerdict,
    ScenarioProposal,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.questions import (
    ask_session_questions,
    session_questions,
)
from ebios_rm.workshops.workshop3_scenarios_strategiques.workshop import (
    Atelier2DataError,
    build_workshop3_input,
    gate_for,
    run_workshop3,
)

GAP_WEAKNESS = "Pas de MFA sur les accès distants VPN"
ECARTE_LIBELLE = "Serveur de sauvegarde"


def _mission_context() -> MissionContext:
    facts = [
        Fact.declaration("activites_description", "Clinique privée, 200 lits."),
        Fact.declaration("perimetre_inclus", "SI hospitalier et portail patient"),
        Fact.declaration("processus_metier_critiques", "Prise en charge des patients"),
        Fact.declaration("interconnexions_tiers", "Liaison de télémaintenance avec l'éditeur du SIH"),
        Fact.declaration("fournisseurs_tiers_critiques", "Hébergeur HDS, éditeur du SIH"),
        Fact.declaration("exposition_internet", "Portail de rendez-vous"),
        # Not in CONTEXT_FIELDS: must not reach atelier 3.
        Fact.declaration("politique_mots_de_passe", "8 caractères, pas de rotation"),
    ]
    return MissionContext(
        organisation_nom="Clinique Test", secteur_activite="Santé",
        applicable_frameworks=["ANSSI_hygiene"], facts=facts,
    )


def _w1_output() -> Workshop1Output:
    return Workshop1Output(
        biens_essentiels=[
            EssentialAsset(
                id="BE-1", nom="Dossier patient", description="Données de santé",
                nature="information", processus_metier_associes=["Prise en charge des patients"],
                origin=Origin.ASSESSMENT, derived_from_fact_fields=["processus_metier_critiques"],
            ),
            EssentialAsset(
                id="BE-2", nom="Planning opératoire", description="Programmation des blocs",
                nature="processus", processus_metier_associes=["Bloc opératoire"],
                origin=Origin.ASSESSMENT, derived_from_fact_fields=["processus_metier_critiques"],
            ),
        ],
        biens_supports=[
            SupportAsset(
                id="BS-1", nom="SIH", description="Système d'information hospitalier",
                type_support="application", biens_essentiels_supportes=["BE-1", "BE-2"],
                origin=Origin.ASSESSMENT, derived_from_fact_fields=["systeme_information_resume"],
            )
        ],
        evenements_redoutes=[
            FearedEvent(
                id="ER-1", description="Indisponibilité du dossier patient", bien_essentiel_id="BE-1",
                categorie_impact=CategorieImpact.FONCTIONNEMENT, gravite=Gravite.CRITIQUE,
                origin=Origin.ASSESSMENT, derived_from_fact_fields=["impact_arret"],
            ),
            FearedEvent(
                id="ER-2", description="Divulgation du planning", bien_essentiel_id="BE-2",
                categorie_impact=CategorieImpact.IMAGE, gravite=Gravite.SIGNIFICATIVE,
                origin=Origin.ASSESSMENT, derived_from_fact_fields=["impact_divulgation"],
            ),
        ],
        baseline_gaps_full=[
            BaselineGap(
                gap_id="BG-deadbeef", weakness=GAP_WEAKNESS,
                controls=[ControlReference(framework="ANSSI_hygiene", control_id="ANSSI-H-21")],
                risk_categories=["acces_distant"],
            )
        ],
        unverified_controls=[UnverifiedControl(control_id="ANSSI-H-01", framework="ANSSI_hygiene")],
        human_edits=[{"champ": "gravite", "motif": "corrigé par l'auditeur"}],
    )


def _couple(couple_id: str, sr: str, ov: str, assets: list[str], *,
            pertinence=Pertinence.ELEVE, vraisemblance=VraisemblanceInitiale.V3) -> CoupleSROV:
    return CoupleSROV(
        id=couple_id, source_risque_id=sr, objectif_vise_id=ov,
        biens_essentiels_ids=assets, valeurs_metier=["Prise en charge des patients"],
        biens_supports_associes=["BS-1"], motivation=4, ressources=3, activite=4,
        pertinence=pertinence, vraisemblance_initiale=vraisemblance,
        statut=StatutSelection.RETENU, justification="Cohérent pour cette clinique.",
    )


def _w2_output(*, broken_reference: bool = False) -> Workshop2Output:
    return Workshop2Output(
        sources_risque=[
            RiskSource(id="SR-01", categorie_id="crime_organise", categorie_libelle="Cybercriminel organisé",
                       nom="Groupe cybercriminel", motivation="Monnayer l'arrêt de l'activité",
                       statut=StatutSelection.RETENU, justification="Secteur ciblé.",
                       derived_from_fact_fields=["exposition_internet"]),
            RiskSource(id="SR-02", categorie_id="concurrent", categorie_libelle="Concurrent",
                       nom="Concurrent régional", motivation="Capter des patients",
                       statut=StatutSelection.RETENU, justification="Concurrence directe.",
                       derived_from_fact_fields=["exposition_internet"]),
            # Retained by atelier 2 but used by no couple: must not travel to atelier 3.
            RiskSource(id="SR-03", categorie_id="amateur", categorie_libelle="Amateur",
                       nom="Opportuniste isolé", statut=StatutSelection.SECONDAIRE,
                       justification="Surface exposée.", derived_from_fact_fields=["exposition_internet"]),
        ],
        objectifs_vises=[
            ObjectifVise(id="OV-01", finalite_id="lucratif", finalite_libelle="Gain financier",
                         description="Obtenir une rançon en bloquant la prise en charge",
                         biens_essentiels_vises=["BE-1"], statut=StatutSelection.RETENU,
                         justification="Dépendance forte.", derived_from_fact_fields=["exposition_internet"]),
            ObjectifVise(id="OV-02", finalite_id="espionnage", finalite_libelle="Espionnage",
                         description="Obtenir le planning opératoire",
                         biens_essentiels_vises=["BE-2"], statut=StatutSelection.RETENU,
                         justification="Avantage commercial.", derived_from_fact_fields=["exposition_internet"]),
        ],
        couples=[
            _couple("CPL-01", "SR-99" if broken_reference else "SR-01", "OV-01", ["BE-1"]),
            _couple("CPL-02", "SR-02", "OV-02", ["BE-2"],
                    pertinence=Pertinence.MOYEN, vraisemblance=VraisemblanceInitiale.V2),
        ],
        couples_secondaires=[_couple("CPL-03", "SR-03", "OV-01", ["BE-1"])],
        elements_ecartes=[W2ElementEcarte(type="source_risque", reference="serveur",
                                          libelle=ECARTE_LIBELLE, raison="pas_un_acteur")],
        human_edits=[{"champ": "pertinence", "motif": "corrigé par l'auditeur"}],
    )


def _input(**kwargs):
    return build_workshop3_input(_mission_context(), _w1_output(), _w2_output(**kwargs))


# --- The input contract (§17) -----------------------------------------------

def test_atelier3_reads_the_approved_result_not_the_history():
    """No baseline gaps, no atelier 2 écartés, no human edits, no secondary couples."""
    payload = _input().model_dump_json()
    assert GAP_WEAKNESS not in payload and "ANSSI-H-21" not in payload
    assert ECARTE_LIBELLE not in payload
    assert "corrigé par l'auditeur" not in payload
    assert "CPL-03" not in payload  # atelier 2 kept it in reserve, not in the study


def test_input_carries_the_couples_with_both_their_ends():
    w3_input = _input()
    assert [c.id for c in w3_input.couples] == ["CPL-01", "CPL-02"]
    assert {s.id for s in w3_input.sources_risque} == {"SR-01", "SR-02"}  # SR-03 is used by no couple
    assert {o.id for o in w3_input.objectifs_vises} == {"OV-01", "OV-02"}
    assert w3_input.contexte["interconnexions_tiers"]
    assert "politique_mots_de_passe" not in w3_input.contexte


# --- Étape 0: atelier 2 is validated, never silently repaired ----------------

def test_invalid_atelier2_reference_alerts_and_blocks():
    w3_input = _input(broken_reference=True)
    assert any("SR-99" in a.probleme for a in w3_input.alertes_atelier2)
    with pytest.raises(Atelier2DataError):
        run_workshop3(w3_input, FakeWorkshop3Runner())


def test_an_asset_with_no_feared_event_is_a_warning_not_a_block():
    w1 = _w1_output()
    w1.evenements_redoutes = [e for e in w1.evenements_redoutes if e.id != "ER-2"]
    alerts = validate_atelier2(_w2_output(), w1)
    assert alerts and all(not a.bloquant for a in alerts)
    assert "BE-2" in alerts[0].probleme


# --- The scenario filter ----------------------------------------------------

def _proposal(**kwargs) -> ScenarioProposal:
    defaults = dict(
        couple_id="CPL-01", resume="Le groupe entre par la télémaintenance et bloque le SIH.",
        parties_prenantes=["éditeur du SIH"], justification="Liaison permanente.",
        derived_from_fact_fields=["interconnexions_tiers"],
    )
    return ScenarioProposal(**{**defaults, **kwargs})


def test_every_rejected_scenario_keeps_its_reason():
    w3_input = _input()
    scenarios, discarded = build_scenarios(
        [
            _proposal(),
            _proposal(couple_id="CPL-99"),                       # couple that does not exist
            _proposal(couple_id="CPL-02", justification="  "),   # nothing argued
            _proposal(couple_id="CPL-02", derived_from_fact_fields=["inventé"]),
            _proposal(couple_id="CPL-02", parties_prenantes=["Consortium Zephyr"]),
            _proposal(),                                         # second one on CPL-01
        ],
        w3_input,
    )
    assert [s.couple_id for s in scenarios] == ["CPL-01"]
    assert [d.raison for d in discarded] == [
        REASON_COUPLE_INCONNU, REASON_SANS_JUSTIFICATION, REASON_SANS_ANCRAGE_CONTEXTE,
        REASON_PARTIE_PRENANTE_INCONNUE, REASON_DOUBLON,
    ]
    assert all(d.raison_label for d in discarded)  # the auditor reads a sentence, not a code


def test_a_stakeholder_is_kept_when_the_dossier_words_it_differently():
    """« SIH (éditeur) » and « l'éditeur du SIH » are the same party; rejecting the
    second would throw away a real route over wording."""
    scenarios, _ = build_scenarios([_proposal(parties_prenantes=["SIH (éditeur)"])], _input())
    assert scenarios[0].parties_prenantes == ["SIH (éditeur)"]


def test_a_direct_attack_needs_no_stakeholder():
    scenarios, discarded = build_scenarios([_proposal(parties_prenantes=[])], _input())
    assert scenarios and not discarded


def test_gravite_and_ratings_come_from_the_earlier_ateliers():
    """Atelier 3 tells the route; it never re-rates the consequence (§17)."""
    scenarios, _ = build_scenarios([_proposal(), _proposal(couple_id="CPL-02")], _input())
    by_couple = {s.couple_id: s for s in scenarios}
    assert by_couple["CPL-01"].gravite is Gravite.CRITIQUE       # from ER-1 on BE-1
    assert by_couple["CPL-02"].gravite is Gravite.SIGNIFICATIVE  # from ER-2 on BE-2
    assert by_couple["CPL-01"].pertinence is Pertinence.ELEVE
    assert by_couple["CPL-01"].vraisemblance_initiale is VraisemblanceInitiale.V3
    assert by_couple["CPL-01"].vraisemblance_pertinence == "Élevé / V3"
    assert by_couple["CPL-01"].evenements_redoutes_ids == ["ER-1"]


def test_scenarios_are_numbered_worst_first():
    scenarios, _ = build_scenarios([_proposal(couple_id="CPL-02"), _proposal()], _input())
    assert [s.id for s in scenarios] == ["SS-01", "SS-02"]
    assert scenarios[0].gravite is Gravite.CRITIQUE  # SS-01 is what hurts most


# --- Passe 2: the critique folds near-duplicates ----------------------------

def test_critique_folds_a_near_duplicate_and_keeps_its_reason():
    scenarios, _ = build_scenarios([_proposal(), _proposal(couple_id="CPL-02")], _input())
    kept, discarded = apply_critique(scenarios, [
        CritiqueVerdict(scenario_id="SS-02", doublon_de="SS-01", raison="Même chemin, même finalité."),
    ])
    assert [s.id for s in kept] == ["SS-01"]
    assert discarded[0].raison == REASON_QUASI_DOUBLON
    assert "SS-01" in discarded[0].detail and "Même chemin" in discarded[0].detail


def test_a_pruning_verdict_without_a_reason_is_refused():
    """« quasi-doublon » with no argument is the model shortening its own output."""
    scenarios, _ = build_scenarios([_proposal(), _proposal(couple_id="CPL-02")], _input())
    kept, discarded = apply_critique(
        scenarios, [CritiqueVerdict(scenario_id="SS-02", doublon_de="SS-01", raison="")]
    )
    assert len(kept) == 2 and not discarded


def test_a_chain_of_verdicts_cannot_empty_the_list():
    scenarios, _ = build_scenarios([_proposal(), _proposal(couple_id="CPL-02")], _input())
    kept, _ = apply_critique(scenarios, [
        CritiqueVerdict(scenario_id="SS-01", doublon_de="SS-02", raison="a"),
        CritiqueVerdict(scenario_id="SS-02", doublon_de="SS-01", raison="b"),
    ])
    assert len(kept) == 1


# --- The count gate (§17 steps 19-21) ---------------------------------------

def test_scenario_count_thresholds():
    """The fiche de test of §17, verbatim."""
    assert list(estimate_cost_and_time(9).options) == [
        "run_anyway", "merge", "choose_subset", "cancel"]
    assert list(estimate_cost_and_time(14).options) == ["merge", "choose_subset", "cancel"]
    assert "run_anyway" not in estimate_cost_and_time(14).options
    assert list(estimate_cost_and_time(6).options) == ["run", "cancel"]


def test_the_estimate_scales_with_the_count():
    assert estimate_cost_and_time(4).llm_calls == 4
    assert estimate_cost_and_time(0).input_tokens == 0
    assert estimate_cost_and_time(3).seconds > estimate_cost_and_time(2).seconds


def test_the_gate_is_a_validation_point_even_below_the_soft_limit():
    """§17 offers [Oui][Annuler] at N<=6: running is the likely answer, not the automatic one."""
    scenarios, _ = build_scenarios([_proposal()], _input())
    gate = gate_for(scenarios)
    assert gate.action == ""  # nobody has ruled yet
    assert gate.options_offertes == ["run", "cancel"]


def test_merging_requires_a_justification_and_keeps_the_worst_gravite():
    scenarios, _ = build_scenarios([_proposal(), _proposal(couple_id="CPL-02")], _input())
    with pytest.raises(ValueError):
        merge_scenarios(scenarios, ["SS-01", "SS-02"], "  ")

    merged, discarded = merge_scenarios(scenarios, ["SS-02", "SS-01"], "Même acteur, même entrée.")
    assert len(merged) == 1
    survivor = merged[0]
    assert survivor.gravite is Gravite.CRITIQUE                     # worst of the two
    assert set(survivor.biens_essentiels_ids) == {"BE-1", "BE-2"}   # both stakes kept
    assert {"SS-01", "SS-02"} <= set(survivor.issu_de)
    assert discarded[0].raison == REASON_FUSIONNE


def test_choosing_a_subset_keeps_only_the_named_ones():
    scenarios, _ = build_scenarios([_proposal(), _proposal(couple_id="CPL-02")], _input())
    kept, discarded = choose_subset(scenarios, ["SS-01"], "Priorité au bloc opératoire.")
    assert [s.couple_id for s in kept] == ["CPL-01"]
    assert discarded[0].raison == REASON_HORS_SOUS_ENSEMBLE
    with pytest.raises(ValueError):
        choose_subset(scenarios, ["SS-01"], "")


def test_a_reduced_list_is_re_evaluated_against_the_same_thresholds():
    """§17 step 21: merge/subset re-enter the same gate, they do not skip it."""
    many = [_proposal(couple_id="CPL-01"), _proposal(couple_id="CPL-02")]
    scenarios, _ = build_scenarios(many, _input())
    assert gate_for(scenarios).n == 2
    kept, _ = choose_subset(scenarios, ["SS-01"], "Réduction assumée.")
    assert gate_for(kept, n_initial=2).n == 1
    assert gate_for(kept, n_initial=2).n_initial == 2


# --- The quality checker ----------------------------------------------------

def test_quality_report_flags_a_gate_decision_about_another_list():
    w3_input = _input()
    scenarios, _ = build_scenarios([_proposal()], w3_input)
    stale = gate_for(scenarios).model_copy(update={"n": 7})
    report = run_quality_checks(w3_input, scenarios, stale)
    assert report.statut == STATUT_ERREUR
    assert any("décision porte sur" in c.message for c in report.erreurs)


def test_quality_report_flags_an_empty_list():
    w3_input = _input()
    report = run_quality_checks(w3_input, [], gate_for([]))
    assert any("aucun scénario" in c.message for c in report.erreurs)


def test_quality_report_warns_on_a_couple_left_without_a_scenario():
    w3_input = _input()
    scenarios, _ = build_scenarios([_proposal()], w3_input)
    report = run_quality_checks(w3_input, scenarios, gate_for(scenarios))
    assert any("CPL-02" in c.message for c in report.avertissements)


# --- End to end, with the fake runner ---------------------------------------

def test_end_to_end_keeps_every_discarded_element_with_its_reason():
    runner = FakeWorkshop3Runner()
    output = run_workshop3(_input(), runner)

    assert runner.calls == ["scenarios", "critique"]
    assert [s.couple_id for s in output.scenarios] == ["CPL-01"]
    assert {d.raison for d in output.elements_ecartes} == {
        REASON_SANS_ANCRAGE_CONTEXTE, REASON_COUPLE_INCONNU, REASON_PARTIE_PRENANTE_INCONNUE,
    }
    assert output.gate_decision.n == 1 and output.gate_decision.action == ""  # the auditor rules
    assert output.quality_report.statut != STATUT_ERREUR


def test_revision_notes_reach_the_runner():
    runner = FakeWorkshop3Runner()
    run_workshop3(_input(), runner, ["Trop de scénarios sur le même acteur"])
    assert runner.revision_notes_seen == ["Trop de scénarios sur le même acteur"]


def test_human_edits_survive_a_redo():
    previous = run_workshop3(_input(), FakeWorkshop3Runner())
    previous.human_edits.append({"path": "scenarios.0.resume", "justification": "reformulé"})
    redone = run_workshop3(_input(), FakeWorkshop3Runner(), None, previous)
    assert redone.human_edits == previous.human_edits


# --- The ecosystem session and the auditor's couple choice ------------------

def test_the_session_only_asks_what_the_ecosystem_context_does_not_answer():
    asked = {q.field_name for q in session_questions(_input())}
    assert "sous_traitants_donnees" in asked        # nothing in the dossier covers it
    assert "interconnexions_tiers" not in asked     # already answered
    assert all(not q.blocking for q in session_questions(_input()))  # none may block


def test_a_session_answer_becomes_a_declared_fact_and_a_skip_is_not_re_asked():
    human = ScriptedHuman(
        answers={"sous_traitants_donnees": "Hébergeur HDS pour les sauvegardes"},
        skips={"clauses_securite_contrats": "À demander au service juridique"},
    )
    enriched = ask_session_questions(_input(), human)

    assert enriched.contexte["sous_traitants_donnees"].startswith("Hébergeur")
    answered = next(f for f in enriched.faits_contexte if f.field_name == "sous_traitants_donnees")
    assert answered.origin is Origin.DECLARATION and answered.question
    still_asked = {q.field_name for q in session_questions(enriched)}
    assert "sous_traitants_donnees" not in still_asked
    assert "clauses_securite_contrats" not in still_asked  # skipped, with its reason


def test_a_couple_the_agent_never_answered_is_recorded_not_just_counted():
    """Everything that does not make it keeps its reason — silence included (§19)."""

    class SilentRunner:
        def propose_scenarios(self, w3_input, revision_notes=None):
            return []

        def critique_scenarios(self, w3_input, scenarios):
            return []

    output = run_workshop3(_input(), SilentRunner())

    assert output.scenarios == []
    assert {e.reference for e in output.elements_ecartes} == {"CPL-01", "CPL-02"}
    assert all(e.raison == REASON_NON_TRAITE for e in output.elements_ecartes)
    assert all(e.raison_label for e in output.elements_ecartes)
