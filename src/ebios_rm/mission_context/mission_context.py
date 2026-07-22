"""Mission Context — the single source of truth (conception §11, §14).

No workshop ever operates on a raw PDF, DOCX, or the raw form. Everything flows
through this pipeline:

    intake form + supplied documents
        -> extraction (source_quote mandatory)
        -> validation (identical / document-only / contradiction)
        -> Mission Context (one object, entirely composed of validated Facts)
        -> Workshop 1

This module owns the two pure ends of that pipeline — turning the form into
declaration Facts, and assembling the final validated Fact set into a
MissionContext. The interactive middle (confirmation, contradiction resolution,
follow-up questions) is driven by the workshop orchestration through the
HumanInterface, because those are the auditor's decisions (§2).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import FactStatus
from ebios_rm.domain.fact import Fact
from ebios_rm.mission_context.intake_form import FIELD_SPECS, OrgContextForm
from ebios_rm.mission_context.priority_matrix import _is_empty


def intake_to_facts(form: OrgContextForm) -> list[Fact]:
    """Turn every non-empty intake field into a Fact of origin 'declaration' (conception §11.1, §4).

    Empty fields are deliberately NOT turned into Facts here — they are candidates
    for the priority matrix (§7), which decides whether to raise them as follow-up
    questions. The AI never invents a value for them (§2).
    """
    facts: list[Fact] = []
    for spec in FIELD_SPECS:
        value = getattr(form, spec.name)
        if _is_empty(value):
            continue
        facts.append(Fact.declaration(spec.name, value))
    return facts


class MissionContext(BaseModel):
    """The consolidated, validated-Fact view handed to Workshop 1 (conception §11, §14)."""

    organisation_nom: str
    secteur_activite: str
    applicable_frameworks: list[str]
    facts: list[Fact] = Field(default_factory=list)
    documents_fournis: list[str] = Field(default_factory=list)

    def get(self, field_name: str) -> Fact | None:
        """The single Fact for a field, if present."""
        for fact in self.facts:
            if fact.field_name == field_name:
                return fact
        return None

    def value(self, field_name: str) -> object | None:
        fact = self.get(field_name)
        return fact.value if fact is not None else None

    def facts_by_status(self, status: FactStatus) -> list[Fact]:
        return [f for f in self.facts if f.status is status]

    @property
    def has_unresolved(self) -> bool:
        """True while any Fact still needs a human decision before workshops may consume it."""
        blocking = {FactStatus.CONTRADICTION, FactStatus.EXTRACTED, FactStatus.ASSESSED, FactStatus.MISSING}
        return any(f.status in blocking for f in self.facts)


_DEFAULT_FRAMEWORKS = ["ISO27001", "ANSSI_hygiene", "RGPD", "NIST"]


def _parse_frameworks(value: object) -> list[str]:
    """Normalise a frameworks answer (list, or comma/semicolon-separated text) to a list."""
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        parts = [p.strip() for chunk in value.split(";") for p in chunk.split(",")]
        return [p for p in parts if p]
    return []


def assemble_from_facts(facts: list[Fact]) -> MissionContext:
    """Build a MissionContext purely from a validated Fact set keyed by question id.

    Used by the document-ingestion path, where there is no OrgContextForm — the
    identity fields are read from the Facts themselves (conception §11, §11.1).
    """
    values = {f.field_name: f.value for f in facts if f.value not in (None, "")}
    documents = _parse_frameworks(values.get("documents_fournis"))  # reuse the list normaliser
    return MissionContext(
        organisation_nom=str(values.get("organisation_nom") or "Organisation non renseignée"),
        secteur_activite=str(values.get("secteur_activite") or "Secteur non renseigné"),
        applicable_frameworks=_parse_frameworks(values.get("applicable_frameworks")) or list(_DEFAULT_FRAMEWORKS),
        facts=facts,
        documents_fournis=documents,
    )


def assemble(form: OrgContextForm, facts: list[Fact]) -> MissionContext:
    """Build the MissionContext from a final, human-validated Fact set (conception §11).

    Callers must have resolved every contradiction and confirmed every extraction
    before calling this — see workshop orchestration. This function does not
    resolve anything; it only consolidates.
    """
    return MissionContext(
        organisation_nom=form.organisation_nom,
        secteur_activite=form.secteur_activite,
        applicable_frameworks=list(form.applicable_frameworks),
        facts=facts,
        documents_fournis=list(form.documents_fournis or []),
    )
