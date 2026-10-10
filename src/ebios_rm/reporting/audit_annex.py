"""Audit annex (annexe d'audit) — pure data rendering via python-docx, no LLM (conception §20.1, §20.3).

Fully exact-output testable. Carries the complete provenance (control_id,
framework, including the RGPD security/legal split) that workshop 4 never
receives (§12.3, §18).

Two steps, kept apart so each can be tested alone:
    collect_audit_annex_data(repo, mission_id) -> AuditAnnexData   (reads the mission DB)
    build_audit_annex(data) -> Word document                       (data in, house-styled document out)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from docx.document import Document as DocxDocument

from ebios_rm.plugins.registry import discover_frameworks
from ebios_rm.repositories.mission_repository import DecisionRow, MissionRepository
from ebios_rm.reporting.house_style import (
    CREAM, GOLD, GREEN, LABEL, ORANGE, Cover, HouseDocument, french_month_year,
)

WORKSHOP_LABELS = {
    0: "Mission Context",
    1: "Atelier 1 — Cadrage et socle",
    2: "Atelier 2 — Sources de risque",
    3: "Atelier 3 — Scénarios stratégiques",
    4: "Atelier 4 — Scénarios opérationnels",
    5: "Atelier 5 — Traitement du risque",
}

# A decision whose action starts with one of these is out of the routine path
# (an approval is routine; a refusal, a block, a forced acceptance is not).
NON_ROUTINE_ACTIONS = ("rejected", "blocked", "paused", "force_accepted", "plafond", "restart")

NATURE_SECURITY = "Sécurité"
NATURE_LEGAL = "Impact légal"
UNKNOWN_VERSION = "—"


@dataclass(frozen=True)
class VersionRow:
    workshop_number: int
    version_number: int
    status: str
    created_at: str


@dataclass(frozen=True)
class AbnormalEvent:
    origin: str
    code: str
    message: str


@dataclass(frozen=True)
class GapProvenanceRow:
    gap_id: str
    weakness: str
    framework: str
    control_id: str
    nature: str


@dataclass(frozen=True)
class UnverifiedRow:
    framework: str
    control_id: str
    reason: str


@dataclass(frozen=True)
class AuditAnnexData:
    mission_id: str
    mission_name: str
    mission_status: str
    attck_version: str
    framework_versions: dict[str, str]
    versions: list[VersionRow]
    decisions: list[DecisionRow]
    gaps: list[GapProvenanceRow]
    unverified: list[UnverifiedRow]
    abnormal_events: list[AbnormalEvent]
    token_totals: dict[str, int]
    generated_at: str = ""
    notes: list[str] = field(default_factory=list)


# --- reading the mission -------------------------------------------------------

def _framework_versions(declared: list[str]) -> dict[str, str]:
    """Version of each declared referential, read from the plugin manifests (the ones the run used)."""
    by_id = {p.id.casefold(): p for p in discover_frameworks()}
    versions: dict[str, str] = {}
    for name in declared:
        plugin = by_id.get(name.casefold())
        versions[name] = (plugin.framework_version or UNKNOWN_VERSION) if plugin else UNKNOWN_VERSION
    return versions


def _declared_frameworks(repo: MissionRepository, mission_id: str, fallback: list[str]) -> list[str]:
    context = repo.latest_output(mission_id, 0)
    declared = (context.output.get("applicable_frameworks") if context else None) or fallback
    return list(declared)


def _events_from_output(atelier: int, output: dict) -> list[AbnormalEvent]:
    """Anomalies the code recorded on an output, and quality checks that were not 'ok'."""
    events: list[AbnormalEvent] = []

    def walk(node: object, owner: str) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item, owner)
        elif isinstance(node, dict):
            here = node["id"] if isinstance(node.get("id"), str) else owner
            for key, value in node.items():
                if key == "anomalies" and isinstance(value, list):
                    for a in value:
                        if isinstance(a, dict) and "code" in a and "message" in a:
                            where = f"Atelier {atelier} · {here}" if here else f"Atelier {atelier}"
                            events.append(AbnormalEvent(where, str(a["code"]), str(a["message"])))
                elif key == "quality_report" and isinstance(value, dict):
                    for check in value.get("checks", []):
                        if check.get("statut", "ok") != "ok":
                            events.append(AbnormalEvent(
                                f"Atelier {atelier} · contrôle qualité ({check['statut']})",
                                str(check.get("controle", "")), str(check.get("message", "")),
                            ))
                else:
                    walk(value, here)

    walk(output, "")
    return events


def collect_audit_annex_data(
    repo: MissionRepository, mission_id: str, *,
    framework_versions: dict[str, str] | None = None, generated_at: str | None = None,
) -> AuditAnnexData:
    mission = repo.get_mission(mission_id)
    if mission is None:
        raise ValueError(f"Mission introuvable : {mission_id}")

    versions: list[VersionRow] = []
    events: list[AbnormalEvent] = []
    gaps: list[GapProvenanceRow] = []
    unverified: list[UnverifiedRow] = []

    for n in range(0, 6):
        all_versions = repo.all_versions(mission_id, n)
        versions += [VersionRow(n, v.version_number, v.status, v.created_at) for v in all_versions]
        if all_versions and n >= 1:
            events += _events_from_output(n, all_versions[-1].output)

    w1 = repo.latest_output(mission_id, 1)
    if w1 is not None:
        for gap in w1.output.get("baseline_gaps_full", []):
            nature = NATURE_SECURITY if gap.get("risk_categories") else NATURE_LEGAL
            for control in gap.get("controls", []):
                gaps.append(GapProvenanceRow(
                    gap["gap_id"], gap.get("weakness", ""), control["framework"], control["control_id"], nature))
        for u in w1.output.get("unverified_controls", []):
            unverified.append(UnverifiedRow(u.get("framework", ""), u["control_id"], u.get("reason", "")))

    decisions = repo.decisions(mission_id)
    for d in decisions:
        if d.action_taken.startswith(NON_ROUTINE_ACTIONS):
            events.append(AbnormalEvent(f"Journal des décisions · {d.stage}", d.action_taken, d.justification_given))

    if framework_versions is None:
        framework_versions = _framework_versions(_declared_frameworks(repo, mission_id, mission.frameworks))

    return AuditAnnexData(
        mission_id=mission.mission_id, mission_name=mission.name, mission_status=mission.status,
        attck_version=repo.attck_version(mission_id) or UNKNOWN_VERSION,
        framework_versions=framework_versions, versions=versions, decisions=decisions,
        gaps=gaps, unverified=unverified, abnormal_events=events,
        token_totals=repo.token_totals(mission_id),
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# --- rendering ----------------------------------------------------------------

SECTION_TITLES = [
    "Référentiels de conformité",
    "Historique des versions par atelier",
    "Journal des décisions de l'auditeur",
    "Provenance des écarts du socle",
    "Événements anormaux",
    "Consommation du modèle",
]

_STATUS_STYLE = {"approved": {"color": GREEN, "bold": True}, "rejected": {"color": ORANGE, "bold": True},
                 "superseded": {"color": LABEL}}


def _cover(data: AuditAnnexData) -> Cover:
    return Cover(
        kicker="ANNEXE D'AUDIT  ·  DOSSIER DE TRAÇABILITÉ",
        title="Annexe d'audit",
        subtitle=data.mission_name,
        tagline="Versions  ·  Décisions de l'auditeur  ·  Provenance des écarts  ·  Événements anormaux",
        footer=f"Projet OGSBC  ·  Annexe d'audit  ·  {french_month_year(data.generated_at)}",
    )


def _section(doc: HouseDocument, number: int) -> None:
    doc.heading(f"{number}. {SECTION_TITLES[number - 1]}")


def build_audit_annex(data: AuditAnnexData) -> DocxDocument:
    doc = HouseDocument(_cover(data))

    doc.label("SOMMAIRE")
    doc.heading("Table des matières", size=18)
    for number, title in enumerate(SECTION_TITLES, 1):
        doc.toc_line(f"{number}.", title.upper())
    doc.page_break()

    doc.callout(
        "À quoi sert ce document",
        "Dossier de traçabilité de la mission, produit sans modèle de langage à partir des seules données "
        "enregistrées. La dernière colonne du tableau des événements anormaux est laissée vide : "
        "l'auditeur y consigne son appréciation.",
        background=CREAM, border=GOLD,
    )
    doc.table(["Rubrique", "Valeur"], [
        ["Mission", data.mission_id],
        ["Statut de la mission", data.mission_status],
        ["Référentiel ATT&CK utilisé", data.attck_version],
        ["Document généré le", data.generated_at],
    ], widths=[34, 66])

    _section(doc, 1)
    if data.framework_versions:
        doc.table(["Référentiel", "Version"], [[k, v] for k, v in data.framework_versions.items()], widths=[60, 40])
    else:
        doc.note("Aucun référentiel de conformité déclaré.")

    _section(doc, 2)
    doc.table(["Atelier", "Version", "Statut", "Date"], [
        [WORKSHOP_LABELS[v.workshop_number], str(v.version_number),
         {"text": v.status, **_STATUS_STYLE.get(v.status, {})}, v.created_at]
        for v in data.versions
    ], widths=[36, 10, 16, 38], size=8.5)

    _section(doc, 3)
    if data.decisions:
        doc.table(["Horodatage", "Étape", "Décideur", "Action", "Justification"], [
            [d.timestamp, d.stage, d.decided_by, d.action_taken, d.justification_given] for d in data.decisions
        ], widths=[26, 8, 10, 18, 38], size=8)
    else:
        doc.note("Aucune décision enregistrée.")

    _section(doc, 4)
    if data.gaps:
        doc.table(["Écart", "Faiblesse", "Référentiel", "Contrôle", "Nature"], [
            [g.gap_id, g.weakness, g.framework, g.control_id, g.nature] for g in data.gaps
        ], widths=[14, 36, 16, 16, 18], size=8.5)
    else:
        doc.note("Aucun écart du socle.")
    if data.unverified:
        doc.heading("Contrôles non vérifiés", level=2)
        doc.table(["Référentiel", "Contrôle", "Raison"],
                  [[u.framework, u.control_id, u.reason] for u in data.unverified], widths=[25, 25, 50], size=8.5)

    _section(doc, 5)
    if data.abnormal_events:
        doc.table(["Origine", "Code", "Message", "Appréciation de l'auditeur"], [
            [e.origin, e.code, e.message, ""] for e in data.abnormal_events
        ], widths=[20, 16, 40, 24], size=8)
    else:
        doc.note("Aucun événement anormal.")

    _section(doc, 6)
    totals = data.token_totals
    doc.table(["Indicateur", "Valeur"], [
        ["Appels au modèle", str(totals.get("llm_calls", 0))],
        ["Tokens en entrée", str(totals.get("input_tokens", 0))],
        ["Tokens en sortie", str(totals.get("output_tokens", 0))],
    ], widths=[60, 40])
    return doc.document


def write_audit_annex(data: AuditAnnexData, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    build_audit_annex(data).save(str(target))
    return target
