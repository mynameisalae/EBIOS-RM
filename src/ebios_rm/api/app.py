"""The web interface's server: reads the mission database, serves the built interface, and produces
the two reports (conception §20) on request.

    create_app(db_path)  ->  a FastAPI app; ``python scripts/run_interface.py`` starts it.
"""

from __future__ import annotations

import tempfile
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ebios_rm.api import views
from ebios_rm.api.jobs import JobBusy, JobRegistry, RunnerFactory
from ebios_rm.api.pilot import PilotBusy, PilotRegistry, Workshops, default_workshops
from ebios_rm.repositories.mission_repository import MissionRepository, connect
from ebios_rm.reporting.appraisals import AnnexReadError, read_appraisals
from ebios_rm.reporting.audit_annex import build_audit_annex, collect_audit_annex_data
from ebios_rm.reporting.pdf import PdfUnavailable, convert_to_pdf

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF = "application/pdf"


def _default_runner_factory(progress):
    from ebios_rm.reporting.report_agent import AgnoReportRunner  # noqa: PLC0415

    return AgnoReportRunner(progress=progress)


def _require_model_key() -> None:
    from ebios_rm.config import load_settings  # noqa: PLC0415

    if not load_settings().openrouter_api_key:
        raise HTTPException(400, "OPENROUTER_API_KEY n'est pas défini : renseignez-le dans .env pour rédiger le rapport.")


class Answer(BaseModel):
    prompt_id: int
    text: str = ""


class PilotStart(BaseModel):
    seance: bool = False        # run the client session of ateliers 4 and 5


def _pdf_of(path: Path) -> Path:
    try:
        return convert_to_pdf(path)
    except PdfUnavailable as exc:
        raise HTTPException(501, str(exc)) from exc


def create_app(
    db_path: str, *, attack_db_path: str | None = None, reports_dir: str | Path = "data/reports",
    ui_dir: str | Path | None = None, runner_factory: RunnerFactory | None = None,
    uploads_dir: str | Path = "data/uploads", workshops: Workshops | None = None, intake=None,
) -> FastAPI:
    app = FastAPI(title="EBIOS RM Agent — OGSBC", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                                                      "http://localhost:5174", "http://127.0.0.1:5174"],
                       allow_methods=["*"], allow_headers=["*"])
    jobs = JobRegistry()
    pilots = PilotRegistry()
    reports = Path(reports_dir)
    factory = runner_factory or _default_runner_factory

    def repo() -> MissionRepository:
        return MissionRepository(connect(db_path))

    def known_mission(mission_id: str) -> MissionRepository:
        r = repo()
        if r.get_mission(mission_id) is None:
            raise HTTPException(404, "Mission introuvable.")
        return r

    @app.get("/api/missions")
    def missions():
        return views.list_missions(repo())

    @app.get("/api/missions/{mission_id}")
    def mission(mission_id: str):
        overview = views.mission_overview(repo(), mission_id)
        if overview is None:
            raise HTTPException(404, "Mission introuvable.")
        return overview

    @app.get("/api/missions/{mission_id}/ateliers/{n}")
    def atelier(mission_id: str, n: int):
        detail = views.atelier_detail(repo(), mission_id, n)
        if detail is None:
            raise HTTPException(404, "Atelier introuvable.")
        return detail

    @app.get("/api/missions/{mission_id}/annexe")
    def annexe(mission_id: str, format: str = "docx"):
        r = known_mission(mission_id)
        document = build_audit_annex(collect_audit_annex_data(r, mission_id))
        if format == "pdf":
            target = reports / f"annexe_audit_{mission_id[:8]}.docx"
            target.parent.mkdir(parents=True, exist_ok=True)
            document.save(str(target))
            pdf = _pdf_of(target)
            return FileResponse(pdf, media_type=PDF, filename=pdf.name)
        buffer = BytesIO()
        document.save(buffer)
        return Response(buffer.getvalue(), media_type=DOCX,
                        headers={"Content-Disposition": f'attachment; filename="annexe_audit_{mission_id[:8]}.docx"'})

    @app.post("/api/missions/{mission_id}/rapport")
    async def write_report(mission_id: str, annexe: UploadFile | None = File(default=None)):
        r = known_mission(mission_id)
        if not views.mission_overview(r, mission_id)["can_write_report"]:
            raise HTTPException(409, "Aucun atelier approuvé : il n'y a encore rien à rapporter.")
        if runner_factory is None:
            _require_model_key()
        appraisals = ()
        if annexe is not None and annexe.filename:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(await annexe.read())
            try:
                reading = read_appraisals(tmp.name)
            except AnnexReadError as exc:
                raise HTTPException(400, str(exc)) from exc
            except Exception as exc:  # noqa: BLE001 — a corrupt upload is the user's file, not a server fault
                raise HTTPException(400, "Ce fichier n'est pas un document Word lisible.") from exc
            finally:
                Path(tmp.name).unlink(missing_ok=True)
            if reading.mission_id != mission_id:
                raise HTTPException(400, "Cette annexe appartient à une autre mission.")
            appraisals = reading.appraisals
        try:
            job = jobs.start_report(db_path, mission_id, factory, reports / f"rapport_mission_{mission_id[:8]}.docx",
                                    appraisals)
        except JobBusy as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"job_id": job.id, "appraisals": len(appraisals)}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        found = jobs.get(job_id)
        if found is None:
            raise HTTPException(404, "Tâche introuvable.")
        return {"id": found.id, "status": found.status, "lines": found.lines,
                "summary": found.summary, "error": found.error}

    @app.get("/api/jobs/{job_id}/fichier")
    def job_file(job_id: str, format: str = "docx"):
        found = jobs.get(job_id)
        if found is None or found.file is None:
            raise HTTPException(404, "Aucun fichier pour cette tâche.")
        if format == "pdf":
            pdf = _pdf_of(found.file)
            return FileResponse(pdf, media_type=PDF, filename=pdf.name)
        return FileResponse(found.file, media_type=DOCX, filename=found.file.name)

    # --- piloting a mission from the web (see pilot.py) ---

    def _start_pilot(mission_id: str, **kwargs):
        try:
            return pilots.start(db_path, mission_id, workshops=workshops or default_workshops, intake=intake,
                                reports_dir=reports, report_factory=factory, **kwargs)
        except PilotBusy as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/missions")
    async def new_mission(questionnaire: UploadFile = File(...), supporting: list[UploadFile] = File(default=[]),
                          seance: bool = Form(False)):
        if workshops is None and intake is None:
            _require_model_key()
        if not questionnaire.filename:
            raise HTTPException(400, "Joignez le questionnaire de contexte rempli.")
        if pilots.busy:                      # refuse before creating a mission nobody will run
            raise HTTPException(409, "Une mission est déjà en cours de pilotage : interrompez-la ou attendez qu'elle s'arrête.")
        r = repo()
        mission_id = r.create_mission(name=Path(questionnaire.filename).stem, frameworks=[])
        folder = Path(uploads_dir) / mission_id
        folder.mkdir(parents=True, exist_ok=True)
        saved: list[Path] = []
        for upload in [questionnaire, *[s for s in supporting if s.filename]]:
            target = folder / Path(upload.filename).name
            target.write_bytes(await upload.read())
            saved.append(target)
        session = _start_pilot(mission_id, kind="intake", files=saved, seance=seance)
        return {"mission_id": mission_id, "session_id": session.id}

    @app.post("/api/missions/{mission_id}/pilote")
    def start_pilot(mission_id: str, body: PilotStart | None = None):
        r = known_mission(mission_id)
        if not views.next_step(r.get_mission(mission_id).status)["can_pilot"]:
            raise HTTPException(409, "Cette mission n'a rien à lancer pour l'instant.")
        if workshops is None:
            _require_model_key()
        existing = pilots.active_for(mission_id)
        session = existing or _start_pilot(mission_id, kind="run", seance=bool(body and body.seance))
        return {"session_id": session.id}

    @app.get("/api/missions/{mission_id}/pilote")
    def current_pilot(mission_id: str):
        known_mission(mission_id)
        session = pilots.active_for(mission_id)
        return {"session_id": session.id if session else None}

    @app.get("/api/pilote/{session_id}")
    def pilot_state(session_id: str, after: int = 0):
        session = pilots.get(session_id)
        if session is None:
            raise HTTPException(404, "Session introuvable (le serveur a redémarré ?).")
        return {"id": session.id, "mission_id": session.mission_id, "status": session.status,
                "error": session.error, "final_status": session.final_status, "files": sorted(session.files),
                **session.channel.snapshot(after)}

    @app.get("/api/pilote/{session_id}/fichier/{kind}")
    def pilot_file(session_id: str, kind: str, format: str = "docx"):
        session = pilots.get(session_id)
        path = session.files.get(kind) if session else None
        if path is None:
            raise HTTPException(404, "Ce document n'a pas (encore) été produit par cette session.")
        if format == "pdf":
            pdf = _pdf_of(path)
            return FileResponse(pdf, media_type=PDF, filename=pdf.name)
        return FileResponse(path, media_type=DOCX, filename=path.name)

    @app.post("/api/pilote/{session_id}/reponse")
    def pilot_answer(session_id: str, answer: Answer):
        session = pilots.get(session_id)
        if session is None:
            raise HTTPException(404, "Session introuvable.")
        if not session.channel.answer(answer.prompt_id, answer.text):
            raise HTTPException(409, "Cette question n'est plus en attente.")
        return {"ok": True}

    @app.post("/api/pilote/{session_id}/arret")
    def pilot_stop(session_id: str):
        if not pilots.stop(session_id):
            raise HTTPException(409, "Cette session n'est plus en cours.")
        return {"ok": True}

    @app.get("/api/projet")
    def project():
        return views.project_facts(attack_db_path)

    if ui_dir is not None and Path(ui_dir).is_dir():
        app.mount("/", StaticFiles(directory=str(ui_dir), html=True), name="ui")
    return app
