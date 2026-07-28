"""Mission Context — the single source of truth (conception §11, §14).

No workshop ever operates on a raw PDF, DOCX, or the raw form. Everything flows
through this pipeline:

    filled questionnaire + supplied documents
        -> extraction (source_quote mandatory)
        -> validation (identical / document-only / contradiction)
        -> Mission Context (one object, entirely composed of validated Facts)
        -> Workshop 1

This module owns the pure end of that pipeline: assembling the final validated
Fact set into a MissionContext. The interactive middle (confirmation,
contradiction resolution, follow-up questions) is driven by intake_ingestion
through the HumanInterface, because those are the auditor's decisions (§2).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ebios_rm.domain.enums import FactStatus
from ebios_rm.domain.fact import Fact


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
    """Build a MissionContext from a validated Fact set keyed by questionnaire id.

    The identity fields are read from the Facts themselves (conception §11, §11.1).
    """
    values = {f.field_name: f.value for f in facts if f.value not in (None, "")}
    documents = _parse_frameworks(values.get("documents_fournis"))  # reuse the list normaliser
    return MissionContext(
        organisation_nom=str(values.get("organisation_nom") or "Organisation non renseignée"),
        secteur_activite=str(values.get("secteur_activite") or "Secteur non renseigné"),
        # The ingestion prompt is shown the referentials this installation can load and
        # answers with their ids, so nothing is matched here: a mention the model did
        # not recognise stays as the client wrote it and stops at the controls gate (§12.5).
        applicable_frameworks=(
            _parse_frameworks(values.get("applicable_frameworks")) or list(_DEFAULT_FRAMEWORKS)
        ),
        facts=facts,
        documents_fournis=documents,
    )
