"""Atelier 5 driven end to end: risk map, treatment strategy, plan, residual risks, monitoring.

Atelier N -> Mission State -> Orchestrator -> Atelier N+1 (§10.2): this module reads the
approved ateliers 1 to 4 from the mission state, and every step it takes is saved back
there before the next one starts. Where the séance stands is read from the saved
w5_output itself — which risks are still without a decision, whether the plan has been
reviewed, which residual risks nobody has accepted yet — so stopping anywhere and
running the same command again resumes at that point without paying twice for a call.

The five activities of the method, in order:
  5-1  the risks, built from the ateliers before them, worded for a decision-maker, and
       the completeness pass on atelier 1's feared events;
  5-2  what the scale says about each risk, and the treatment option the auditor decides;
  5-3  the treatment plan in its four axes, reviewed measure by measure;
  5-4  the residual risks once the plan is counted, formally accepted by name;
  5-5  the monitoring framework — indicators, committee, review cycles.

Two decisions are never asked of the model (§2): the treatment option per risk and the
acceptance of the residual risks. The agent proposes wording, measures, a residual
evaluation and indicators; the auditor and the direction rule.

At each decision the auditor can also question the agent about the result, grounded in
the mission context (the clarification loop of atelier 1). Every interaction goes through
injected ``io_in`` / ``io_out`` and every model call through an injected runner, so the
whole flow runs in tests without a terminal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ebios_rm.domain.enums import (
    Acceptabilite,
    AxeMesure,
    Gravite,
    OptionTraitement,
    VraisemblanceInitiale,
)
from ebios_rm.domain.risk_scenario import RiskScenario
from ebios_rm.mission_context.clarification import ClarificationRunner, clarification_repl
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.orchestrator import mission_state
from ebios_rm.orchestrator.approval_cli import ApprovalLoop, ask_choice, ask_ids
from ebios_rm.repositories.attack_repository import AttackMitigation, AttackRepository
from ebios_rm.repositories.mission_repository import MissionRepository
from ebios_rm.workshops.common import AtelierDataError
from ebios_rm.workshops.workshop1_cadrage.human_interface import HumanInterface, ask_justification
from ebios_rm.workshops.workshop5_traitement_risque import (
    Workshop5Input,
    Workshop5Output,
    ask_session_questions,
    assemble_output,
    build_workshop5_input,
    formulate,
    initial_output,
    run_cadre,
    run_mesures,
    run_residuel,
    techniques_citees,
)
from ebios_rm.workshops.workshop5_traitement_risque.agent_runner import Workshop5AgentRunner
from ebios_rm.workshops.workshop5_traitement_risque.assessment import (
    accept_residuel,
    er_graves_non_couverts,
    option_proposee,
    remove_mesures,
    set_traitement,
)
from ebios_rm.workshops.workshop5_traitement_risque.models import (
    ACTIVITE_FORMULATION,
    ACTIVITE_MESURES,
    ACTIVITE_PLAN_VALIDE,
    REASON_MESURE_ECARTEE_PAR_AUDITEUR,
)

STAGE = "workshop_5"
RESUME_COMMAND = "python scripts/run_workshop5.py {mission_id}"

Ask = Callable[[str], str]
Say = Callable[[str], None]

# The four options of activity 5-2, as the auditor picks them.
_OPTION_KEYS: dict[str, OptionTraitement] = {
    "r": OptionTraitement.REDUCTION,
    "m": OptionTraitement.MAINTIEN,
    "p": OptionTraitement.PARTAGE,
    "e": OptionTraitement.EVITEMENT,
}
_OPTION_LABELS: dict[OptionTraitement, str] = {
    OptionTraitement.REDUCTION: "réduire : agir sur le scénario pour le rendre moins vraisemblable",
    OptionTraitement.MAINTIEN: "maintenir : garder le risque en l'état",
    OptionTraitement.PARTAGE: "partager : transférer tout ou partie (assurance, contrat, tiers)",
    OptionTraitement.EVITEMENT: "éviter : renoncer à l'activité ou à l'exposition",
}


class Workshop5NotReady(RuntimeError):
    """A prerequisite of atelier 5 is missing; the message says which, and what to run."""


class _Paused(Exception):
    """The auditor chose to stop here. Everything so far is saved; the same command resumes."""


def load_input(repo: MissionRepository, mission_id: str) -> tuple[MissionContext, Workshop5Input]:
    """The approved ateliers 1 to 4, read from the mission state, as the narrow atelier 5 input."""
    mission = repo.get_mission(mission_id)
    if mission is None:
        raise Workshop5NotReady(f"Mission introuvable : {mission_id}")
    mission_context = mission_state.load_mission_context(repo, mission_id)
    w1 = mission_state.load_w1_output(repo, mission_id)
    w2 = mission_state.load_w2_output(repo, mission_id)
    w3 = mission_state.load_w3_output(repo, mission_id)
    w4 = mission_state.load_w4_output(repo, mission_id)
    if mission_context is None or w1 is None or w2 is None or w3 is None or w4 is None:
        raise Workshop5NotReady(
            "Mission incomplète : il faut un Mission Context et les résultats des ateliers 1 à 4.")
    if not mission_state.is_approved(repo, mission_id, mission_state.WORKSHOP_4):
        # Asked of the atelier 4 version, not of mission.status: a treatment plan built on
        # scenarios the auditor has not ruled on would be rewritten the moment they do (§2).
        raise Workshop5NotReady(
            f"L'atelier 4 n'est pas approuvé (statut de la mission : {mission.status}). "
            f"Approuvez-le d'abord : python scripts/run_workshop4.py {mission_id}")
    return mission_context, build_workshop5_input(mission_context, w1, w2, w3, w4)


def run_workshop5(
    repo: MissionRepository,
    mission_id: str,
    attack: AttackRepository,
    runner: Workshop5AgentRunner,
    *,
    human: HumanInterface | None = None,
    clarifier: ClarificationRunner | None = None,
    io_in: Ask = input,
    io_out: Say = print,
) -> int:
    """Run or resume atelier 5. 0 approved, 1 stopped by the auditor (resumable).

    ``human`` holds the séance questions (None skips them); ``clarifier`` answers the
    auditor's questions at each decision (None skips that). ``attack`` supplies the ATT&CK
    mitigations of the techniques the modes cite — read in code, never by the model.
    A failed model call or an interrupt propagates to the caller, everything already
    decided being saved.
    """
    mission_context, w5_input = load_input(repo, mission_id)
    io_out(f"Entrée atelier 5 : {len(w5_input.scenarios_strategiques)} scénario(s) stratégique(s), "
           f"{len(w5_input.modes_operatoires)} mode(s) opératoire(s) développé(s) dont "
           f"{sum(1 for m in w5_input.modes_operatoires if m.retenu)} retenu(s), "
           f"{len(w5_input.baseline_gaps)} écart(s) du socle, "
           f"{len(w5_input.evenements_redoutes)} événement(s) redouté(s).")
    for alert in w5_input.alertes_atelier4:
        io_out(f"  [{'BLOQUANT' if alert.bloquant else 'avertissement'}] {alert.reference} — {alert.probleme}")
    if w5_input.alertes_bloquantes:
        raise AtelierDataError(4, w5_input.alertes_bloquantes)

    saved = mission_state.load_w5_output(repo, mission_id)
    if saved is not None and mission_state.is_approved(repo, mission_id, mission_state.WORKSHOP_5):
        io_out("Atelier 5 déjà approuvé. Résultat enregistré :")
        print_summary(saved, w5_input, io_out)
        return 0

    if saved is not None:
        treated = [r.scenario_strategique_id for r in saved.risques]
        expected = [m.scenario_strategique_id for m in w5_input.modes_operatoires if m.retenu]
        if treated and sorted(set(treated)) != sorted(set(expected)):
            # Atelier 4 was redone and re-approved after this atelier 5 started: the risk
            # map describes scenarios that are no longer the approved ones.
            io_out(f"\nL'atelier 4 a changé depuis le début de l'atelier 5 : {sorted(set(treated))} traités, "
                   f"{sorted(set(expected))} approuvés aujourd'hui.")
            choice = ask_choice("Recommencer l'atelier 5 sur la liste approuvée ?",
                                {"o": "oui, nouvelle tentative (l'ancienne reste dans l'historique)",
                                 "n": "non, en rester là"}, io_in, io_out)
            if choice == "n":
                return 1
            repo.log_decision(mission_id, stage=STAGE, action="restart_atelier4_modifie",
                              justification=f"Risques portant sur {sorted(set(treated))}, "
                                            f"scénarios approuvés {sorted(set(expected))}")
            saved = None
        else:
            io_out("Atelier 5 en cours — reprise là où il s'est arrêté.")

    if saved is None and human is not None:
        enriched = ask_session_questions(w5_input, human)
        answered = mission_state.persist_session_answers(
            repo, mission_id, mission_context, w5_input, enriched, stage=STAGE)
        if answered:
            io_out(f"  {answered} réponse(s) de séance enregistrée(s) dans le contexte de la mission.")
        w5_input = enriched

    flow = Workshop5Flow(repo, mission_id, mission_context, w5_input, attack, runner,
                         clarifier, io_in, io_out)
    return flow.run(saved)


@dataclass
class Workshop5Flow:
    repo: MissionRepository
    mission_id: str
    mission_context: MissionContext
    w5_input: Workshop5Input
    attack: AttackRepository
    runner: Workshop5AgentRunner
    clarifier: ClarificationRunner | None = None
    io_in: Ask = input
    io_out: Say = print
    _mitigations: dict[str, list[AttackMitigation]] | None = field(default=None, repr=False)

    def run(self, saved: Workshop5Output | None) -> int:
        try:
            output = self.advance(saved if saved is not None else self.start())
            return self.approval(output)
        except _Paused:
            self.io_out("Tout est enregistré. Pour reprendre : "
                        + RESUME_COMMAND.format(mission_id=self.mission_id))
            return 1

    def start(self) -> Workshop5Output:
        output = initial_output(self.w5_input, self.attack.version())
        if not output.risques:
            raise Workshop5NotReady(
                "Aucun risque à traiter : aucun scénario stratégique ne porte de mode opératoire "
                "retenu avec une vraisemblance révisée. Reprenez l'atelier 4.")
        mission_state.save_w5_output(self.repo, self.mission_id, output)
        self.repo.set_status(self.mission_id, "w5_in_progress")
        return output

    def checkpoint(self, output: Workshop5Output) -> Workshop5Output:
        mission_state.checkpoint_w5_output(self.repo, self.mission_id, output)
        return output

    def mitigations(self) -> dict[str, list[AttackMitigation]]:
        """The ATT&CK mitigations of every technique the modes cite — one query, then cached."""
        if self._mitigations is None:
            techniques = techniques_citees(self.w5_input)
            self._mitigations = self.attack.mitigations_for(techniques)
            found = sum(len(v) for v in self._mitigations.values())
            self.io_out(f"ATT&CK {self.attack.version()} : {found} mesure(s) de sécurité rattachées aux "
                        f"{len(techniques)} technique(s) citées par les modes opératoires.")
        return self._mitigations

    # --- the five activities, in the order the method fixes ------------------

    def advance(self, output: Workshop5Output) -> Workshop5Output:
        """Take the séance from wherever it stands to the assembled plan, saving every step."""
        while True:
            if ACTIVITE_FORMULATION not in output.activites_faites:
                output = self.formulate_risques(output)
            elif any(r.option_traitement is None for r in output.risques):
                output = self.decide_traitement(output)
            elif ACTIVITE_MESURES not in output.activites_faites:
                output = self.mesures(output)
            elif ACTIVITE_PLAN_VALIDE not in output.activites_faites:
                output = self.review_plan(output)
            elif any(r.vraisemblance_residuelle is None for r in output.risques):
                output = self.residuel(output)
            elif any(not r.accepte_par.strip() for r in output.risques):
                output = self.accept(output)
            elif output.cadre_suivi is None:
                output = self.cadre(output)
            else:
                return self.checkpoint(assemble_output(self.w5_input, output))

    # --- 5-1: the risks --------------------------------------------------

    def formulate_risques(self, output: Workshop5Output) -> Workshop5Output:
        """The risk map, worded for the people who will rule on it (activité 5-1)."""
        self.io_out(f"\n=== 5-1 Formulation des risques — {len(output.risques)} risque(s), "
                    "un appel au modèle ===")
        output = self.checkpoint(formulate(self.w5_input, output, self.runner))
        print_risques(output, self.w5_input, self.io_out)
        print_carte(output.risques, self.io_out)
        self.clarify(output)
        return self.coverage_gate(output)

    def coverage_gate(self, output: Workshop5Output) -> Workshop5Output:
        """The completeness pass of the method: a grave feared event nobody carries (activité 5-1)."""
        uncovered = [c.evenement_redoute_id for c in er_graves_non_couverts(output.couverture_er)]
        light = [c.evenement_redoute_id for c in output.couverture_er
                 if not c.couvert and c.evenement_redoute_id not in uncovered]
        if light:
            self.io_out(f"\nÉvénements redoutés de moindre gravité portés par aucun risque : {', '.join(light)}.")
        if not uncovered:
            return output
        self.io_out(f"\n/!\\ Événement(s) redouté(s) grave(s) ou critique(s) qu'aucun risque ne porte : "
                    f"{', '.join(uncovered)}.")
        self.io_out("La méthode demande d'itérer les ateliers 2 à 4 avant d'écrire le plan : un risque "
                    "majeur non couvert ne sera traité par aucune mesure.")
        choice = ask_choice("Que faire ?", {
            "n": "s'arrêter ici et reprendre les ateliers 2 à 4",
            "c": "continuer quand même (motif obligatoire, consigné)",
        }, self.io_in, self.io_out)
        if choice == "n":
            raise _Paused
        reason = ask_justification("Motif (obligatoire, §8) : ", self.io_in, self.io_out)
        self.repo.log_decision(self.mission_id, stage=STAGE,
                               action="couverture_er_incomplete:" + ",".join(uncovered),
                               justification=reason)
        return output

    # --- 5-2: the treatment strategy -------------------------------------

    def decide_traitement(self, output: Workshop5Output) -> Workshop5Output:
        """One decision per risk, the auditor's, each with its mandatory reason (§2, §8)."""
        pending = [r for r in output.risques if r.option_traitement is None]
        self.io_out(f"\n=== 5-2 Stratégie de traitement — {len(pending)} risque(s) à décider ===")
        self.io_out("L'échelle d'acceptabilité propose ; la décision vous appartient. "
                    "'q' à tout moment pour s'arrêter, la séance reprend ici.")
        for risque in pending:
            print_risque(risque, output, self.w5_input, self.io_out)
            proposed = option_proposee(risque)
            options = {key: (_OPTION_LABELS[option] + (" — proposé par l'échelle" if option is proposed else ""))
                       for key, option in _OPTION_KEYS.items()}
            choice = ask_choice(f"{risque.id} — quelle option de traitement ?",
                               {**options, "q": "s'arrêter ici"}, self.io_in, self.io_out)
            if choice == "q":
                raise _Paused
            option = _OPTION_KEYS[choice]
            if (option is OptionTraitement.MAINTIEN
                    and risque.acceptabilite is Acceptabilite.INACCEPTABLE):
                self.io_out(f"\n{risque.id} est « {Acceptabilite.INACCEPTABLE.value} » et vous le maintenez "
                            "en l'état. La méthode impose alors des mesures à court terme, ou le refus de "
                            "tout ou partie de l'activité.")
                self.io_out("Tapez CONFIRMER pour maintenir malgré tout ; toute autre saisie revient au choix.")
                if self.io_in("> ").strip() != "CONFIRMER":
                    continue
            justification = ask_justification(
                f"Motif de la décision sur {risque.id} (obligatoire, §8) : ", self.io_in, self.io_out)
            output = self.checkpoint(set_traitement(output, risque.id, option, justification))
            self.repo.log_decision(self.mission_id, stage=STAGE,
                                   action=f"traitement:{risque.id}:{option.value}",
                                   justification=justification)
        return output

    # --- 5-3: the treatment plan -----------------------------------------

    def a_traiter(self, output: Workshop5Output) -> list[RiskScenario]:
        """The risks the plan has to cover: everything the auditor did not simply keep as it is."""
        return [r for r in output.risques if r.option_traitement is not OptionTraitement.MAINTIEN]

    def mesures(self, output: Workshop5Output, revision_notes: list[str] | None = None) -> Workshop5Output:
        """Ask for the plan, once, over every risk to treat (activité 5-3)."""
        treat = self.a_traiter(output)
        if not treat:
            self.io_out("\nAucun risque à réduire, partager ou éviter : le plan de traitement est vide.")
            return self.checkpoint(output.model_copy(update={
                "activites_faites": [*output.activites_faites, ACTIVITE_MESURES, ACTIVITE_PLAN_VALIDE]}))
        self.io_out(f"\n=== 5-3 Plan de traitement — {len(treat)} risque(s) à traiter, un appel au modèle "
                    "sur l'ensemble ===")
        self.io_out("Un seul appel pour tout le plan : une mesure qui sert trois risques vaut mieux que trois "
                    "mesures, et cela ne s'obtient pas risque par risque.")
        if ask_choice("Demander les mesures maintenant ?",
                      {"o": "oui", "n": "non, s'arrêter ici"}, self.io_in, self.io_out) == "n":
            raise _Paused
        return self.checkpoint(run_mesures(self.w5_input, output, self.runner, self.mitigations(),
                                          treat, revision_notes))

    def review_plan(self, output: Workshop5Output) -> Workshop5Output:
        """The auditor's review of the plan, measure by measure (activité 5-3, §2)."""
        while True:
            print_plan(output, self.io_out)
            self.clarify(output)
            choice = ask_choice("Que faire du plan ?", {
                "v": "le valider en l'état",
                "r": "nommer le responsable, la charge et l'échéance d'une mesure",
                "e": "écarter une ou plusieurs mesures (motif obligatoire)",
                "c": "le compléter (nouvel appel au modèle, mesures déjà retenues comprises)",
                "q": "s'arrêter ici",
            }, self.io_in, self.io_out)
            if choice == "q":
                raise _Paused
            if choice == "v":
                self.repo.log_decision(self.mission_id, stage=STAGE, action="plan_valide",
                                       justification=f"{len(output.mesures)} mesure(s) retenue(s) par l'auditeur")
                return self.checkpoint(output.model_copy(update={
                    "activites_faites": [*output.activites_faites, ACTIVITE_PLAN_VALIDE]}))
            if choice == "e":
                ids = ask_ids("Identifiants des mesures à écarter :",
                              {m.id for m in output.mesures}, self.io_in, self.io_out)
                if ids:
                    reason = ask_justification("Motif (obligatoire, §8) : ", self.io_in, self.io_out)
                    output = self.checkpoint(remove_mesures(
                        output, ids, REASON_MESURE_ECARTEE_PAR_AUDITEUR, reason))
                    self.repo.log_decision(self.mission_id, stage=STAGE,
                                           action="mesures_ecartees:" + ",".join(ids), justification=reason)
                continue
            if choice == "r":
                output = self.assign_mesure(output)
                continue
            notes = ask_justification("Ce qui manque au plan (transmis au modèle, §8) : ",
                                      self.io_in, self.io_out)
            self.repo.log_decision(self.mission_id, stage=STAGE, action="plan_complete", justification=notes)
            output = self.mesures(output.model_copy(update={
                "activites_faites": [a for a in output.activites_faites if a != ACTIVITE_MESURES]}), [notes])

    def assign_mesure(self, output: Workshop5Output) -> Workshop5Output:
        """Who carries a measure, for how much work, by when — the auditor's columns of the plan."""
        ids = ask_ids("Identifiant de la mesure :", {m.id for m in output.mesures}, self.io_in, self.io_out)
        if not ids:
            return output
        by_id = {m.id: m for m in output.mesures}
        updated = dict(by_id)
        for mesure_id in ids:
            current = by_id[mesure_id]
            self.io_out(f"\n{mesure_id} — {current.libelle}")
            self.io_out(f"      responsable « {current.responsable} » · charge « {current.charge_estimee} » "
                        f"· échéance « {current.echeance} » · coût/complexité « {current.cout_complexite} »")
            responsable = self.io_in("Responsable ([Entrée] = inchangé) : ").strip()
            charge = self.io_in("Charge estimée en j/h ([Entrée] = inchangé) : ").strip()
            echeance = self.io_in("Échéance en mois ([Entrée] = inchangé) : ").strip()
            updated[mesure_id] = current.model_copy(update={
                "responsable": responsable or current.responsable,
                "charge_estimee": charge or current.charge_estimee,
                "echeance": echeance or current.echeance,
            })
            self.repo.log_decision(
                self.mission_id, stage=STAGE, action=f"mesure_affectee:{mesure_id}",
                justification=f"responsable « {updated[mesure_id].responsable} », "
                              f"charge « {updated[mesure_id].charge_estimee} », "
                              f"échéance « {updated[mesure_id].echeance} »")
        return self.checkpoint(output.model_copy(update={
            "mesures": [updated[m.id] for m in output.mesures]}))

    # --- 5-4: the residual risks -----------------------------------------

    def residuel(self, output: Workshop5Output) -> Workshop5Output:
        """What remains once the plan is in place — the likelihood only, never the gravité (5-4)."""
        treated = [r for r in output.risques if r.mesures_ids]
        self.io_out(f"\n=== 5-4 Risques résiduels — {len(treated)} risque(s) porteur(s) de mesures ===")
        if treated:
            self.io_out("Un appel au modèle : la gravité ne bouge pas, seule la vraisemblance peut baisser, "
                        "et seulement dans la limite de ce que les mesures revendiquent.")
        return self.checkpoint(run_residuel(self.w5_input, output, self.runner, treated))

    def accept(self, output: Workshop5Output) -> Workshop5Output:
        """The formal acceptance of the residual risks by the direction (activité 5-4, §2)."""
        pending = [r for r in output.risques if not r.accepte_par.strip()]
        self.io_out(f"\n=== 5-4 Acceptation des risques résiduels — {len(pending)} en attente ===")
        print_carte(output.risques, self.io_out, residuel=True)
        for risque in pending:
            print_residuel(risque, self.io_out)
        unacceptable = [r.id for r in pending if r.acceptabilite_residuelle is Acceptabilite.INACCEPTABLE]
        if unacceptable:
            self.io_out(f"\n/!\\ Risque(s) encore « {Acceptabilite.INACCEPTABLE.value} » après le plan : "
                        f"{', '.join(unacceptable)}. La méthode attend un plan renforcé, ou le refus de tout "
                        "ou partie de l'activité — une acceptation ici est une décision de la direction.")
        self.clarify(output)

        choice = ask_choice("Que faire des risques résiduels ?", {
            "a": "les faire accepter formellement (nom et fonction du décideur)",
            "p": "renforcer le plan d'abord (retour à l'activité 5-3)",
            "q": "s'arrêter ici",
        }, self.io_in, self.io_out)
        if choice == "q":
            raise _Paused
        if choice == "p":
            notes = ask_justification("Ce qui doit être renforcé (transmis au modèle, §8) : ",
                                      self.io_in, self.io_out)
            self.repo.log_decision(self.mission_id, stage=STAGE, action="plan_renforce", justification=notes)
            # Reopened state saved first, then the call — so a failure mid-call resumes
            # with the plan reopened, and the model is told what was missing.
            return self.mesures(self.checkpoint(self.reopen_plan(output, notes)), [notes])

        ids = ask_ids(f"Identifiants acceptés ([Entrée] = tous : {', '.join(r.id for r in pending)}) :",
                      {r.id for r in pending}, self.io_in, self.io_out) or [r.id for r in pending]
        who = ask_justification("Qui prononce l'acceptation (nom et fonction, obligatoire, §8) : ",
                                self.io_in, self.io_out)
        self.repo.log_decision(self.mission_id, stage=STAGE, action="residuels_acceptes:" + ",".join(ids),
                               justification=f"Acceptés par {who}")
        return self.checkpoint(accept_residuel(output, ids, who))

    def reopen_plan(self, output: Workshop5Output, notes: str) -> Workshop5Output:
        """Send the séance back to activity 5-3: the plan reopens, the residual evaluation is void.

        The acceptance goes with it: the direction accepted a residual level, not a
        promise — a plan that changes has to be accepted again.
        """
        return output.model_copy(update={
            "activites_faites": [a for a in output.activites_faites
                                 if a not in {ACTIVITE_MESURES, ACTIVITE_PLAN_VALIDE}],
            "risques": [r.model_copy(update={
                "vraisemblance_residuelle": None, "niveau_risque_residuel": None,
                "acceptabilite_residuelle": None, "accepte_par": "",
                "motif_residuel": f"Évaluation à refaire — plan renforcé : {notes}",
            }) for r in output.risques],
        })

    # --- 5-5: the monitoring framework -----------------------------------

    def cadre(self, output: Workshop5Output) -> Workshop5Output:
        """The framework that keeps the study alive after the plan is written (activité 5-5)."""
        suggested = str(self.w5_input.contexte.get("cadence_comite_securite", "") or "")
        self.io_out("\n=== 5-5 Cadre de suivi des risques — un appel au modèle pour les indicateurs ===")
        if suggested:
            self.io_out(f"Cadence indiquée en séance : {suggested}")
        self.io_out("La méthode suggère une revue tous les six mois en montée en puissance, "
                    "tous les douze en rythme de croisière.")
        comite = self.io_in(f"Instance de suivi et cadence [{suggested or 'à renseigner'}] : ").strip() or suggested
        cycles = self.io_in("Cadence de révision de l'étude (ex. « 12 mois ») : ").strip()
        prochaine = self.io_in("Prochaine revue (date ou échéance) : ").strip()
        output = self.checkpoint(run_cadre(self.w5_input, output, self.runner, comite=comite,
                                          cycles=cycles, prochaine_revue=prochaine))
        print_cadre(output, self.io_out)
        return output

    def clarify(self, output: Workshop5Output) -> None:
        if self.clarifier is not None:
            clarification_repl(self.clarifier, self.mission_context, output,
                               io_in=self.io_in, io_out=self.io_out)

    # --- the approval gate every atelier shares ------------------------------

    def approval(self, output: Workshop5Output) -> int:
        return ApprovalLoop(
            repo=self.repo,
            mission_id=self.mission_id,
            stage=STAGE,
            workshop_number=mission_state.WORKSHOP_5,
            label="l'atelier 5",
            print_output=self.show_final,
            rerun=self.redo,
            save=self.save_edit,
            model_cls=Workshop5Output,
            edit_examples="mesures.0.responsable        mesures.1.echeance        risques.0.option_traitement",
            io_in=self.io_in,
            io_out=self.io_out,
        ).run(output)

    def show_final(self, output: Workshop5Output) -> None:
        print_summary(output, self.w5_input, self.io_out)
        self.clarify(output)

    def redo(self, notes: list[str], blocks: set[str] | None, previous: Workshop5Output) -> Workshop5Output:
        """A rejection at the approval gate reopens the plan, as a new version.

        The risk map and the treatment options are kept: they are the auditor's own
        decisions, and a rejection is about the plan that follows from them. Their reasons
        travel to the model, so the new plan answers them instead of repeating itself.
        """
        reopened = self.reopen_plan(previous, notes[-1] if notes else "Relance demandée par l'auditeur")
        mission_state.save_w5_output(self.repo, self.mission_id, reopened)
        self.repo.set_status(self.mission_id, "w5_in_progress")
        return self.advance(self.mesures(reopened, notes))

    def save_edit(self, corrected: Workshop5Output) -> Workshop5Output:
        final = assemble_output(self.w5_input, corrected)
        mission_state.save_w5_output(self.repo, self.mission_id, final)
        return final


# --- Printing --------------------------------------------------------------

_GRAVITES = (Gravite.MINIMALE, Gravite.SIGNIFICATIVE, Gravite.GRAVE, Gravite.CRITIQUE)
_VRAISEMBLANCES = (VraisemblanceInitiale.V4, VraisemblanceInitiale.V3,
                   VraisemblanceInitiale.V2, VraisemblanceInitiale.V1)


def print_carte(risques: list[RiskScenario], io_out: Say = print, *, residuel: bool = False) -> None:
    """The risk map of the method: gravité across, vraisemblance down, risk ids in the cells."""
    title = "Cartographie des risques résiduels" if residuel else "Cartographie des risques"
    io_out(f"\n{title} — gravité en colonnes, vraisemblance en lignes")
    io_out("            " + "".join(f"{g.value[:13]:<14}" for g in _GRAVITES))
    for vraisemblance in _VRAISEMBLANCES:
        cells = []
        for gravite in _GRAVITES:
            here = [r.id for r in risques
                    if r.gravite is gravite
                    and (r.vraisemblance_residuelle if residuel else r.vraisemblance) is vraisemblance]
            cells.append(f"{' '.join(here) or '-':<14}")
        io_out(f"   {vraisemblance.value:<9}" + "".join(cells))


def print_risque(risque: RiskScenario, output: Workshop5Output, w5_input: Workshop5Input,
                 io_out: Say = print) -> None:
    """One risk as the auditor decides on it (activité 5-2)."""
    sources = {s.id: s.nom for s in w5_input.sources_risque}
    objectifs = {o.id: o.description for o in w5_input.objectifs_vises}
    modes = {m.id: m for m in w5_input.modes_operatoires}
    io_out(f"\n[{risque.id}] {risque.libelle or '(sans formulation)'}")
    io_out(f"      {sources.get(risque.source_risque_id, risque.source_risque_id)} -> "
           f"{objectifs.get(risque.objectif_vise_id, risque.objectif_vise_id)} "
           f"({risque.scenario_strategique_id})")
    io_out(f"      gravité {risque.gravite.value} · vraisemblance {risque.vraisemblance.value} · "
           f"risque {risque.niveau_risque.value if risque.niveau_risque else '?'} · "
           f"{risque.acceptabilite.value if risque.acceptabilite else '?'}")
    retenu = modes.get(risque.mode_retenu_id)
    if retenu is not None:
        io_out(f"      mode retenu {retenu.id} « {retenu.variante} » — "
               f"{len(retenu.attack_path)} étape(s)")
        for n, step in enumerate(retenu.attack_path, 1):
            io_out(f"         {n}. {step.phase or step.tactic} "
                   f"{step.technique_id} {step.technique_name} — {step.description[:80]}")
    for mode_id in risque.modes_alternatifs_ids:
        other = modes.get(mode_id)
        if other is not None:
            io_out(f"      mode alternatif {other.id} « {other.variante} » — vraisemblance "
                   f"{other.revised_likelihood.value if other.revised_likelihood else '?'}")


def print_risques(output: Workshop5Output, w5_input: Workshop5Input, io_out: Say = print) -> None:
    io_out(f"\n=== Risques ({len(output.risques)}) — du plus élevé au plus faible ===")
    for risque in output.risques:
        io_out(f"  [{risque.id}] {risque.libelle or '(sans formulation)'}")
        io_out(f"        gravité {risque.gravite.value} · vraisemblance {risque.vraisemblance.value} · "
               f"risque {risque.niveau_risque.value if risque.niveau_risque else '?'} · "
               f"{risque.acceptabilite.value if risque.acceptabilite else '?'}")


def print_plan(output: Workshop5Output, io_out: Say = print) -> None:
    """The treatment plan as the method lays it out: axis by axis, with its columns."""
    io_out(f"\n=== Plan de traitement du risque ({len(output.mesures)} mesure(s)) ===")
    for axe in AxeMesure:
        mesures = [m for m in output.mesures if m.axe is axe]
        if not mesures:
            continue
        io_out(f"\n-- {axe.value.upper()} ({len(mesures)}) --")
        for mesure in mesures:
            io_out(f"  [{mesure.id}] {mesure.libelle}")
            io_out(f"        {mesure.thematique or 'sans thématique'} · risques "
                   f"{', '.join(mesure.risques_ids) or '-'} · modes {', '.join(mesure.modes_ids) or '-'} · "
                   f"écarts {', '.join(mesure.gap_ids) or '-'}")
            io_out(f"        responsable {mesure.responsable or '—'} · coût/complexité "
                   f"{mesure.cout_complexite or '—'} · charge {mesure.charge_estimee or '—'} · échéance "
                   f"{mesure.echeance or '—'} · priorité "
                   f"{mesure.priorite.value if mesure.priorite else '—'} · {mesure.statut.value}")
            if mesure.freins:
                io_out(f"        freins : {mesure.freins}")
            if mesure.mitigation_ids_attck:
                io_out(f"        ATT&CK : {', '.join(mesure.mitigation_ids_attck)}")
            io_out(f"        {mesure.justification} (baisse revendiquée : "
                   f"{mesure.effet_vraisemblance} niveau(x))")


def print_residuel(risque: RiskScenario, io_out: Say = print) -> None:
    residuel = risque.vraisemblance_residuelle.value if risque.vraisemblance_residuelle else "?"
    niveau = risque.niveau_risque_residuel.value if risque.niveau_risque_residuel else "?"
    io_out(f"\n[{risque.id}] {risque.libelle or '(sans formulation)'}")
    io_out(f"      {risque.option_traitement.value if risque.option_traitement else '?'} · mesures "
           f"{', '.join(risque.mesures_ids) or 'aucune'}")
    io_out(f"      vraisemblance {risque.vraisemblance.value} -> {residuel} · gravité "
           f"{risque.gravite.value} (inchangée) · risque "
           f"{risque.niveau_risque.value if risque.niveau_risque else '?'} -> {niveau} · "
           f"{risque.acceptabilite_residuelle.value if risque.acceptabilite_residuelle else '?'}")
    if risque.motif_residuel:
        io_out(f"      {risque.motif_residuel}")


def print_cadre(output: Workshop5Output, io_out: Say = print) -> None:
    cadre = output.cadre_suivi
    if cadre is None:
        return
    io_out(f"\n=== Cadre de suivi — {len(cadre.indicateurs)} indicateur(s) ===")
    io_out(f"  Instance : {cadre.comite or '—'} · révision de l'étude : {cadre.cycles or '—'} · "
           f"prochaine revue : {cadre.prochaine_revue or '—'}")
    for indicateur in cadre.indicateurs:
        io_out(f"  [{indicateur.id}] {indicateur.libelle} — {indicateur.type_valeur}, cible "
               f"{indicateur.cible}, {indicateur.frequence or 'fréquence à fixer'} "
               f"({', '.join(indicateur.mesures_ids) or 'plan entier'})")


def print_summary(output: Workshop5Output, w5_input: Workshop5Input, io_out: Say = print) -> None:
    """The whole atelier as it is about to be approved."""
    io_out(f"\n=== Atelier 5 — traitement du risque · ATT&CK {output.attck_version} ===")
    print_carte(output.risques, io_out)
    print_carte(output.risques, io_out, residuel=True)
    for risque in output.risques:
        print_residuel(risque, io_out)
        io_out(f"      décision : {risque.justification_traitement or '—'}")
        io_out(f"      accepté par : {risque.accepte_par or 'PERSONNE'}")
    print_plan(output, io_out)
    print_cadre(output, io_out)

    uncovered = er_graves_non_couverts(output.couverture_er)
    if uncovered:
        io_out("\n=== Événements redoutés graves sans risque — itérer les ateliers 2 à 4 ===")
        for entry in uncovered:
            io_out(f"  {entry.evenement_redoute_id} ({entry.gravite}) {entry.description[:80]}")

    if output.elements_ecartes:
        io_out(f"\n=== Éléments écartés ({len(output.elements_ecartes)}) — avec leur raison ===")
        for element in output.elements_ecartes:
            io_out(f"  « {element.libelle or element.reference} » ({element.reference}) : {element.raison_label}")
            if element.detail:
                io_out(f"        {element.detail}")

    io_out(f"\n=== Contrôle qualité — statut : {output.quality_report.statut} ===")
    for check in output.quality_report.checks:
        marker = {"ok": "  ", "avertissement": "/!\\", "erreur": "XX "}.get(check.statut, "  ")
        io_out(f"  {marker} {check.controle} : {check.message}")
