"""Atelier 4 driven end to end: session, fan-out, batch review, coherence, approval (conception §18).

Atelier N -> Mission State -> Orchestrator -> Atelier N+1 (§10.2): this module reads
the approved ateliers 1 to 3 from the mission state, and every step it takes is
saved back there before the next one starts. Where the mission stands is read from
the saved w4_output itself — which scenarios are pending, which await the auditor,
whether coherence ran and was ruled on — so stopping anywhere and running the same
command again resumes at that point, without paying again for a call already made.

The loop is §18's, in order:
  22-24  one independent sub-agent per pending scenario, each answer checked as it returns;
  25     the auditor reviews the results together, anomalies highlighted, and confirms
         them or sends some back — to revise, or to redo — always with a reason;
  26     a cost preview before any second pass;
  27     round again while anything is pending (per-scenario cap: 3 analyses, then CONFIRMER);
  28     once stable, one coherence call; rejecting its findings reopens the loop;
  29     the final merge, then the approval gate every atelier shares.

At each decision the auditor can also question the agent about the result, grounded
in the mission context (the clarification loop of atelier 1).

Every interaction goes through injected ``io_in`` / ``io_out`` and every model
through injected runners, so the whole flow runs in tests without a terminal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ebios_rm.domain.enums import ImpactType
from ebios_rm.domain.operational_scenario import (
    STATUT_A_REFAIRE,
    STATUT_A_REVISER,
    STATUT_ANALYSE,
    STATUT_CONFIRME,
    OperationalScenario,
)
from ebios_rm.mission_context.clarification import ClarificationRunner, clarification_repl
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.orchestrator import mission_state
from ebios_rm.orchestrator.approval_cli import ApprovalLoop, ask_choice, ask_ids
from ebios_rm.repositories.attack_repository import AttackCatalogue
from ebios_rm.repositories.mission_repository import MissionRepository
from ebios_rm.services.cost_estimation_service import estimate_cost_and_time
from ebios_rm.workshops.common import AtelierDataError
from ebios_rm.workshops.workshop1_cadrage.human_interface import HumanInterface, ask_justification
from ebios_rm.workshops.workshop4_scenarios_operationnels import (
    Workshop4Input,
    Workshop4Output,
    ask_session_questions,
    assemble_output,
    build_workshop4_input,
    initial_output,
    pending_scenarios,
    run_analyses,
    run_coherence,
)
from ebios_rm.workshops.workshop4_scenarios_operationnels.agent_runner import Workshop4AgentRunner
from ebios_rm.workshops.workshop4_scenarios_operationnels.assessment import (
    MAX_ITERATIONS,
    apply_coherence,
    confirm,
    path_summary,
    send_back,
)
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import (
    COHERENCE_ECARTEE,
    CONSTAT_REVISION,
)

STAGE = "workshop_4"
RESUME_COMMAND = "python scripts/run_workshop4.py {mission_id}"

Ask = Callable[[str], str]
Say = Callable[[str], None]


class Workshop4NotReady(RuntimeError):
    """A prerequisite of atelier 4 is missing; the message says which, and what to run."""


class _Paused(Exception):
    """The auditor chose to stop here. Everything so far is saved; the same command resumes."""


def load_input(repo: MissionRepository, mission_id: str) -> tuple[MissionContext, Workshop4Input]:
    """The approved ateliers 1 to 3, read from the mission state, as the narrow atelier 4 input."""
    mission = repo.get_mission(mission_id)
    if mission is None:
        raise Workshop4NotReady(f"Mission introuvable : {mission_id}")
    mission_context = mission_state.load_mission_context(repo, mission_id)
    w1 = mission_state.load_w1_output(repo, mission_id)
    w2 = mission_state.load_w2_output(repo, mission_id)
    w3 = mission_state.load_w3_output(repo, mission_id)
    if mission_context is None or w1 is None or w2 is None or w3 is None:
        raise Workshop4NotReady(
            "Mission incomplète : il faut un Mission Context et les résultats des ateliers 1, 2 et 3.")
    if not mission_state.is_approved(repo, mission_id, mission_state.WORKSHOP_3):
        # Asked of the atelier 3 version, not of mission.status: N sub-agents built on a
        # list the auditor has not ruled on would all be redone the moment it changes (§2).
        raise Workshop4NotReady(
            f"L'atelier 3 n'est pas approuvé (statut de la mission : {mission.status}). "
            f"Approuvez-le d'abord : python scripts/run_workshop3.py {mission_id}")
    return mission_context, build_workshop4_input(mission_context, w1, w2, w3)


def run_workshop4(
    repo: MissionRepository,
    mission_id: str,
    catalogue: AttackCatalogue,
    runner: Workshop4AgentRunner,
    *,
    human: HumanInterface | None = None,
    clarifier: ClarificationRunner | None = None,
    io_in: Ask = input,
    io_out: Say = print,
) -> int:
    """Run or resume atelier 4. 0 approved, 1 stopped by the auditor (resumable).

    ``human`` holds the session (None skips it); ``clarifier`` answers the auditor's
    questions at each decision (None skips that). A failed model call or an interrupt
    propagates to the caller, everything already done being saved.
    """
    mission_context, w4_input = load_input(repo, mission_id)
    io_out(f"Entrée atelier 4 : {len(w4_input.scenarios)} scénario(s) stratégique(s), "
           f"{len(w4_input.baseline_gaps)} écart(s) du socle, {len(w4_input.biens_supports)} bien(s) support(s), "
           f"{len(w4_input.contexte)} élément(s) de contexte. ATT&CK {catalogue.version}, "
           f"{len(catalogue.techniques)} techniques actives.")
    for alert in w4_input.alertes_atelier3:
        io_out(f"  [{'BLOQUANT' if alert.bloquant else 'avertissement'}] {alert.reference} — {alert.probleme}")
    if w4_input.alertes_bloquantes:
        raise AtelierDataError(3, w4_input.alertes_bloquantes)

    saved = mission_state.load_w4_output(repo, mission_id)
    if saved is not None and mission_state.is_approved(repo, mission_id, mission_state.WORKSHOP_4):
        io_out("Atelier 4 déjà approuvé. Résultat enregistré :")
        print_summary(saved, w4_input, io_out)
        return 0

    if saved is not None:
        analysed = [s.scenario_strategique_id for s in saved.scenarios]
        if analysed != [s.id for s in w4_input.scenarios]:
            # Atelier 3 was redone and re-approved after this atelier 4 started: its
            # analyses describe a list that no longer exists.
            io_out(f"\nL'atelier 3 a changé depuis le début de l'atelier 4 : {analysed} analysés, "
                   f"{[s.id for s in w4_input.scenarios]} approuvés aujourd'hui.")
            choice = ask_choice("Recommencer l'atelier 4 sur la liste approuvée ?",
                                {"o": "oui, nouvelle tentative (l'ancienne reste dans l'historique)",
                                 "n": "non, en rester là"}, io_in, io_out)
            if choice == "n":
                return 1
            repo.log_decision(mission_id, stage=STAGE, action="restart_atelier3_modifie",
                              justification=f"Scénarios analysés {analysed}, approuvés {[s.id for s in w4_input.scenarios]}")
            saved = None
        else:
            io_out("Atelier 4 en cours — reprise là où il s'est arrêté.")

    if saved is None and human is not None:
        enriched = ask_session_questions(w4_input, human)
        answered = mission_state.persist_session_answers(
            repo, mission_id, mission_context, w4_input, enriched, stage=STAGE)
        if answered:
            io_out(f"  {answered} réponse(s) de séance enregistrée(s) dans le contexte de la mission.")
        w4_input = enriched

    flow = Workshop4Flow(repo, mission_id, mission_context, w4_input, catalogue, runner,
                         clarifier, io_in, io_out)
    return flow.run(saved)


@dataclass
class Workshop4Flow:
    repo: MissionRepository
    mission_id: str
    mission_context: MissionContext
    w4_input: Workshop4Input
    catalogue: AttackCatalogue
    runner: Workshop4AgentRunner
    clarifier: ClarificationRunner | None = None
    io_in: Ask = input
    io_out: Say = print

    def run(self, saved: Workshop4Output | None) -> int:
        try:
            output = self.advance(saved if saved is not None else self.start())
            return self.approval(output)
        except _Paused:
            self.io_out("Tout est enregistré. Pour reprendre : "
                        + RESUME_COMMAND.format(mission_id=self.mission_id))
            return 1

    def start(self) -> Workshop4Output:
        output = initial_output(self.w4_input, self.catalogue.version)
        mission_state.save_w4_output(self.repo, self.mission_id, output)
        self.repo.set_attck_version(self.mission_id, self.catalogue.version)
        self.repo.set_status(self.mission_id, "w4_in_progress")
        return output

    def checkpoint(self, output: Workshop4Output) -> Workshop4Output:
        mission_state.checkpoint_w4_output(self.repo, self.mission_id, output)
        return output

    # --- the loop (§18 steps 22-29) -----------------------------------------

    def advance(self, output: Workshop4Output) -> Workshop4Output:
        """Take the output from wherever it stands to the final merge, saving every step."""
        while True:
            if pending_scenarios(output):
                output = self.analyse(output)
            elif any(s.statut == STATUT_ANALYSE for s in output.scenarios):
                output = self.review(output)
            elif output.coherence is None:
                self.io_out("\n=== Vérification de cohérence de l'ensemble ===")
                output = self.checkpoint(run_coherence(self.w4_input, output, self.runner))
            elif not output.coherence.decision:
                output = self.decide_coherence(output)
            else:
                return self.checkpoint(assemble_output(self.w4_input, output, self.catalogue))

    def analyse(self, output: Workshop4Output) -> Workshop4Output:
        pending = pending_scenarios(output)
        estimate = estimate_cost_and_time(len(pending))
        redo = [s.id for s in pending if s.iterations]
        self.io_out(f"\n=== Analyse de {len(pending)} scénario(s) — un sous-agent indépendant chacun ===")
        self.io_out(f"Estimation : {estimate.llm_calls} appel(s), ~{estimate.input_tokens} tokens en entrée, "
                    f"~{estimate.output_tokens} en sortie, ~{max(1, round(estimate.seconds / 60))} min.")
        if redo:
            # §18 step 26: nothing is paid for twice without the auditor seeing the price first.
            one = estimate_cost_and_time(1)
            self.io_out(f"Seconde analyse de {', '.join(redo)} — ~{one.input_tokens + one.output_tokens} tokens "
                        "par scénario.")
            if ask_choice("Lancer la reprise ?", {"o": "oui, lancer", "n": "non, pas maintenant"},
                          self.io_in, self.io_out) == "n":
                raise _Paused

        waiting = {s.id for s in pending}

        def saved(current: Workshop4Output) -> None:
            self.checkpoint(current)
            for scenario in current.scenarios:
                if scenario.id in waiting and scenario.statut == STATUT_ANALYSE:
                    waiting.discard(scenario.id)
                    self.io_out(f"   {scenario.id} analysé et enregistré : {len(scenario.attack_path)} étape(s), "
                                f"{len(scenario.blocking_anomalies)} anomalie(s) bloquante(s).")

        return run_analyses(self.w4_input, output, self.runner, self.catalogue, checkpoint=saved)

    def review(self, output: Workshop4Output) -> Workshop4Output:
        """The batch review (§18 step 25): all results together, anomalies first in sight."""
        awaiting = [s for s in output.scenarios if s.statut == STATUT_ANALYSE]
        confirmed = [s for s in output.scenarios if s.statut == STATUT_CONFIRME]
        self.io_out(f"\n=== Revue des analyses — {len(awaiting)} à examiner"
                    + (f", {len(confirmed)} déjà confirmée(s)" if confirmed else "") + " ===")
        for scenario in confirmed:
            self.io_out(f"  [{scenario.id}] confirmé — {path_summary(scenario)}")
        for scenario in awaiting:
            print_scenario(scenario, self.w4_input, self.io_out)
        self.clarify(output)

        known = {s.id for s in output.scenarios}
        while True:
            self.io_out("\n[Entrée] confirmer ces analyses ; les identifiants à renvoyer à l'agent "
                        "(ex. SO-02, SO-04) ; 'q' pour s'arrêter ici.")
            raw = self.io_in("> ").strip()
            if raw.casefold() == "q":
                raise _Paused
            ids = [p.strip().upper() for p in raw.replace(";", ",").split(",") if p.strip()]
            unknown = [i for i in ids if i not in known]
            if not unknown:
                break
            self.io_out(f"    Identifiant inconnu : {', '.join(unknown)}.")

        for scenario_id in ids:
            scenario = next(s for s in output.scenarios if s.id == scenario_id)
            if not self.below_cap(scenario):
                continue
            mode = ask_choice(
                f"{scenario_id} — comment l'agent doit-il le reprendre ?",
                {"r": "réviser : corriger cette analyse sur vos remarques",
                 "x": "rejeter et refaire : construire un autre mode opératoire"},
                self.io_in, self.io_out)
            motif = ask_justification(f"Motif pour {scenario_id} (obligatoire, §8) : ", self.io_in, self.io_out)
            statut = STATUT_A_REVISER if mode == "r" else STATUT_A_REFAIRE
            output = send_back(output, [scenario_id], motif, statut)
            self.repo.log_decision(self.mission_id, stage=STAGE, action=f"{statut}:{scenario_id}", justification=motif)

        to_confirm = [s for s in awaiting if s.id not in ids]
        blocked = [s for s in to_confirm if s.blocking_anomalies]
        if blocked:
            self.io_out("\nAnomalies bloquantes sur : " + ", ".join(s.id for s in blocked))
            self.io_out("Tapez CONFIRMER pour les confirmer malgré tout ; toute autre saisie les laisse "
                        "en attente de votre décision.")
            if self.io_in("> ").strip() == "CONFIRMER":
                reason = ask_justification("Motif (obligatoire, §8) : ", self.io_in, self.io_out)
                self.repo.log_decision(self.mission_id, stage=STAGE,
                                       action="anomalies_levees:" + ",".join(s.id for s in blocked),
                                       justification=reason)
            else:
                to_confirm = [s for s in to_confirm if not s.blocking_anomalies]
        if to_confirm:
            output = confirm(output, [s.id for s in to_confirm])
            self.repo.log_decision(self.mission_id, stage=STAGE,
                                   action="analyses_confirmees:" + ",".join(s.id for s in to_confirm),
                                   justification="Confirmées par l'auditeur")
        return self.checkpoint(output)

    def decide_coherence(self, output: Workshop4Output) -> Workshop4Output:
        """The auditor's ruling on the coherence findings (§18 step 28)."""
        review = output.coherence
        by_id = {s.id: s for s in output.scenarios}
        self.io_out(f"\n=== Cohérence d'ensemble — {len(review.constats)} constat(s) ===")
        for n, finding in enumerate(review.constats, 1):
            self.io_out(f"[{n}] {finding.label} — {', '.join(finding.scenario_ids)}")
            self.io_out(f"    {finding.explication}")
            if finding.type == CONSTAT_REVISION:
                current = by_id[finding.scenario_a_reviser].revised_likelihood
                self.io_out(f"    Proposition : {finding.scenario_a_reviser} "
                            f"{current.value if current else '—'} -> {finding.vraisemblance_proposee}")
        self.clarify(output)

        choice = ask_choice("Que faire de ces constats ?", {
            "a": "les accepter — les révisions proposées sont appliquées",
            "r": "rouvrir des scénarios pour que l'agent les reprenne",
            "i": "les écarter (motif obligatoire)",
            "q": "en rester là pour l'instant",
        }, self.io_in, self.io_out)
        if choice == "q":
            raise _Paused
        if choice == "a":
            self.repo.log_decision(self.mission_id, stage=STAGE, action="coherence_acceptee",
                                   justification=f"{len(review.constats)} constat(s) accepté(s)")
            return self.checkpoint(apply_coherence(output))
        if choice == "i":
            reason = ask_justification("Motif (obligatoire, §8) : ", self.io_in, self.io_out)
            self.repo.log_decision(self.mission_id, stage=STAGE, action="coherence_ecartee", justification=reason)
            decided = review.model_copy(update={"decision": COHERENCE_ECARTEE, "justification": reason})
            return self.checkpoint(output.model_copy(update={"coherence": decided}))

        cited = sorted({i for f in review.constats for i in f.scenario_ids})
        ids = ask_ids(f"Scénarios à rouvrir ([Entrée] = ceux des constats : {', '.join(cited)}) :",
                      set(by_id), self.io_in, self.io_out) or cited
        motif = ask_justification("Motif (obligatoire, §8) : ", self.io_in, self.io_out)
        reopened = output
        for scenario_id in ids:
            if not self.below_cap(by_id[scenario_id]):
                continue
            findings = "; ".join(f.explication for f in review.constats if scenario_id in f.scenario_ids)
            reopened = send_back(reopened, [scenario_id],
                                 f"{motif} (constat de cohérence : {findings})" if findings else motif,
                                 STATUT_A_REVISER)
        self.repo.log_decision(self.mission_id, stage=STAGE, action="coherence_rouverte:" + ",".join(ids),
                               justification=motif)
        # send_back voids the coherence review; if every reopening was declined, keep it for a ruling.
        if reopened is output:
            return output
        return self.checkpoint(reopened)

    def below_cap(self, scenario: OperationalScenario) -> bool:
        """§18 step 27: three analyses per scenario, then only on a typed confirmation."""
        if scenario.iterations < MAX_ITERATIONS:
            return True
        self.io_out(f"\n{scenario.id} a déjà été analysé {scenario.iterations} fois (plafond de "
                    f"{MAX_ITERATIONS}, §18). Tapez CONFIRMER pour le renvoyer malgré tout ; toute autre "
                    "saisie le laisse tel quel.")
        return self.io_in("> ").strip() == "CONFIRMER"

    def clarify(self, output: Workshop4Output) -> None:
        if self.clarifier is not None:
            clarification_repl(self.clarifier, self.mission_context, output,
                               io_in=self.io_in, io_out=self.io_out)

    # --- the approval gate every atelier shares ------------------------------

    def approval(self, output: Workshop4Output) -> int:
        return ApprovalLoop(
            repo=self.repo,
            mission_id=self.mission_id,
            stage=STAGE,
            workshop_number=mission_state.WORKSHOP_4,
            label="l'atelier 4",
            print_output=self.show_final,
            rerun=self.redo,
            save=self.save_edit,
            model_cls=Workshop4Output,
            edit_examples="scenarios.0.revised_likelihood        scenarios.1.attack_path.2.technique_id",
            block_labels={str(n): (s.id, f"{s.id} — {s.resume[:80] or path_summary(s)}")
                          for n, s in enumerate(output.scenarios, 1)},
            io_in=self.io_in,
            io_out=self.io_out,
        ).run(output)

    def show_final(self, output: Workshop4Output) -> None:
        print_summary(output, self.w4_input, self.io_out)
        self.clarify(output)

    def redo(self, notes: list[str], blocks: set[str] | None, previous: Workshop4Output) -> Workshop4Output:
        """A rejection at the approval gate reopens the scenarios the auditor names — as a new version."""
        ids = sorted(blocks) if blocks else [s.id for s in previous.scenarios]
        reopened = send_back(previous, ids, notes[-1] if notes else "Relance demandée par l'auditeur",
                             STATUT_A_REVISER)
        mission_state.save_w4_output(self.repo, self.mission_id, reopened)
        self.repo.set_status(self.mission_id, "w4_in_progress")
        return self.advance(reopened)

    def save_edit(self, corrected: Workshop4Output) -> Workshop4Output:
        final = assemble_output(self.w4_input, corrected, self.catalogue)
        mission_state.save_w4_output(self.repo, self.mission_id, final)
        return final


# --- Printing --------------------------------------------------------------

_MARK = {True: "XX ", False: "/!\\"}


def print_scenario(scenario: OperationalScenario, w4_input: Workshop4Input, io_out: Say = print) -> None:
    """One analysis as the auditor reviews it: anomalies, path, likelihood, gaps."""
    sources = {s.id: s.nom for s in w4_input.sources_risque}
    objectifs = {o.id: o.description for o in w4_input.objectifs_vises}
    weakness = {g.gap_id: g.weakness for g in w4_input.baseline_gaps}
    revised = scenario.revised_likelihood.value if scenario.revised_likelihood else "?"
    level = scenario.revised_risk_level.value if scenario.revised_risk_level else "non calculé"

    io_out(f"\n[{scenario.id}] {scenario.scenario_strategique_id} · "
           f"{sources.get(scenario.source_risque_id, scenario.source_risque_id)} -> "
           f"{objectifs.get(scenario.objectif_vise_id, scenario.objectif_vise_id)}")
    io_out(f"      gravité {scenario.gravite.value} · vraisemblance {scenario.vraisemblance_initiale.value} -> "
           f"{revised} · niveau de risque {level} · analyse n°{scenario.iterations}")
    for anomaly in sorted(scenario.anomalies, key=lambda a: not a.bloquante):
        io_out(f"      {_MARK[anomaly.bloquante]} [{anomaly.code}] {anomaly.message}")
    if scenario.resume:
        io_out(f"      {scenario.resume}")
    for n, step in enumerate(scenario.attack_path, 1):
        technique = f"{step.technique_id} {step.technique_name}" if step.technique_id else "(sans technique ATT&CK)"
        support = f"  [{step.bien_support_id}]" if step.bien_support_id else ""
        io_out(f"        {n}. {step.phase or step.tactic:<10} {technique}{support}")
        io_out(f"           {step.description}")
        if step.justification:
            io_out(f"           ↳ {step.justification}")
    if scenario.likelihood_revision_reason:
        io_out(f"      Motif de révision : {scenario.likelihood_revision_reason}")

    counts = {t: 0 for t in ImpactType}
    for entry in scenario.baseline_gaps_considered:
        counts[entry.impact_type] += 1
    if scenario.baseline_gaps_considered:
        io_out(f"      Écarts du socle : {counts[ImpactType.INCREASES_LIKELIHOOD]} facilitent, "
               f"{counts[ImpactType.INCREASES_IMPACT]} aggravent, {counts[ImpactType.NO_IMPACT]} sans effet, "
               f"{counts[ImpactType.NOT_RELEVANT]} hors sujet")
        for entry in scenario.baseline_gaps_considered:
            if entry.impact_type in {ImpactType.INCREASES_LIKELIHOOD, ImpactType.INCREASES_IMPACT}:
                io_out(f"        + {entry.gap_id} {weakness.get(entry.gap_id, '')[:70]}")
                io_out(f"          {entry.impact_on_scenario}")
    if scenario.new_baseline_gap_identified:
        gap = scenario.new_baseline_gap_identified
        io_out(f"      Nouvel écart proposé : {gap.weakness} — {gap.justification} "
               f"({', '.join(gap.derived_from_fact_fields)}) — à confirmer, l'atelier 1 n'est pas modifié.")
    if scenario.motifs_auditeur:
        io_out(f"      Vos motifs précédents : {' | '.join(scenario.motifs_auditeur)}")


def print_summary(output: Workshop4Output, w4_input: Workshop4Input, io_out: Say = print) -> None:
    """The whole atelier as it is about to be approved."""
    sources = {s.id: s.nom for s in w4_input.sources_risque}
    io_out(f"\n=== Atelier 4 — scénarios opérationnels ({len(output.scenarios)}) · ATT&CK {output.attck_version} ===")
    for scenario in output.scenarios:
        revised = scenario.revised_likelihood.value if scenario.revised_likelihood else "?"
        level = scenario.revised_risk_level.value if scenario.revised_risk_level else "?"
        io_out(f"  [{scenario.id}] {scenario.scenario_strategique_id} {sources.get(scenario.source_risque_id, '')}"
               f" · gravité {scenario.gravite.value} · {scenario.vraisemblance_initiale.value} -> {revised}"
               f" · risque {level} · {scenario.statut}")
        io_out(f"        {path_summary(scenario)}")
        if scenario.resume:
            io_out(f"        {scenario.resume}")

    if output.coherence is not None:
        io_out(f"\n=== Cohérence — {len(output.coherence.constats)} constat(s), décision « "
               f"{output.coherence.decision or 'en attente'} » ===")
        for finding in output.coherence.constats:
            io_out(f"  {finding.label} ({', '.join(finding.scenario_ids)}) : {finding.explication}")
        if output.coherence.justification:
            io_out(f"  Motif : {output.coherence.justification}")

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
