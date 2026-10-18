"""Drive a mission from the web, exactly as the terminal does.

The terminal flows (intake, the five ateliers, the approval gates) already take their input and
output as plain callables. This module gives them a *channel* instead of a keyboard and a screen:
every line they print goes to a journal the page reads, and every question they ask waits until the
auditor answers on the page. Nothing in the flows changes — the web is just another way to type.

One session at a time: token accounting goes through a process-wide sink (agent_runtime), so two
missions running together would write each other's tokens into the wrong mission.
"""

from __future__ import annotations

import asyncio
import re
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ebios_rm.agent_runtime import set_token_sink
from ebios_rm.orchestrator import mission_state, state_machine
from ebios_rm.orchestrator.workshop1_runner import Workshop1Runner
from ebios_rm.repositories.mission_repository import MissionRepository, connect


class PilotBusy(RuntimeError):
    """A mission is already being driven."""


class Interrupted(KeyboardInterrupt):
    """The auditor pressed « Interrompre » — what Ctrl+C is in the terminal."""


_OPTION = re.compile(r"^\s+\[([^\]]+)\]\s+(.+)$")


@dataclass
class Prompt:
    id: int
    text: str
    kind: str                                   # text | yesno | choice
    options: list[dict[str, str]] = field(default_factory=list)
    confirm: bool = False                       # the flow wants the word CONFIRMER


class Channel:
    """The journal and the pending question of one session."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.prompt: Prompt | None = None
        self._answer: str | None = None
        self._cond = threading.Condition()
        self._next_prompt = 1
        self._interrupted = False

    # --- what the flows call -------------------------------------------------------------

    def say(self, text: object = "") -> None:
        with self._cond:
            self.lines.extend(str(text).split("\n"))

    def ask(self, prompt: str = "") -> str:
        with self._cond:
            if self._interrupted:
                raise Interrupted
            self.prompt = self._describe(prompt)
            self._next_prompt += 1
            self._answer = None
            self._cond.notify_all()
            while self._answer is None:
                if self._interrupted:
                    self.prompt = None
                    raise Interrupted
                self._cond.wait(timeout=0.5)
            answer, self._answer, self.prompt = self._answer, None, None
        self.say(f"> {answer}" if answer else "> (entrée)")
        return answer

    # --- what the web calls --------------------------------------------------------------

    def answer(self, prompt_id: int, text: str) -> bool:
        with self._cond:
            if self.prompt is None or self.prompt.id != prompt_id or self._answer is not None:
                return False
            self._answer = text
            self._cond.notify_all()
            return True

    def interrupt(self) -> None:
        with self._cond:
            self._interrupted = True
            self._cond.notify_all()

    def raise_if_interrupted(self) -> None:
        """Called after every model call (through the token sink): « Interrompre » then takes effect within seconds."""
        if self._interrupted:
            raise Interrupted

    def snapshot(self, after: int = 0) -> dict:
        with self._cond:
            prompt = None
            if self.prompt is not None and self._answer is None:
                prompt = {"id": self.prompt.id, "text": self.prompt.text, "kind": self.prompt.kind,
                          "options": self.prompt.options, "confirm": self.prompt.confirm}
            return {"lines": self.lines[after:], "next": len(self.lines), "prompt": prompt}

    # --- reading a prompt the way a person would -----------------------------------------

    def _describe(self, text: str) -> Prompt:
        recent = self.lines[-40:]
        options: list[dict[str, str]] = []
        for line in reversed(recent):                       # the block of "[k] label" lines just above
            match = _OPTION.match(line)
            if match:
                options.insert(0, {"key": match.group(1).strip(), "label": match.group(2).strip()})
            elif options:
                break
            elif line.strip():
                break
        confirm = any("CONFIRMER" in line for line in recent[-6:]) or "CONFIRMER" in text
        if re.search(r"\[\s*oui\s*/\s*non\s*\]", text, re.IGNORECASE):
            return Prompt(self._next_prompt, text, "yesno", [{"key": "oui", "label": "Oui"}, {"key": "non", "label": "Non"}])
        if options and not text.strip().rstrip(":").strip("> ").strip():
            return Prompt(self._next_prompt, text, "choice", options, confirm)
        return Prompt(self._next_prompt, text, "text", [], confirm)


@dataclass
class Session:
    id: str
    mission_id: str
    kind: str                                   # intake | run
    channel: Channel = field(default_factory=Channel)
    status: str = "running"                     # running | done | stopped | error
    error: str = ""
    final_status: str = ""
    files: dict[str, Path] = field(default_factory=dict)   # the two reports, once the five ateliers are approved


Workshops = Callable[[MissionRepository, Channel], dict]
IntakeFactory = Callable[[MissionRepository, str, "Channel"], None]


def _reference_repo():
    from ebios_rm.db.loader import build_reference_db  # noqa: PLC0415
    from ebios_rm.repositories.reference_repository import ReferenceRepository  # noqa: PLC0415

    return ReferenceRepository(build_reference_db(":memory:"))


class WebWorkshop1Runner(Workshop1Runner):
    """Atelier 1 with its two keyboard steps (controls check, unverified review) on the channel."""

    def __init__(self, reference_repo, repo: MissionRepository, channel: Channel) -> None:
        super().__init__(reference_repo, repo)
        self._channel = channel

    def check_controls_available(self, mission_context, mission_id):
        from ebios_rm.workshops.workshop1_cadrage.assessment import frameworks_without_controls  # noqa: PLC0415

        missing = frameworks_without_controls(mission_context.applicable_frameworks, self._reference_repo)
        if not missing:
            return mission_context
        self._channel.say("=== ARRÊT : référentiels sans contrôles chargés ===")
        for framework in missing:
            self._channel.say(f"   - {framework}")
        self._channel.say("L'agent n'invente jamais un texte de référentiel : chargez les contrôles de ces "
                          "référentiels, puis reprenez la mission.")
        self._repo.set_status(mission_id, "blocked_missing_controls")
        return None

    async def run(self, input, mission_id):
        from ebios_rm.agent_runtime import StructuredCallFailed  # noqa: PLC0415
        from ebios_rm.orchestrator.signals import WorkshopBlocked  # noqa: PLC0415
        from ebios_rm.workshops.workshop1_cadrage.agent import AgnoWorkshop1Runner  # noqa: PLC0415
        from ebios_rm.workshops.workshop1_cadrage.workshop import run_workshop1  # noqa: PLC0415

        try:
            output = run_workshop1(input, AgnoWorkshop1Runner(), self._reference_repo)
        except StructuredCallFailed as exc:
            raise WorkshopBlocked(f"Échec du modèle pendant l'atelier 1 : {exc}") from exc
        self._cli._review_unverified(self._repo, mission_id, output, self._channel.ask, self._channel.say)
        return output


def default_workshops(repo: MissionRepository, channel: Channel, seance: bool = False) -> dict:
    """The five real ateliers, wired to the channel instead of the keyboard.

    ``seance`` adds the client session of ateliers 4 and 5 (the questions the terminal asks unless
    ``--no-session``): the auditor answers, asks what a question means, or forces an answer with « ! ».
    """
    from ebios_rm.orchestrator.workshop2_runner import Workshop2Runner  # noqa: PLC0415
    from ebios_rm.orchestrator.workshop3_runner import Workshop3Runner  # noqa: PLC0415
    from ebios_rm.orchestrator.workshop4_runner import Workshop4Runner  # noqa: PLC0415
    from ebios_rm.orchestrator.workshop5_runner import Workshop5Runner  # noqa: PLC0415

    human = clarifier = None
    if seance:
        from ebios_rm.mission_context.clarification_agent import AgnoClarificationRunner  # noqa: PLC0415
        from ebios_rm.mission_context.conversation import AgnoConversationRunner  # noqa: PLC0415
        from ebios_rm.workshops.workshop1_cadrage.human_interface import ConversationalHumanInterface  # noqa: PLC0415

        human = ConversationalHumanInterface(AgnoConversationRunner(), io_in=channel.ask, io_out=channel.say)
        clarifier = AgnoClarificationRunner()
    return {
        1: WebWorkshop1Runner(_reference_repo(), repo, channel),
        2: Workshop2Runner(),
        3: Workshop3Runner(io_in=channel.ask, io_out=channel.say),
        4: Workshop4Runner(repo, io_in=channel.ask, io_out=channel.say, human=human, clarifier=clarifier),
        5: Workshop5Runner(repo, io_in=channel.ask, io_out=channel.say, human=human, clarifier=clarifier),
    }


def produce_reports(repo: MissionRepository, mission_id: str, channel: Channel, session: Session,
                    reports_dir: Path, report_factory) -> None:
    """The mission ends with its two documents: the annex (no model) and the mission report (checked)."""
    from ebios_rm.reporting.audit_annex import build_audit_annex, collect_audit_annex_data  # noqa: PLC0415
    from ebios_rm.reporting.mission_report import build_snapshot, write_mission_report, write_mission_report_file  # noqa: PLC0415

    channel.say("=== Production des rapports ===")
    reports_dir.mkdir(parents=True, exist_ok=True)
    annex = reports_dir / f"annexe_audit_{mission_id[:8]}.docx"
    build_audit_annex(collect_audit_annex_data(repo, mission_id)).save(str(annex))
    session.files["annexe"] = annex
    channel.say("Annexe d'audit produite (sans modèle).")
    try:
        runner = report_factory(lambda line: channel.say(line.strip()))
        report = write_mission_report(build_snapshot(repo, mission_id), runner)
        target = write_mission_report_file(report, reports_dir / f"rapport_mission_{mission_id[:8]}.docx")
    except Exception as exc:  # noqa: BLE001 — the annex stands; say why the report did not
        channel.say(f"Rapport de mission non produit : {type(exc).__name__} : {exc}")
        return
    session.files["rapport"] = target
    statements = sum(len(s.statements) for s in report.sections)
    channel.say(f"Rapport de mission produit : {len(report.sections)} section(s), {statements} affirmation(s) retenue(s), "
                f"{report.corrected} corrigée(s), {len(report.rejected)} écartée(s).")


def default_intake(repo: MissionRepository, mission_id: str, channel: Channel, files: list[Path]) -> None:
    """Questionnaire (+ supporting documents) to a validated Mission Context — the terminal's intake."""
    from ebios_rm.mission_context.conversation import AgnoConversationRunner  # noqa: PLC0415
    from ebios_rm.mission_context.ingestion_agent import AgnoIngestionRunner  # noqa: PLC0415
    from ebios_rm.mission_context.mission_context import assemble_from_facts  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.auditor_review import AgnoAuditorReviewRunner  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.human_interface import ConversationalHumanInterface  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.intake_ingestion import complete_intake_from_documents  # noqa: PLC0415
    from ebios_rm.workshops.workshop1_cadrage.intake_review import AgnoIntakeReviewRunner  # noqa: PLC0415

    intake_doc, *supporting = files
    human = ConversationalHumanInterface(AgnoConversationRunner(), io_in=channel.ask, io_out=channel.say)
    channel.say("=== Collecte du contexte ===")
    channel.say(f"Questionnaire : {intake_doc.name}" + (f" · {len(supporting)} document(s) joint(s)" if supporting else ""))

    def checkpoint(facts):
        mission_state.checkpoint_mission_context(repo, mission_id, assemble_from_facts(facts))

    context = complete_intake_from_documents(
        intake_doc, supporting, AgnoIngestionRunner(), human, AgnoAuditorReviewRunner(),
        checkpoint=checkpoint, intake_reviewer=AgnoIntakeReviewRunner(),
    )
    mission_state.save_mission_context(repo, mission_id, context)
    repo.set_status(mission_id, state_machine.MissionStatus.CONTEXT_READY)
    channel.say(f"Contexte prêt : {len(context.facts)} faits validés.")


def _approve(channel: Channel):
    from ebios_rm.workshops.workshop1_cadrage.human_interface import approve_workshop  # noqa: PLC0415

    return lambda label: approve_workshop(label, io_in=channel.ask, io_out=channel.say)


def _confirm(channel: Channel):
    def confirm(label: str) -> bool:
        channel.say(f"Plafond de {mission_state.ROLLBACK_CAP} versions atteint pour {label}.")
        channel.say("Une nouvelle reprise est inhabituelle. Tapez CONFIRMER pour relancer malgré tout,")
        channel.say("ou toute autre saisie pour arrêter et conserver la dernière version.")
        return channel.ask("> ").strip() == "CONFIRMER"

    return confirm


def _status(repo: MissionRepository, mission_id: str) -> str:
    mission = repo.get_mission(mission_id)
    return mission.status if mission else ""


def _unstick(repo: MissionRepository, mission_id: str) -> None:
    """A crash or an interruption mid-atelier leaves 'wN_running': ateliers 1-3 cannot resume, restart them."""
    mission = repo.get_mission(mission_id)
    if mission is None:
        return
    for n in (1, 2, 3):
        if mission.status in (state_machine.running(n), state_machine.paused(n)):
            repo.set_status(mission_id, state_machine.MissionStatus.CONTEXT_READY if n == 1
                            else state_machine.approved(n - 1))


class PilotRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._active: str | None = None

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    @property
    def busy(self) -> bool:
        return self._active is not None

    def active_for(self, mission_id: str) -> Session | None:
        for session in reversed(list(self._sessions.values())):
            if session.mission_id == mission_id and session.status == "running":
                return session
        return None

    def start(self, db_path: str, mission_id: str, *, kind: str, workshops: Workshops = default_workshops,
              intake: Callable[..., None] | None = None, files: list[Path] | None = None, seance: bool = False,
              reports_dir: Path | None = None, report_factory=None) -> Session:
        with self._lock:
            if self._active is not None:
                raise PilotBusy("Une mission est déjà en cours de pilotage : interrompez-la ou attendez qu'elle s'arrête.")
            session = Session(id=uuid.uuid4().hex, mission_id=mission_id, kind=kind)
            self._sessions[session.id] = session
            self._active = session.id
        threading.Thread(target=self._run, args=(session, db_path, workshops, intake, files or [], seance,
                                                 reports_dir, report_factory), daemon=True).start()
        return session

    def stop(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None or session.status != "running":
            return False
        session.channel.interrupt()
        return True

    @staticmethod
    def _drive(repo: MissionRepository, mission_id: str, channel: Channel, workshops: Workshops,
               seance: bool = False) -> None:
        """Hand the mission to the Orchestrator, from whatever status it is in."""
        from ebios_rm.orchestrator.orchestrator import Orchestrator  # noqa: PLC0415

        status = _status(repo, mission_id)
        try:
            action = state_machine.next_action(status).action
        except ValueError:
            action = "unknown"
        if action in ("blocked", "unknown", "start_intake", "resume_intake"):
            channel.say(f"La mission ne peut pas avancer d'ici (statut : {status}) : la collecte du contexte "
                        "n'est pas terminée, ou la mission est bloquée.")
            return

        ateliers = workshops(repo, channel, seance=True) if seance else workshops(repo, channel)
        first = ateliers.get(1)
        if status == state_machine.MissionStatus.CONTEXT_READY and hasattr(first, "check_controls_available"):
            context = mission_state.load_mission_context(repo, mission_id)
            checked = first.check_controls_available(context, mission_id) if context is not None else None
            if checked is None:
                return
            if checked is not context:
                mission_state.save_mission_context(repo, mission_id, checked)
        orchestrator = Orchestrator(repo, ateliers, approve=_approve(channel), reinforced_confirm=_confirm(channel))
        asyncio.run(orchestrator.run_mission(mission_id))

    def _run(self, session: Session, db_path: str, workshops: Workshops, intake, files: list[Path], seance: bool,
             reports_dir: Path | None, report_factory) -> None:
        channel = session.channel
        repo = MissionRepository(connect(db_path))
        mission_id = session.mission_id

        def sink(input_tokens: int, output_tokens: int, model: str) -> None:
            repo.log_tokens(mission_id, input_tokens=input_tokens, output_tokens=output_tokens, model_used=model)
            channel.raise_if_interrupted()      # a model call just ended: this is the moment to stop

        set_token_sink(sink)
        try:
            if session.kind == "intake":
                (intake or default_intake)(repo, mission_id, channel, files)
            _unstick(repo, mission_id)
            self._drive(repo, mission_id, channel, workshops, seance)
            if _status(repo, mission_id) in (state_machine.approved(5), state_machine.MissionStatus.ALL_APPROVED)                     and reports_dir is not None and report_factory is not None:
                produce_reports(repo, mission_id, channel, session, reports_dir, report_factory)
            session.final_status = _status(repo, mission_id)
            session.status = "done"
            channel.say(f"=== Fin de la session — statut de la mission : {session.final_status} ===")
        except Interrupted:
            session.status = "stopped"
            session.final_status = _status(repo, mission_id)
            channel.say("=== Session interrompue — tout ce qui a été enregistré est conservé ===")
        except BaseException as exc:  # noqa: BLE001 — whatever happens, the page must learn that the session ended
            session.status, session.error = "error", f"{type(exc).__name__} : {exc}"
            channel.say(f"=== Erreur : {session.error} ===")
        finally:
            set_token_sink(None)
            with self._lock:
                self._active = None
