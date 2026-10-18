"""What the interface shows, read from the mission database — no business logic, no model call.

Each function turns what the ateliers stored into a plain dict the web interface can draw:
the missions list, one mission's overview, one atelier's detail, and the project's own
numbers. Nothing is invented here: a figure that cannot be read from the data is left out.
"""

from __future__ import annotations

import sqlite3
import subprocess
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

from ebios_rm.orchestrator import state_machine
from ebios_rm.plugins.registry import discover_frameworks
from ebios_rm.repositories.attack_repository import AttackRepositoryError, connect_readonly
from ebios_rm.repositories.mission_repository import MissionRepository
from ebios_rm.reporting.audit_annex import WORKSHOP_LABELS
from ebios_rm.reporting.history import all_versions

APPROVED = "approved"

QUESTIONS = {
    1: "Que faut-il protéger, et où en est la sécurité aujourd'hui ?",
    2: "Qui pourrait nous attaquer, et pourquoi ?",
    3: "Quel chemin global un attaquant emprunterait-il ?",
    4: "Comment, techniquement, étape par étape ?",
    5: "Quelles mesures mettre en œuvre ?",
}
SHORT_LABELS = {1: "Cadrage et socle", 2: "Sources de risque", 3: "Scénarios stratégiques",
                4: "Scénarios opérationnels", 5: "Traitement du risque"}
LEVELS = ("Faible", "Moyen", "Élevé", "Critique")


def _state(version) -> str:
    if version is None:
        return "absent"
    return "approved" if version.status == APPROVED else "in_progress"


def _organisation(repo: MissionRepository, mission_id: str) -> dict:
    context = repo.latest_output(mission_id, 0)
    if context is None:
        return {}
    return {"nom": context.output.get("organisation_nom", ""),
            "secteur": context.output.get("secteur_activite", ""),
            "referentiels": context.output.get("applicable_frameworks", [])}


def _count(output: dict, key: str) -> int:
    value = output.get(key)
    return len(value) if isinstance(value, list) else 0


def _techniques(output: dict) -> set[str]:
    return {step["technique_id"] for scenario in output.get("scenarios", [])
            for step in scenario.get("attack_path", []) if step.get("technique_id")}


def _level_shift(output: dict) -> str:
    risks = output.get("risques", [])
    if not risks:
        return ""
    before = Counter(r.get("niveau_risque") for r in risks)
    after = Counter(r.get("niveau_risque_residuel") for r in risks)
    top_before = next((lvl for lvl in reversed(LEVELS) if before.get(lvl)), "")
    top_after = next((lvl for lvl in reversed(LEVELS) if after.get(lvl)), "")
    if top_before and top_after and top_before != top_after:
        return f"{len(risks)} risques ramenés de {top_before} à {top_after}"
    return f"{len(risks)} risques traités"


def atelier_metrics(n: int, output: dict) -> tuple[str, list[dict]]:
    """(one-line headline, [{label, value}]) for an atelier output."""
    if n == 1:
        metrics = [("Biens essentiels", _count(output, "biens_essentiels")),
                   ("Biens supports", _count(output, "biens_supports")),
                   ("Événements redoutés", _count(output, "evenements_redoutes")),
                   ("Écarts du socle", _count(output, "baseline_gaps_full"))]
        headline = f"{metrics[0][1]} biens essentiels, {metrics[2][1]} événements redoutés identifiés"
    elif n == 2:
        metrics = [("Sources de risque", _count(output, "sources_risque")),
                   ("Objectifs visés", _count(output, "objectifs_vises")),
                   ("Couples retenus", _count(output, "couples"))]
        headline = f"{metrics[2][1]} couples source/objectif retenus"
    elif n == 3:
        metrics = [("Scénarios stratégiques", _count(output, "scenarios"))]
        headline = f"{metrics[0][1]} scénarios stratégiques"
    elif n == 4:
        scenarios = output.get("scenarios", [])
        steps = sum(len(s.get("attack_path", [])) for s in scenarios)
        metrics = [("Modes opératoires", len(scenarios)), ("Étapes d'attaque", steps),
                   ("Techniques ATT&CK", len(_techniques(output)))]
        headline = f"{len(scenarios)} modes opératoires, {len(_techniques(output))} techniques ATT&CK distinctes"
    elif n == 5:
        # Same wording under two ids is one measure (as in the pages and the report).
        def plain(text: object) -> str:
            return unicodedata.normalize("NFD", str(text)).encode("ascii", "ignore").decode().lower()

        distinct = {plain(m.get("libelle") or m.get("id")) for m in output.get("mesures", [])}
        metrics = [("Risques traités", _count(output, "risques")), ("Mesures", len(distinct)),
                   ("Indicateurs de suivi", len((output.get("cadre_suivi") or {}).get("indicateurs", [])))]
        headline = _level_shift(output) or "Plan de traitement"
    else:
        return "", []
    return headline, [{"label": label, "value": value} for label, value in metrics]


def list_missions(repo: MissionRepository) -> list[dict]:
    missions = []
    for mission in repo.list_missions():
        organisation = _organisation(repo, mission.mission_id)
        ateliers = []
        for n in range(1, 6):
            version = repo.latest_output(mission.mission_id, n)
            ateliers.append({"n": n, "state": _state(version)})
        missions.append({
            "id": mission.mission_id, "name": mission.name, "status": mission.status,
            "organisation": organisation.get("nom") or mission.name, "secteur": organisation.get("secteur", ""),
            "updated_at": mission.updated_at, "ateliers": ateliers,
            "approved": sum(1 for a in ateliers if a["state"] == "approved"),
        })
    return missions


def next_step(status: str) -> dict:
    """What the Orchestrator would do next from this status, said for a person."""
    try:
        action = state_machine.next_action(status)
    except ValueError:
        return {"action": "unknown", "label": "La collecte du contexte n’est pas terminée", "can_pilot": False}
    n = action.workshop_number
    labels = {
        "start_workshop": f"Lancer l’atelier {n}",
        "resume_workshop": f"Reprendre l’atelier {n}",
        "await_approval": f"Valider l’atelier {n}",
        "redo_workshop": f"Refaire l’atelier {n}",
        "generate_report": "Les 5 ateliers sont approuvés : les rapports peuvent être produits",
        "done": "Mission terminée",
        "blocked": "Mission bloquée",
        "start_intake": "Collecter le contexte",
        "resume_intake": "La collecte du contexte n’est pas terminée",
    }
    can_pilot = action.action in ("start_workshop", "resume_workshop", "await_approval", "redo_workshop")
    return {"action": action.action, "workshop": n, "label": labels.get(action.action, action.action), "can_pilot": can_pilot}


def mission_overview(repo: MissionRepository, mission_id: str) -> dict | None:
    mission = repo.get_mission(mission_id)
    if mission is None:
        return None
    ateliers = []
    for n in range(1, 6):
        versions = all_versions(repo, mission_id, n)
        latest = versions[-1] if versions else None
        headline, metrics = atelier_metrics(n, latest.output) if latest else ("", [])
        ateliers.append({
            "n": n, "label": SHORT_LABELS[n], "question": QUESTIONS[n], "state": _state(latest),
            "version": latest.version_number if latest else None, "versions": len(versions),
            "updated_at": latest.created_at if latest else None, "headline": headline, "metrics": metrics,
        })
    totals = repo.token_totals(mission_id)
    return {
        "mission": {"id": mission.mission_id, "name": mission.name, "status": mission.status,
                    "created_at": mission.created_at, "updated_at": mission.updated_at},
        "organisation": _organisation(repo, mission_id),
        "attck_version": repo.attck_version(mission_id),
        "ateliers": ateliers,
        "decisions": len(repo.decisions(mission_id)),
        "model_calls": totals["llm_calls"],
        "can_write_report": any(a["state"] == "approved" for a in ateliers),
        "next_step": next_step(mission.status),
    }


def atelier_detail(repo: MissionRepository, mission_id: str, n: int) -> dict | None:
    if repo.get_mission(mission_id) is None or n not in WORKSHOP_LABELS or n == 0:
        return None
    versions = all_versions(repo, mission_id, n)
    latest = versions[-1] if versions else None
    headline, metrics = atelier_metrics(n, latest.output) if latest else ("", [])
    return {
        "n": n, "label": SHORT_LABELS[n], "question": QUESTIONS[n], "state": _state(latest),
        "headline": headline, "metrics": metrics,
        "versions": [{"number": v.version_number, "status": v.status, "created_at": v.created_at} for v in versions],
        "output": latest.output if latest else None,
        "organisation": _organisation(repo, mission_id),
    }


# --- the project itself ---------------------------------------------------------------

def _git_activity(repo_root: Path) -> dict | None:
    try:
        out = subprocess.run(
            ["git", "log", "--all", "--format=%ad", "--date=short"], cwd=repo_root,
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None
    if not out:
        return None
    days = sorted(date.fromisoformat(d) for d in out)
    first = days[0]
    weeks = Counter((d - first).days // 7 for d in days)
    return {"first": first.isoformat(), "last": days[-1].isoformat(), "commits": len(days),
            "weeks": [{"week": w + 1, "commits": weeks.get(w, 0)} for w in range(max(weeks) + 1)]}


def project_facts(attack_db_path: str | Path | None = None, repo_root: Path | None = None) -> dict:
    frameworks = [{"id": p.id, "name": p.name, "version": p.framework_version, "controls": len(p.controls)}
                  for p in discover_frameworks()]
    attack = None
    if attack_db_path and Path(attack_db_path).exists():
        try:
            conn = connect_readonly(attack_db_path)
            version = conn.execute("SELECT version_tag FROM attack_version LIMIT 1").fetchone()
            techniques = conn.execute("SELECT COUNT(*) FROM techniques WHERE revoked = 0 AND deprecated = 0").fetchone()[0]
            mitigations = conn.execute("SELECT COUNT(*) FROM mitigations WHERE revoked = 0 AND deprecated = 0").fetchone()[0]
            attack = {"version": version[0] if version else "", "techniques": techniques, "mitigations": mitigations}
            conn.close()
        except (AttackRepositoryError, sqlite3.Error):  # a missing table must not break the page
            attack = None
    return {
        "ateliers": [{"n": n, "label": SHORT_LABELS[n], "question": QUESTIONS[n]} for n in range(1, 6)],
        "frameworks": frameworks,
        "controls": sum(f["controls"] for f in frameworks),
        "attack": attack,
        "activity": _git_activity(repo_root or Path(__file__).resolve().parents[3]),
    }
