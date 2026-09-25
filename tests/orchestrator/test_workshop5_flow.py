"""Atelier 5 driven end to end, without a terminal and without an LLM (conception §19).

What these tests hold: the séance goes through the five activities in the order the
method fixes, the two decisions the method puts on people are actually asked, stopping
anywhere saves everything and resuming pays for nothing twice, the completeness pass on
atelier 1's feared events can halt the plan, and a rejection at the approval gate
reopens the plan with the auditor's reasons rather than the whole atelier.

Both the model and the terminal are injected: a fake runner counting its calls, and a
scripted io that answers by looking at what the flow just printed.
"""

from __future__ import annotations

import pytest

from ebios_rm.domain.enums import (
    Acceptabilite,
    CategorieImpact,
    Confidence,
    FactStatus,
    Gravite,
    OptionTraitement,
    Origin,
    VraisemblanceInitiale,
)
from ebios_rm.domain.essential_asset import EssentialAsset, SupportAsset
from ebios_rm.domain.fact import Fact
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.domain.operational_scenario import AttackStep, OperationalScenario
from ebios_rm.domain.risk_source import ObjectifVise, RiskSource
from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.mission_context.clarification import ClarificationAnswer
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.orchestrator import mission_state
from ebios_rm.orchestrator.workshop5_flow import (
    Workshop5Flow,
    Workshop5NotReady,
    load_input,
)
from ebios_rm.repositories.attack_repository import AttackMitigation
from ebios_rm.repositories.mission_repository import MissionRepository, connect
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap, ControlReference, Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Output
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import Workshop3Output
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import Workshop4Output
from ebios_rm.workshops.workshop5_traitement_risque.models import (
    ACTIVITE_MESURES,
    ACTIVITE_PLAN_VALIDE,
    IndicatorProposal,
    MeasureProposal,
    ResidualProposal,
    RiskFormulationProposal,
    Workshop5Input,
)

GAP_ID = "BG-a1b2c3"


# --- The terminal, scripted ------------------------------------------------

class ScriptedIO:
    """Answers each prompt by matching what was printed just before it.

    Rules are (needle, answer) pairs and the first match wins. A rule answers as many
    times as it is matched — the séance asks « Motif (obligatoire) » in several places
    and they all deserve one — unless its needle starts with '!', which makes it
    one-shot: the first pass takes it, the next falls through to the rule behind it.
    That is how a test says « refuse the first time, accept the second ».

    An unmatched prompt fails the test with what the flow was showing, so a broken
    expectation says where it broke instead of hanging.
    """

    def __init__(self, rules: list[tuple[str, str]]) -> None:
        self.rules = list(rules)
        self.lines: list[str] = []
        self._since_input: list[str] = []
        self.asked: list[str] = []

    def out(self, line: str) -> None:
        self.lines.append(str(line))
        self._since_input.append(str(line))

    def ask(self, prompt: str) -> str:
        context = "\n".join(self._since_input) + "\n" + prompt
        self._since_input = []
        self.asked.append(prompt)
        for index, (needle, answer) in enumerate(self.rules):
            once = needle.startswith("!")
            if needle.lstrip("!") in context:
                if once:
                    self.rules.pop(index)
                return answer
        raise AssertionError(f"Aucune réponse prévue pour :\n{context[-1500:]}")

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


# --- The model, faked ------------------------------------------------------

class FakeRunner:
    """One canned answer per call, and a count of every call made."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.notes: dict[str, list[list[str] | None]] = {"formulate": [], "mesures": [], "indicateurs": []}
        self.comite_seen: list[str] = []

    def formulate_risques(self, w5_input, risques, revision_notes=None):
        self.calls.append("formulate")
        self.notes["formulate"].append(revision_notes)
        return [RiskFormulationProposal(risque_id=r.id, libelle=f"Risque métier {r.id}") for r in risques]

    def propose_mesures(self, w5_input, output, risques, mitigations, revision_notes=None):
        self.calls.append("mesures")
        self.notes["mesures"].append(revision_notes)
        n = len(output.mesures)
        return [
            MeasureProposal(
                axe="protection", thematique="authentification et contrôle d'accès",
                libelle=f"Déployer la MFA sur les accès distants ({n + 1})",
                description="MFA sur le VPN.", risques_ids=["R1"], modes_ids=["SO-01", "SO-02"],
                etapes_visees=["SO-01 étape 1"], gap_ids=[GAP_ID], mitigation_ids_attck=["M1032"],
                origine="atelier4_vulnerabilite", freins="Budget.", responsable="DSI",
                cout_complexite="+", charge_estimee="20 j/h", echeance="6 mois",
                justification="Casse l'accès initial.", effet_vraisemblance=1,
            ),
        ]

    def evaluate_residuel(self, w5_input, output, risques):
        self.calls.append("residuel")
        return [ResidualProposal(risque_id=r.id, vraisemblance_residuelle="V2",
                                 motif="La MFA casse l'étape d'accès initial.") for r in risques]

    def propose_indicateurs(self, w5_input, output, revision_notes=None):
        self.calls.append("indicateurs")
        self.notes["indicateurs"].append(revision_notes)
        self.comite_seen.append(output.cadre_suivi.comite if output.cadre_suivi else "")
        return [IndicatorProposal(libelle="Taux de comptes couverts par la MFA", type_valeur="taux",
                                  cible="100 %", frequence="trimestrielle", mesures_ids=["M-01"])]


class FakeClarifier:
    """Answers every question from the mission context, and remembers it was asked."""

    def __init__(self) -> None:
        self.questions: list[str] = []

    def answer(self, question, mission_context, workshop_output=None):
        self.questions.append(question)
        return ClarificationAnswer(answered=True, answer="R1 porte le mode SO-01, le plus vraisemblable.",
                                   based_on_facts=["SO-01"])


class FakeAttack:
    """The ATT&CK base, reduced to what atelier 5 asks of it."""

    def version(self) -> str:
        return "ATT&CK-Latest (sha256 test000000)"

    def mitigations_for(self, technique_ids):
        return {t: [AttackMitigation("M1032", "Multi-factor Authentication", "Second facteur.")]
                for t in technique_ids}


# --- Fixtures --------------------------------------------------------------

@pytest.fixture
def repo():
    conn = connect(":memory:")
    yield MissionRepository(conn)
    conn.close()


def _mode(mode_id, scenario_id, *, retenu=False, gravite=Gravite.CRITIQUE,
          revised=VraisemblanceInitiale.V3, evenements=("ER-1",)) -> OperationalScenario:
    return OperationalScenario(
        id=mode_id, scenario_strategique_id=scenario_id, source_risque_id="SR-01",
        objectif_vise_id="OV-01", variante=f"Mode {mode_id}", voie="acces_distant", retenu=retenu,
        gravite=gravite, vraisemblance_initiale=VraisemblanceInitiale.V2, revised_likelihood=revised,
        biens_essentiels_ids=["BE-1"], evenements_redoutes_ids=list(evenements),
        attack_path=[AttackStep(tactic="initial-access", technique_id="T1078",
                                technique_name="Valid Accounts", description="Connexion VPN.",
                                bien_support_id="BS-1", justification="Aucune MFA.")],
    )


def _scenario(scenario_id, gravite) -> StrategicScenario:
    return StrategicScenario(id=scenario_id, source_risque_id="SR-01", objectif_vise_id="OV-01",
                             couple_id=f"C-{scenario_id}", resume=f"Route {scenario_id}",
                             justification="Plausible ici.", biens_essentiels_ids=["BE-1"],
                             evenements_redoutes_ids=["ER-1"], gravite=gravite)


def _feared(event_id, gravite) -> FearedEvent:
    return FearedEvent(id=event_id, description=f"Événement {event_id}", bien_essentiel_id="BE-1",
                       categorie_impact=CategorieImpact.FONCTIONNEMENT, gravite=gravite,
                       origin=Origin.ASSESSMENT)


def _w5_input(*, evenements=None) -> Workshop5Input:
    return Workshop5Input(
        organisation_nom="Clinique Test", secteur_activite="Santé",
        contexte={"maturite_securite": "faible", "cadence_comite_securite": "tous les six mois"},
        modes_operatoires=[
            _mode("SO-01", "SS-01", retenu=True),
            _mode("SO-02", "SS-01", revised=VraisemblanceInitiale.V2),
            _mode("SO-03", "SS-02", retenu=True, gravite=Gravite.GRAVE,
                  revised=VraisemblanceInitiale.V1, evenements=("ER-3",)),
        ],
        scenarios_strategiques=[_scenario("SS-01", Gravite.CRITIQUE), _scenario("SS-02", Gravite.GRAVE)],
        sources_risque=[RiskSource(id="SR-01", categorie_id="CAT-1", nom="Concurrent",
                                   justification="Secteur concurrentiel.")],
        objectifs_vises=[ObjectifVise(id="OV-01", finalite_id="F-1", description="Obtenir le fichier",
                                      justification="Valeur marchande.")],
        biens_essentiels=[EssentialAsset(id="BE-1", nom="Dossier patient", description="Données",
                                         nature="information", origin=Origin.ASSESSMENT,
                                         derived_from_fact_fields=["x"])],
        biens_supports=[SupportAsset(id="BS-1", nom="SIH", description="SI hospitalier",
                                     type_support="application", biens_essentiels_supportes=["BE-1"],
                                     origin=Origin.ASSESSMENT, derived_from_fact_fields=["x"])],
        evenements_redoutes=evenements if evenements is not None else [
            _feared("ER-1", Gravite.CRITIQUE), _feared("ER-3", Gravite.GRAVE)],
        baseline_gaps=[BaselineGap(gap_id=GAP_ID, weakness="Absence de MFA",
                                   controls=[ControlReference(framework="ISO27001", control_id="A.5.17")],
                                   risk_categories=["initial_access"])],
    )


def _context() -> MissionContext:
    return MissionContext(organisation_nom="Clinique Test", secteur_activite="Santé",
                          applicable_frameworks=["ISO27001"])


def _flow(repo, io, runner, w5_input=None, clarifier=None) -> tuple[str, Workshop5Flow]:
    mission_id = repo.create_mission("Clinique Test", ["ISO27001"])
    flow = Workshop5Flow(repo, mission_id, _context(), w5_input or _w5_input(), FakeAttack(), runner,
                         clarifier, io.ask, io.out)
    return mission_id, flow


# The whole séance answered: options decided, plan validated, residuals accepted, gate approved.
HAPPY_RULES: list[tuple[str, str]] = [
    ("R1 — quelle option de traitement", "r"),
    ("R2 — quelle option de traitement", "m"),
    ("Motif de la décision", "Décidé en séance avec la direction."),
    ("Demander les mesures maintenant", "o"),
    ("Que faire du plan", "v"),
    ("Que faire des risques résiduels", "a"),
    ("Identifiants acceptés", ""),
    ("Qui prononce l'acceptation", "Mme la directrice générale"),
    ("Instance de suivi et cadence", "Comité sécurité semestriel"),
    ("Cadence de révision de l'étude", "12 mois"),
    ("Prochaine revue", "2026-03"),
    ("Approuvez-vous ce résultat", "oui"),
]


# --- The happy path: the five activities, in order --------------------------

def test_the_seance_runs_the_five_activities_and_is_approved(repo):
    io, runner = ScriptedIO(HAPPY_RULES), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)

    assert flow.run(None) == 0
    assert runner.calls == ["formulate", "mesures", "residuel", "indicateurs"]

    saved = mission_state.load_w5_output(repo, mission_id)
    assert [r.id for r in saved.risques] == ["R1", "R2"]
    assert saved.risques[0].option_traitement is OptionTraitement.REDUCTION
    assert saved.risques[1].option_traitement is OptionTraitement.MAINTIEN
    assert [m.id for m in saved.mesures] == ["M-01"]
    assert saved.risques[0].vraisemblance_residuelle is VraisemblanceInitiale.V2
    assert saved.risques[1].vraisemblance_residuelle is saved.risques[1].vraisemblance
    assert all(r.accepte_par == "Mme la directrice générale" for r in saved.risques)
    assert saved.cadre_suivi.comite == "Comité sécurité semestriel"
    assert [i.id for i in saved.cadre_suivi.indicateurs] == ["IND-01"]
    assert saved.quality_report.erreurs == []
    assert mission_state.is_approved(repo, mission_id, mission_state.WORKSHOP_5)


def test_the_gravite_never_moves_and_the_map_is_printed_both_ways(repo):
    io, runner = ScriptedIO(HAPPY_RULES), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)
    flow.run(None)

    saved = mission_state.load_w5_output(repo, mission_id)
    assert saved.risques[0].gravite is Gravite.CRITIQUE
    assert "Cartographie des risques" in io.text
    assert "Cartographie des risques résiduels" in io.text


def test_every_decision_is_logged_with_its_justification(repo):
    io, runner = ScriptedIO(HAPPY_RULES), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)
    flow.run(None)

    actions = [d.action_taken for d in repo.decisions(mission_id)]
    assert "traitement:R1:reduction" in actions
    assert "traitement:R2:maintien" in actions
    assert "plan_valide" in actions
    assert any(a.startswith("residuels_acceptes") for a in actions)
    assert "approved" in actions


# --- Stopping and resuming --------------------------------------------------

def test_stopping_at_a_decision_saves_everything_and_resumes_without_paying_twice(repo):
    stop_after_r1 = [
        ("R1 — quelle option de traitement", "r"),
        ("R2 — quelle option de traitement", "q"),
        ("Motif de la décision", "Décidé en séance."),
    ]
    io, runner = ScriptedIO(stop_after_r1), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)

    assert flow.run(None) == 1                       # stopped, resumable
    assert runner.calls == ["formulate"]
    paused = mission_state.load_w5_output(repo, mission_id)
    assert paused.risques[0].option_traitement is OptionTraitement.REDUCTION
    assert paused.risques[1].option_traitement is None

    io2, runner2 = ScriptedIO(HAPPY_RULES), FakeRunner()
    resumed = Workshop5Flow(repo, mission_id, _context(), _w5_input(), FakeAttack(), runner2,
                            None, io2.ask, io2.out)
    assert resumed.run(paused) == 0
    # The formulation was already paid for, and R1's decision is not asked again.
    assert runner2.calls == ["mesures", "residuel", "indicateurs"]
    assert "R1 — quelle option de traitement" not in io2.text


def test_stopping_before_the_plan_call_does_not_buy_it_on_resume(repo):
    io, runner = ScriptedIO([
        ("R1 — quelle option", "r"), ("R2 — quelle option", "m"),
        ("Motif de la décision", "Décidé en séance."),
        ("Demander les mesures maintenant", "n"),
    ]), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)

    assert flow.run(None) == 1
    assert runner.calls == ["formulate"]
    paused = mission_state.load_w5_output(repo, mission_id)
    assert ACTIVITE_MESURES not in paused.activites_faites
    assert paused.mesures == []


def test_a_plan_left_unreviewed_is_reviewed_again_on_resume(repo):
    io, runner = ScriptedIO([
        ("R1 — quelle option", "r"), ("R2 — quelle option", "m"),
        ("Motif de la décision", "Décidé en séance."),
        ("Demander les mesures maintenant", "o"),
        ("Que faire du plan", "q"),
    ]), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)

    assert flow.run(None) == 1
    paused = mission_state.load_w5_output(repo, mission_id)
    assert ACTIVITE_MESURES in paused.activites_faites
    assert ACTIVITE_PLAN_VALIDE not in paused.activites_faites
    assert len(paused.mesures) == 1

    io2, runner2 = ScriptedIO(HAPPY_RULES), FakeRunner()
    resumed = Workshop5Flow(repo, mission_id, _context(), _w5_input(), FakeAttack(), runner2,
                            None, io2.ask, io2.out)
    assert resumed.run(paused) == 0
    assert "mesures" not in runner2.calls          # the plan is not bought a second time
    assert "Que faire du plan" in io2.text


# --- The auditor outranks the agent and the scale ---------------------------

def test_the_auditor_can_drop_a_measure_and_its_reason_is_kept(repo):
    io, runner = ScriptedIO([
        ("R1 — quelle option", "r"), ("R2 — quelle option", "m"),
        ("Motif de la décision", "Décidé en séance."),
        ("Demander les mesures maintenant", "o"),
        ("Identifiants des mesures à écarter", "M-01"),
        ("Motif (obligatoire", "Déjà couvert par un projet en cours."),
        # First pass through the plan: drop; second pass: validate what is left.
        ("!Que faire du plan", "e"),
        # Dropping the only measure leaves R1 to be reduced with nothing: the checker
        # blocks approval, and only a typed override gets past it (§14).
        ("Tapez CONFIRMER pour approuver", "CONFIRMER"),
    ] + HAPPY_RULES), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)
    flow.run(None)

    saved = mission_state.load_w5_output(repo, mission_id)
    dropped = [e for e in saved.elements_ecartes if e.type == "mesure"]
    assert [e.detail for e in dropped] == ["Déjà couvert par un projet en cours."]
    assert "mesures_ecartees:M-01" in [d.action_taken for d in repo.decisions(mission_id)]


def test_keeping_an_unacceptable_risk_as_it_is_takes_a_typed_confirmation(repo):
    asked: list[str] = []

    class Watcher(ScriptedIO):
        def ask(self, prompt):
            answer = super().ask(prompt)
            asked.append(answer)
            return answer

    io = Watcher([
        # R1 is « Inacceptable »: choosing maintien must be confirmed in writing.
        ("R1 — quelle option de traitement", "m"),
        ("Tapez CONFIRMER pour maintenir", "non"),
        ("R2 — quelle option de traitement", "q"),
    ])
    mission_id, flow = _flow(repo, io, FakeRunner())

    assert flow.run(None) == 1
    paused = mission_state.load_w5_output(repo, mission_id)
    assert paused.risques[0].acceptabilite is Acceptabilite.INACCEPTABLE
    assert paused.risques[0].option_traitement is None      # refused, so nothing was recorded
    assert "non" in asked


def test_an_uncovered_serious_feared_event_can_halt_the_seance(repo):
    io = ScriptedIO([("s'arrêter ici et reprendre les ateliers 2 à 4", "n")])
    w5_input = _w5_input(evenements=[_feared("ER-1", Gravite.CRITIQUE), _feared("ER-3", Gravite.GRAVE),
                                     _feared("ER-9", Gravite.CRITIQUE)])
    _mission_id, flow = _flow(repo, io, FakeRunner(), w5_input)

    assert flow.run(None) == 1
    assert "ER-9" in io.text
    assert "itérer les ateliers 2 à 4" in io.text or "reprendre les ateliers 2 à 4" in io.text


def test_continuing_past_an_uncovered_feared_event_is_logged(repo):
    io = ScriptedIO([("continuer quand même", "c"),
                     ("Tapez CONFIRMER pour approuver", "CONFIRMER"),
                     ("Motif (obligatoire", "ER-9 traité hors périmètre de cette étude.")]
                    + HAPPY_RULES)
    w5_input = _w5_input(evenements=[_feared("ER-1", Gravite.CRITIQUE), _feared("ER-3", Gravite.GRAVE),
                                     _feared("ER-9", Gravite.CRITIQUE)])
    mission_id, flow = _flow(repo, io, FakeRunner(), w5_input)
    flow.run(None)

    actions = [d.action_taken for d in repo.decisions(mission_id)]
    assert any(a.startswith("couverture_er_incomplete") for a in actions)


def test_a_residual_risk_can_send_the_seance_back_to_the_plan(repo):
    io, runner = ScriptedIO([
        # First pass: the residual level is still too high, so the plan is reinforced;
        # second pass through 5-4, the residual risks are accepted.
        ("!Que faire des risques résiduels", "p"),
        ("Ce qui doit être renforcé", "Rien sur la sauvegarde."),
    ] + HAPPY_RULES), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)

    assert flow.run(None) == 0
    assert runner.calls.count("mesures") == 2
    assert runner.notes["mesures"][-1] == ["Rien sur la sauvegarde."]
    saved = mission_state.load_w5_output(repo, mission_id)
    assert len(saved.mesures) == 2                 # the plan was reinforced, not replaced
    assert saved.risques[0].vraisemblance_residuelle is not None
    assert all(r.accepte_par for r in saved.risques)


def _rejected_once(block: str) -> list[tuple[str, str]]:
    """Refuse at the gate once, send back ``block``, approve the relaunch."""
    return [
        ("!Approuvez-vous ce résultat", "non"),
        ("Motif du refus", "Aucune mesure sur la sauvegarde."),
        ("relancer l'agent en tenant compte du motif", "r"),
        ("Quelles parties faut-il refaire", block),
    ] + HAPPY_RULES


def test_a_rejection_of_the_plan_reopens_only_the_plan_with_its_reasons(repo):
    io, runner = ScriptedIO(_rejected_once("3")), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)

    assert flow.run(None) == 0
    assert runner.calls == ["formulate", "mesures", "residuel", "indicateurs",
                            "mesures", "residuel"]
    assert runner.notes["mesures"][-1] == ["Aucune mesure sur la sauvegarde."]
    saved = mission_state.load_w5_output(repo, mission_id)
    # The treatment decisions are the auditor's own and survive the relaunch.
    assert saved.risques[0].option_traitement is OptionTraitement.REDUCTION
    assert len(saved.mesures) == 2
    # A changed plan is accepted again: the direction ruled on a residual level.
    assert io.text.count("Acceptation des risques résiduels") == 2
    # A new version, the refused one kept in the history (§12.6).
    assert repo.version_count(mission_id, mission_state.WORKSHOP_5) == 2


def test_a_rejection_of_the_wording_redoes_the_wording_alone(repo):
    io, runner = ScriptedIO(_rejected_once("1")), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)

    assert flow.run(None) == 0
    assert runner.calls == ["formulate", "mesures", "residuel", "indicateurs", "formulate"]
    assert runner.notes["formulate"][-1] == ["Aucune mesure sur la sauvegarde."]
    saved = mission_state.load_w5_output(repo, mission_id)
    assert len(saved.mesures) == 1 and all(r.accepte_par for r in saved.risques)


def test_a_rejection_of_the_options_asks_them_again_and_rebuilds_the_plan(repo):
    io, runner = ScriptedIO(_rejected_once("2")), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)

    assert flow.run(None) == 0
    assert io.text.count("R1 — quelle option de traitement") == 2
    assert runner.calls.count("mesures") == 2        # new options, new plan


def test_a_rejection_of_the_monitoring_redoes_the_indicators_with_the_reasons(repo):
    io, runner = ScriptedIO(_rejected_once("4")), FakeRunner()
    _mission_id, flow = _flow(repo, io, runner)

    assert flow.run(None) == 0
    assert runner.calls == ["formulate", "mesures", "residuel", "indicateurs", "indicateurs"]
    assert runner.notes["indicateurs"][-1] == ["Aucune mesure sur la sauvegarde."]
    assert runner.comite_seen == ["Comité sécurité semestriel"] * 2   # the call sees the instance


def test_a_hand_edit_at_the_gate_recomputes_the_level_it_implies(repo):
    io, runner = ScriptedIO([
        ("!Approuvez-vous ce résultat", "non"),
        ("Motif du refus", "Le résiduel de R1 est trop optimiste."),
        ("corriger vous-même", "c"),
        ("!Chemin", "risques.0.vraisemblance_residuelle"),
        ("Chemin", ""),
        ("Nouvelle valeur", "V3"),
        ("Justification", "La MFA ne couvre pas les comptes de service."),
    ] + HAPPY_RULES), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)

    assert flow.run(None) == 0
    r1 = mission_state.load_w5_output(repo, mission_id).risques[0]
    assert r1.vraisemblance_residuelle is VraisemblanceInitiale.V3
    assert r1.niveau_risque_residuel is not None
    assert r1.niveau_risque_residuel.value == "Critique"      # Critique x V3, recomputed
    assert r1.acceptabilite_residuelle is Acceptabilite.INACCEPTABLE


def test_the_auditor_can_question_the_agent_before_deciding(repo):
    clarifier = FakeClarifier()
    io, runner = ScriptedIO([
        ("!R1 — quelle option de traitement", "?"),
        ("!Votre question", ""),                       # nothing to ask on the risk map (5-1)
        ("!Votre question", "Pourquoi SO-01 porte-t-il le risque ?"),   # asked at R1's decision
        ("Votre question", ""),
    ] + HAPPY_RULES), FakeRunner()
    _mission_id, flow = _flow(repo, io, runner, clarifier=clarifier)

    assert flow.run(None) == 0
    assert clarifier.questions == ["Pourquoi SO-01 porte-t-il le risque ?"]
    assert "R1 porte le mode SO-01" in io.text
    assert "poser une question à l'agent" in io.text


def test_the_owner_proposed_from_the_session_reaches_the_plan(repo):
    io, runner = ScriptedIO(HAPPY_RULES), FakeRunner()
    mission_id, flow = _flow(repo, io, runner)
    flow.run(None)
    assert mission_state.load_w5_output(repo, mission_id).mesures[0].responsable == "DSI"


# --- The input contract read off the mission state --------------------------

def _seed_mission(repo, *, approve_w4: bool) -> str:
    mission_id = repo.create_mission("Clinique Test", ["ISO27001"])
    mission_state.save_mission_context(repo, mission_id, _context().model_copy(update={"facts": [
        Fact(field_name="maturite_securite", value="faible", origin=Origin.DECLARATION,
             confidence=Confidence.HIGH, status=FactStatus.APPROVED),
        Fact(field_name="perimetre_exclus", value="filiales", origin=Origin.DECLARATION,
             confidence=Confidence.HIGH, status=FactStatus.APPROVED),
    ]}))
    w5_input = _w5_input()
    mission_state.save_w1_output(repo, mission_id, Workshop1Output(
        biens_essentiels=w5_input.biens_essentiels, biens_supports=w5_input.biens_supports,
        evenements_redoutes=w5_input.evenements_redoutes, baseline_gaps_full=w5_input.baseline_gaps))
    mission_state.save_w2_output(repo, mission_id, Workshop2Output(
        sources_risque=w5_input.sources_risque, objectifs_vises=w5_input.objectifs_vises))
    mission_state.save_w3_output(repo, mission_id, Workshop3Output(
        scenarios=w5_input.scenarios_strategiques))
    version = mission_state.save_w4_output(repo, mission_id, Workshop4Output(
        scenarios=w5_input.modes_operatoires))
    if approve_w4:
        repo.set_version_status(mission_id, mission_state.WORKSHOP_4, version, "approved")
    return mission_id


def test_load_input_refuses_to_start_on_an_unapproved_atelier4(repo):
    mission_id = _seed_mission(repo, approve_w4=False)
    with pytest.raises(Workshop5NotReady, match="atelier 4"):
        load_input(repo, mission_id)


def test_load_input_refuses_an_unknown_mission(repo):
    with pytest.raises(Workshop5NotReady):
        load_input(repo, "no-such-mission")


def test_load_input_gives_atelier5_the_gaps_whole_and_only_its_own_context(repo):
    mission_id = _seed_mission(repo, approve_w4=True)
    _context_loaded, w5_input = load_input(repo, mission_id)

    # Unlike atelier 4, the plan sees which requirement each gap comes from (§12.3, §19).
    assert w5_input.baseline_gaps[0].frameworks == ["ISO27001"]
    assert w5_input.baseline_gaps[0].control_ids == ["A.5.17"]
    # The narrow input: a context field atelier 5 has no use for does not travel.
    assert "maturite_securite" in w5_input.contexte
    assert "perimetre_exclus" not in w5_input.contexte
    assert [m.id for m in w5_input.modes_operatoires] == ["SO-01", "SO-02", "SO-03"]
    assert w5_input.alertes_atelier4 == []


# --- The Orchestrator's adapter, driving the same séance -------------------

def test_the_orchestrator_adapter_runs_the_seance_up_to_its_own_gate(repo):
    import asyncio

    from ebios_rm.orchestrator.workshop5_runner import Workshop5Runner

    mission_id = _seed_mission(repo, approve_w4=True)
    _context_loaded, w5_input = load_input(repo, mission_id)
    io, runner = ScriptedIO(HAPPY_RULES), FakeRunner()
    adapter = Workshop5Runner(repo, runner=runner, attack=FakeAttack(), io_in=io.ask, io_out=io.out)

    output = asyncio.run(adapter.run(w5_input, mission_id))

    # The Orchestrator owns the approval: the adapter stops at the assembled plan.
    assert not any("Approuvez-vous" in prompt for prompt in io.asked)
    assert runner.calls == ["formulate", "mesures", "residuel", "indicateurs"]
    assert "2 risque(s) dont 2 résiduel(s) accepté(s), 1 mesure(s)" in adapter.summarize_output(output)


def test_the_orchestrator_adapter_turns_a_pause_into_workshop_halted(repo):
    import asyncio

    from ebios_rm.orchestrator.signals import WorkshopHalted
    from ebios_rm.orchestrator.workshop5_runner import Workshop5Runner

    mission_id = _seed_mission(repo, approve_w4=True)
    _context_loaded, w5_input = load_input(repo, mission_id)
    io = ScriptedIO([("R1 — quelle option de traitement", "q")])
    adapter = Workshop5Runner(repo, runner=FakeRunner(), attack=FakeAttack(), io_in=io.ask, io_out=io.out)

    with pytest.raises(WorkshopHalted):
        asyncio.run(adapter.run(w5_input, mission_id))
    # And the same mission resumes where it stopped, the wording already paid for.
    io2, runner2 = ScriptedIO(HAPPY_RULES), FakeRunner()
    resumed = Workshop5Runner(repo, runner=runner2, attack=FakeAttack(), io_in=io2.ask, io_out=io2.out)
    asyncio.run(resumed.resume(mission_id))
    assert runner2.calls == ["mesures", "residuel", "indicateurs"]
