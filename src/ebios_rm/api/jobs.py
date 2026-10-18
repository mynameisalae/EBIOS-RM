"""Mission reports take a minute or more (one model call per section): they run as background jobs
the interface polls, instead of holding a web request open.

One job at a time. Token accounting goes through a process-wide sink (agent_runtime), so two jobs
running together would write each other's tokens into the wrong mission.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ebios_rm.agent_runtime import StructuredCallFailed, set_token_sink
from ebios_rm.repositories.mission_repository import MissionRepository, connect
from ebios_rm.reporting.appraisals import Appraisal
from ebios_rm.reporting.mission_report import build_snapshot, write_mission_report, write_mission_report_file
from ebios_rm.reporting.report_agent import ReportRunner

RunnerFactory = Callable[[Callable[[str], None]], ReportRunner]


class JobBusy(RuntimeError):
    """A report is already being written."""


@dataclass
class Job:
    id: str
    mission_id: str
    status: str = "running"            # running | done | error
    lines: list[str] = field(default_factory=list)
    summary: dict | None = None
    error: str = ""
    file: Path | None = None


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._running: str | None = None

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def start_report(
        self, db_path: str, mission_id: str, runner_factory: RunnerFactory, target: Path,
        appraisals: tuple[Appraisal, ...] = (),
    ) -> Job:
        with self._lock:
            if self._running is not None:
                raise JobBusy("Un rapport est déjà en cours de rédaction.")
            job = Job(id=uuid.uuid4().hex, mission_id=mission_id)
            self._jobs[job.id] = job
            self._running = job.id
        threading.Thread(
            target=self._run, args=(job, db_path, runner_factory, target, appraisals), daemon=True,
        ).start()
        return job

    def _run(self, job: Job, db_path: str, runner_factory: RunnerFactory, target: Path,
             appraisals: tuple[Appraisal, ...]) -> None:
        repo = MissionRepository(connect(db_path))
        set_token_sink(lambda i, o, model: repo.log_tokens(
            job.mission_id, input_tokens=i, output_tokens=o, model_used=model))
        try:
            snapshot = build_snapshot(repo, job.mission_id)
            report = write_mission_report(snapshot, runner_factory(lambda line: job.lines.append(line.strip())),
                                          appraisals=appraisals)
            job.file = write_mission_report_file(report, target)
            job.summary = {
                "sections": len(report.sections),
                "statements": sum(len(s.statements) for s in report.sections),
                "corrected": report.corrected,
                "rejected": [{"section": r.section, "text": r.text, "reason": r.reason} for r in report.rejected],
                "skipped": [{"title": s.title, "reason": s.reason} for s in report.skipped],
            }
            job.status = "done"
        except StructuredCallFailed as exc:
            job.status, job.error = "error", f"Le modèle n'a pas pu rédiger une section : {exc}"
        except Exception as exc:  # noqa: BLE001 — whatever happens, the page must learn that the job ended
            job.status, job.error = "error", f"{type(exc).__name__} : {exc}"
        finally:
            set_token_sink(None)
            with self._lock:
                self._running = None
