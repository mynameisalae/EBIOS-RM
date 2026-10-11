"""Mission report (rapport de mission) — LLM-narrated, current version only (conception §20.1, §20.2).

Every claim must cite a precise mission_state field; an automatic check
runs before any statement is added (anti-hallucination gate, §20.2).

The flow, each step testable alone:
    build_snapshot(repo, mission_id)         what the report may read: approved current versions only
    write_mission_report(snapshot, runner)   one model call per section, every statement checked in code
    build_mission_report(report)             the house-styled Word document

A statement the gate refuses is never printed in the report and never dropped silently:
it lands in ``MissionReport.rejected`` with its reason, for the auditor to see.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from docx.document import Document as DocxDocument

from ebios_rm.domain.operational_scenario import STATUT_CONFIRME
from ebios_rm.repositories.mission_repository import MissionRepository
from ebios_rm.reporting.appraisals import Appraisal
from ebios_rm.reporting.house_style import CREAM, GOLD, Cover, HouseDocument, french_month_year
from ebios_rm.reporting.report_agent import Refusal, ReportRunner, SectionSpec, Statement

APPROVED = "approved"
REFERENCES_TITLE = "Références des sources"

# "Levels in context" (§20.3): the scale every level is read against, citable like any field.
SCALES = {
    "gravite": "Minimale < Significative < Grave < Critique",
    "vraisemblance": "V1 (la moins vraisemblable) à V4 (la plus vraisemblable)",
    "niveau_risque": "Faible < Moyen < Élevé < Critique",
}

SECTIONS = (
    SectionSpec("synthese", "Synthèse", (5,),
                "Une vraie synthèse pour une direction, en 3 à 5 phrases au plus : le nombre de risques retenus, "
                "leur niveau avant puis après traitement, et ce que la direction a accepté. Ne répète pas chaque "
                "champ : va à l'essentiel."),
    SectionSpec("perimetre", "Périmètre et enjeux", (1,),
                "L'organisation étudiée, ses biens essentiels, les événements redoutés et leur gravité."),
    SectionSpec("sources", "Sources de risque", (2,),
                "Les sources de risque et objectifs visés retenus, et la pertinence de chaque couple."),
    SectionSpec("strategiques", "Scénarios stratégiques", (3,),
                "Les scénarios stratégiques retenus : quelle source, quel objectif, par quelle voie."),
    SectionSpec("operationnels", "Scénarios opérationnels", (4,),
                "Les modes opératoires confirmés : comment l'attaque se déroulerait, sa vraisemblance et son niveau "
                "de risque, et quel mode porte le risque de chaque scénario stratégique."),
    SectionSpec("traitement", "Traitement du risque", (5,),
                "La stratégie de traitement de chaque risque, les mesures retenues, les risques résiduels et leur "
                "acceptation, le cadre de suivi."),
)


# --- what the report may read -------------------------------------------------

_DROPPED_TOP_LEVEL = {"quality_report", "elements_ecartes", "human_edits", "activites_faites", "attck_version"}
_PROVENANCE_KEYS = {"origin", "derived_from_fact_fields", "evidence_quote"}
_W4_SCENARIO_KEYS = (
    "id", "scenario_strategique_id", "source_risque_id", "objectif_vise_id", "variante", "voie", "resume",
    "gravite", "vraisemblance_initiale", "revised_likelihood", "revised_risk_level", "retenu",
    "biens_essentiels_ids", "evenements_redoutes_ids",
)
_W4_STEP_KEYS = ("phase", "tactic", "technique_id", "technique_name", "description", "vraisemblance_action")


def _prune(node):
    if isinstance(node, dict):
        return {k: _prune(v) for k, v in node.items() if k not in _PROVENANCE_KEYS}
    if isinstance(node, list):
        return [_prune(v) for v in node]
    return node


def _pick(item: dict, keys: tuple[str, ...]) -> dict:
    return {k: item[k] for k in keys if k in item}


def _generic_view(output: dict) -> dict:
    kept = {k: v for k, v in output.items() if k not in _DROPPED_TOP_LEVEL and not k.startswith("alertes_")}
    return _prune(kept)


def _view_w1(output: dict) -> dict:
    """No control provenance here: framework and control_id are the audit annex's (§12.3, §20.3)."""
    view = _generic_view(output)
    view.pop("unverified_controls", None)
    view.pop("baseline_scope_decisions", None)
    view["baseline_gaps_full"] = [_pick(g, ("gap_id", "weakness")) for g in output.get("baseline_gaps_full", [])]
    return view


def _view_w4(output: dict) -> dict:
    """Confirmed scenarios only (§20.3), without the working notes behind each analysis."""
    scenarios = []
    for scenario in output.get("scenarios", []):
        if scenario.get("statut") != STATUT_CONFIRME:
            continue
        item = _pick(scenario, _W4_SCENARIO_KEYS)
        item["attack_path"] = [_pick(step, _W4_STEP_KEYS) for step in scenario.get("attack_path", [])]
        scenarios.append(item)
    return {"scenarios": scenarios}


_VIEWS: dict[int, Callable[[dict], dict]] = {1: _view_w1, 4: _view_w4}


@dataclass(frozen=True)
class MissionSnapshot:
    mission_name: str
    state: dict
    approved: tuple[int, ...]
    not_approved: dict[int, str]


def build_snapshot(repo: MissionRepository, mission_id: str) -> MissionSnapshot:
    mission = repo.get_mission(mission_id)
    if mission is None:
        raise ValueError(f"Mission introuvable : {mission_id}")

    context = repo.latest_output(mission_id, 0)
    organisation = {}
    if context is not None:
        organisation = {
            "nom": context.output.get("organisation_nom", ""),
            "secteur_activite": context.output.get("secteur_activite", ""),
            "referentiels": context.output.get("applicable_frameworks", []),
        }
    state: dict = {"organisation": organisation, "echelles": dict(SCALES)}
    approved: list[int] = []
    not_approved: dict[int, str] = {}
    for n in range(1, 6):
        latest = repo.latest_output(mission_id, n)
        if latest is None:
            not_approved[n] = "aucune version enregistrée"
        elif latest.status != APPROVED:
            not_approved[n] = f"version {latest.version_number} non approuvée (statut : {latest.status})"
        else:
            state[f"w{n}"] = _VIEWS.get(n, _generic_view)(latest.output)
            approved.append(n)
    return MissionSnapshot(mission.name, state, tuple(approved), not_approved)


# --- the anti-hallucination gate (§20.2) ---------------------------------------

_IDENTIFIER = re.compile(
    r"\b(?:(?:SS|SR|OV|SO|BE|ER|BS|IND|M)-\d+|BG-[0-9a-f]{8}|R\d+|T\d{4}(?:\.\d{3})?|M1\d{3}|V[1-4])\b"
)


def _parts(path: str) -> list[str]:
    return [p for p in re.sub(r"\[(\d+)\]", r".\1", path.strip()).split(".") if p]


def _resolve(state: dict, parts: list[str]) -> tuple[bool, object]:
    node: object = state
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return False, None
    return True, node


def _scopes(state: dict, parts: list[str], value: object) -> list[object]:
    """What a citation vouches for: the cited value (or, for a bare field, the object that holds it),
    and the nearest enclosing object that carries an ``id`` — the thing the sentence is about."""
    if isinstance(value, dict):
        scopes: list[object] = [value]
    else:
        _, parent = _resolve(state, parts[:-1])
        scopes = [parent if isinstance(parent, dict) else value]
    for depth in range(len(parts) - 1, 1, -1):
        _, ancestor = _resolve(state, parts[:depth])
        if isinstance(ancestor, dict) and isinstance(ancestor.get("id"), str):
            scopes.append(ancestor)
            break
    return scopes


def check_statement(statement: Statement, state: dict) -> str | None:
    """None if the statement stands; otherwise why it is refused.

    Every citation must point at a real field or object inside an atelier, and every
    identifier the text names (R1, SO-02, M-03, T1078, V3...) must appear in what the
    citations cover. This catches invented fields and invented identifiers; it does not
    judge whether the sentence reads the data faithfully, which stays the auditor's call.
    """
    if not statement.text.strip():
        return "texte vide"
    if not statement.sources:
        return "aucune source citée"
    scopes = []
    for raw in statement.sources:
        parts = _parts(raw)
        if len(parts) < 2:
            return f"source trop vague : {raw}"
        found, value = _resolve(state, parts)
        if not found:
            return f"source introuvable : {raw}"
        scopes += _scopes(state, parts, value)
    attested = json.dumps(scopes, ensure_ascii=False)
    for token in dict.fromkeys(_IDENTIFIER.findall(statement.text)):
        if token not in attested:
            return f"« {token} » ne figure pas dans les champs cités"
    return None


# --- writing the report ---------------------------------------------------------

@dataclass(frozen=True)
class ReportSection:
    key: str
    title: str
    statements: tuple[Statement, ...]


@dataclass(frozen=True)
class SkippedSection:
    title: str
    reason: str


@dataclass(frozen=True)
class RejectedStatement:
    section: str
    text: str
    sources: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class MissionReport:
    mission_name: str
    organisation: str
    generated_at: str
    sections: tuple[ReportSection, ...]
    skipped: tuple[SkippedSection, ...]
    rejected: tuple[RejectedStatement, ...]
    corrected: int = 0  # statements refused once, then kept after the model rewrote their citations


APPRAISALS_TITLE = "Appréciations de l'auditeur"
_APPRAISAL_SOURCE = "auditeur.appreciations."


def _draft_section(
    spec: SectionSpec, subset: dict, runner: ReportRunner,
    extra_check: Callable[[Statement], str | None] | None = None,
) -> tuple[list[Statement], list[RejectedStatement], int]:
    """The model drafts, the gate checks, one correction round, and nothing refused is lost silently."""

    def verdict(statement: Statement) -> str | None:
        return check_statement(statement, subset) or (extra_check(statement) if extra_check else None)

    kept: list[Statement] = []
    refused: list[tuple[Statement, str]] = []
    for statement in runner.write_section(spec, subset).statements:
        reason = verdict(statement)
        if reason is None:
            kept.append(statement)
        else:
            refused.append((statement, reason))

    rejected: list[RejectedStatement] = []
    corrected = 0
    if refused:  # one correction round: rewrite with proper citations, or give the statement up
        revised = runner.revise_section(
            spec, subset, [Refusal(text=s.text, sources=s.sources, reason=r) for s, r in refused],
        ).statements
        for index, (original, reason) in enumerate(refused):
            retry = revised[index] if index < len(revised) else None
            if retry is None or not retry.text.strip():
                rejected.append(RejectedStatement(
                    spec.title, original.text, tuple(original.sources), f"abandonnée après refus — {reason}"))
                continue
            new_reason = verdict(retry)
            if new_reason is None:
                kept.append(retry)
                corrected += 1
            else:
                rejected.append(RejectedStatement(spec.title, retry.text, tuple(retry.sources), new_reason))
    return kept, rejected, corrected


def _appraisal_spec(appraisals: tuple[Appraisal, ...]) -> SectionSpec:
    ateliers = sorted({int(m.group(1)) for a in appraisals if (m := re.match(r"Atelier (\d)", a.origin))})
    return SectionSpec(
        "appreciations", APPRAISALS_TITLE, tuple(ateliers),
        "Pour chaque appréciation de l'auditeur (auditeur.appreciations), une affirmation qui la restitue "
        "fidèlement et l'attribue à l'auditeur (« L'auditeur a apprécié que… »). N'ajoute aucun jugement, ne "
        "corrige pas l'auditeur, situe l'événement concerné. Cite l'appréciation "
        "(auditeur.appreciations.N.appreciation) et le champ de l'événement concerné.",
    )


def _cites_the_auditor(statement: Statement) -> str | None:
    if any(_parts(source)[:2] == ["auditeur", "appreciations"] for source in statement.sources):
        return None
    return "ne cite pas l'appréciation de l'auditeur"


def write_mission_report(
    snapshot: MissionSnapshot, runner: ReportRunner, *, appraisals: tuple[Appraisal, ...] = (),
    generated_at: str | None = None,
) -> MissionReport:
    sections: list[ReportSection] = []
    skipped: list[SkippedSection] = []
    rejected: list[RejectedStatement] = []
    corrected = 0

    plan: list[tuple[SectionSpec, dict, Callable | None]] = []
    for spec in SECTIONS:
        missing = [n for n in spec.ateliers if n not in snapshot.approved]
        if missing:
            reasons = "; ".join(f"atelier {n} : {snapshot.not_approved[n]}" for n in missing)
            skipped.append(SkippedSection(spec.title, reasons))
            continue
        wanted = {"organisation", "echelles", *(f"w{n}" for n in spec.ateliers)}
        plan.append((spec, {k: v for k, v in snapshot.state.items() if k in wanted}, None))

    if appraisals:  # only the cells the auditor filled in, with only the ateliers they concern
        spec = _appraisal_spec(appraisals)
        wanted = {"organisation", "echelles", *(f"w{n}" for n in spec.ateliers)}
        subset = {k: v for k, v in snapshot.state.items() if k in wanted}
        subset["auditeur"] = {"appreciations": [
            {"origine": a.origin, "code": a.code, "message": a.message, "appreciation": a.text} for a in appraisals
        ]}
        plan.append((spec, subset, _cites_the_auditor))

    for spec, subset, extra_check in plan:
        kept, refused, fixed = _draft_section(spec, subset, runner, extra_check)
        rejected += refused
        corrected += fixed
        if kept:
            sections.append(ReportSection(spec.key, spec.title, tuple(kept)))
        else:
            skipped.append(SkippedSection(spec.title, "aucune affirmation vérifiée"))

    return MissionReport(
        mission_name=snapshot.mission_name,
        organisation=snapshot.state["organisation"].get("nom") or snapshot.mission_name,
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        sections=tuple(sections), skipped=tuple(skipped), rejected=tuple(rejected), corrected=corrected,
    )


# --- rendering -------------------------------------------------------------------

def build_mission_report(report: MissionReport) -> DocxDocument:
    doc = HouseDocument(Cover(
        kicker="RAPPORT DE MISSION  ·  ANALYSE DE RISQUE EBIOS RM",
        title="Rapport de mission",
        subtitle=report.organisation,
        tagline="Périmètre  ·  Sources de risque  ·  Scénarios  ·  Traitement du risque",
        footer=f"Projet OGSBC  ·  Rapport de mission  ·  {french_month_year(report.generated_at)}",
    ))

    doc.label("SOMMAIRE")
    doc.heading("Table des matières", size=18)
    for number, section in enumerate(report.sections, 1):
        doc.toc_line(f"{number}.", section.title.upper())
    if report.sections:
        doc.toc_line(f"{len(report.sections) + 1}.", REFERENCES_TITLE.upper())
    doc.page_break()

    doc.callout(
        "Comment lire ce rapport",
        "Ce rapport est rédigé avec l'assistance d'une IA, à partir des seules versions approuvées de l'étude. "
        "Chaque affirmation porte un numéro entre crochets qui renvoie, en fin de document, aux champs précis de "
        "l'étude sur lesquels elle repose ; ce rattachement est vérifié automatiquement avant que l'affirmation "
        "soit retenue. L'analyse et sa validation restent celles de l'auditeur.",
        background=CREAM, border=GOLD,
    )
    doc.table(["Échelle", "Valeurs"], [
        ["Gravité", SCALES["gravite"]],
        ["Vraisemblance", SCALES["vraisemblance"]],
        ["Niveau de risque", SCALES["niveau_risque"]],
    ], widths=[28, 72])
    if report.skipped:
        doc.note("Sections non incluses dans cette version : " + "; ".join(
            f"{s.title} ({s.reason})" for s in report.skipped) + ".")

    references: list[tuple[int, str]] = []
    for number, section in enumerate(report.sections, 1):
        doc.heading(f"{number}. {section.title}")
        for statement in section.statements:
            reference = len(references) + 1
            doc.statement(statement.text, reference)
            references.append((reference, ", ".join(statement.sources)))
    if references:
        doc.page_break()
        doc.heading(f"{len(report.sections) + 1}. {REFERENCES_TITLE}")
        doc.note("Chaque numéro renvoie aux champs de l'étude sur lesquels l'affirmation repose.")
        for reference, sources in references:
            doc.reference_line(reference, sources)
    return doc.document


def write_mission_report_file(report: MissionReport, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    build_mission_report(report).save(str(target))
    return target
