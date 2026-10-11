"""The web interface's server: reads the mission database, serves the built interface, and produces
the two reports (conception §20) on request.

    create_app(db_path)  ->  a FastAPI app; ``python scripts/run_interface.py`` starts it.
"""

from __future__ import annotations

import tempfile
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from ebios_rm.api import views
from ebios_rm.api.jobs import JobBusy, JobRegistry, RunnerFactory
from ebios_rm.repositories.mission_repository import MissionRepository, connect
from ebios_rm.reporting.appraisals import AnnexReadError, read_appraisals
from ebios_rm.reporting.audit_annex import build_audit_annex, collect_audit_annex_data

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _default_runner_factory(progress):
    from ebios_rm.reporting.report_agent import AgnoReportRunner  # noqa: PLC0415

    return AgnoReportRunner(progress=progress)


def _require_model_key() -> None:
    from ebios_rm.config import load_settings  # noqa: PLC0415

    if not load_settings().openrouter_api_key:
        raise HTTPException(400, "OPENROUTER_API_KEY n'est pas défini : renseignez-le dans .env pour rédiger le rapport.")


def create_app(
    db_path: str, *, attack_db_path: str | None = None, reports_dir: str | Path = "data/reports",
    ui_dir: str | Path | None = None, runner_factory: RunnerFactory | None = None,
) -> FastAPI:
    app = FastAPI(title="EBIOS RM Agent — OGSBC", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])
    jobs = JobRegistry()
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
    def annexe(mission_id: str):
        r = known_mission(mission_id)
        buffer = BytesIO()
        build_audit_annex(collect_audit_annex_data(r, mission_id)).save(buffer)
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
    def job_file(job_id: str):
        found = jobs.get(job_id)
        if found is None or found.file is None:
            raise HTTPException(404, "Aucun fichier pour cette tâche.")
        return FileResponse(found.file, media_type=DOCX, filename=found.file.name)

    @app.get("/api/projet")
    def project():
        return views.project_facts(attack_db_path)

    if ui_dir is not None and Path(ui_dir).is_dir():
        app.mount("/", StaticFiles(directory=str(ui_dir), html=True), name="ui")
    return app
