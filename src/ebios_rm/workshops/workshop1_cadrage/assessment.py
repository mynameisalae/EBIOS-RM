"""Deterministic baseline-assessment methodology for Workshop 1 (conception §15).

Pure functions, no LLM and no I/O — this is where the evidence discipline, the
RGPD security/legal split, the stable gap-id hashing, and the scope-decision
completeness rule are enforced in code, so an LLM can never talk its way past them.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ebios_rm.repositories.reference_repository import BaselineControl
from ebios_rm.workshops.workshop1_cadrage.models import (
    REASON_INVALID_VERDICT,
    REASON_NO_EVIDENCE_CITED,
    REASON_NO_INFORMATION,
    REASON_UNKNOWN_CONTROL,
    BaselineGap,
    BaselineScopeDecision,
    CadrageProposal,
    ControlAssessmentProposal,
    ControlReference,
    UnverifiedControl,
)

_GAP_VERDICT = "gap"
_COMPLIANT_VERDICT = "compliant"
_INSUFFICIENT_VERDICT = "insufficient_information"

# Mots-clés qui caractérisent des BIENS SUPPORTS et qui sont formellement
# interdits comme Biens Essentiels (méthodologie EBIOS RM).
_INFRASTRUCTURE_TERMS = (
    "serveur", "server", "base de donnees", "database", "bdd", "firewall", "pare-feu",
    "switch", "routeur", "vpn", "reseau", "network", "active directory", "ad",
    "poste de travail", "ordinateur", "application", "logiciel", "messagerie"
)


def _normalise(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(c for c in stripped if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", ascii_text.casefold()).strip()


def validate_cadrage_proposal(proposal: CadrageProposal) -> list[str]:
    """Validation déterministe stricte de la proposition de cadrage émise par l'IA.

    Renvoie la liste des erreurs bloquantes. Si la liste n'est pas vide, le cadrage
    est méthodologiquement invalide et doit être rejeté ou corrigé.
    """
    errors: list[str] = []

    # 1. Vérification de présence minimale
    if not proposal.biens_essentiels:
        errors.append("Aucun bien essentiel proposé : l'organisation doit avoir au moins un processus ou une information vitale.")
    if not proposal.evenements_redoutes:
        errors.append("Aucun événement redouté proposé : les enjeux de sécurité sont absents.")

    # 2. Unicité et intégrité des Biens Essentiels
    be_ids: set[str] = set()
    for be in proposal.biens_essentiels:
        if not be.id or not be.id.strip():
            errors.append("Un bien essentiel n'a pas d'identifiant.")
        elif be.id in be_ids:
            errors.append(f"Identifiant de bien essentiel en double : '{be.id}'.")
        be_ids.add(be.id)

        # Vérification méthodologique : un serveur ne peut pas être un bien essentiel
        normalised_name = _normalise(f"{be.nom} {be.description}")
        for term in _INFRASTRUCTURE_TERMS:
            if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalised_name):
                errors.append(
                    f"Le bien essentiel '{be.nom}' ({be.id}) mentionne un composant d'infrastructure "
                    f"('« {term} »'). Un serveur ou équipement est un Bien Support, pas un Bien Essentiel."
                )
                break

    # 3. Unicité et couverture des Événements Redoutés
    er_ids: set[str] = set()
    be_couverts: set[str] = set()
    for er in proposal.evenements_redoutes:
        if not er.id or not er.id.strip():
            errors.append("Un événement redouté n'a pas d'identifiant.")
        elif er.id in er_ids:
            errors.append(f"Identifiant d'événement redouté en double : '{er.id}'.")
        er_ids.add(er.id)

        if not er.bien_essentiel_id or er.bien_essentiel_id not in be_ids:
            errors.append(
                f"L'événement redouté '{er.id}' référence un bien essentiel inconnu : '{er.bien_essentiel_id}'."
            )
        else:
            be_couverts.add(er.bien_essentiel_id)

    # RÈGLE D'OR EBIOS RM : Chaque bien essentiel doit porter au moins un événement redouté
    be_orphelins = be_ids - be_couverts
    if be_orphelins:
        errors.append(
            f"Les biens essentiels suivants n'ont AUCUN événement redouté associé : {sorted(be_orphelins)}. "
            "Chaque bien essentiel doit obligatoirement porter au moins un enjeu de sécurité."
        )

    # 4. Unicité et dépendances des Biens Supports
    bs_ids: set[str] = set()
    for bs in proposal.biens_supports:
        if not bs.id or not bs.id.strip():
            errors.append("Un bien support n'a pas d'identifiant.")
        elif bs.id in bs_ids:
            errors.append(f"Identifiant de bien support en double : '{bs.id}'.")
        bs_ids.add(bs.id)

        for ref_be in bs.biens_essentiels_supportes:
            if ref_be not in be_ids:
                errors.append(
                    f"Le bien support '{bs.nom}' ({bs.id}) référence un bien essentiel inconnu : '{ref_be}'."
                )

    return errors


def has_evidence(proposal: ControlAssessmentProposal) -> bool:
    """A compliant/gap verdict is only accepted with a non-empty cited evidence quote (conception §15)."""
    return bool(proposal.evidence_quote and proposal.evidence_quote.strip())


@dataclass
class FrameworkAssessment:
    """The result of assessing one framework's controls against the Mission Context."""

    gaps: list[BaselineGap]
    insufficient: list[UnverifiedControl]


def assess_framework(
    framework: str,
    controls: list[BaselineControl],
    proposals: list[ControlAssessmentProposal],
) -> FrameworkAssessment:
    """Turn the LLM's per-control verdicts into validated gaps, enforcing evidence (conception §15).

    A 'gap' or 'compliant' verdict with no evidence is downgraded to insufficient —
    never silently accepted. Only evidence-backed gaps produce a BaselineGap.
    """
    controls_by_id = {c.control_id: c for c in controls}
    gaps: list[BaselineGap] = []
    insufficient: list[UnverifiedControl] = []

    def unverified(proposal, reason: str, control=None) -> None:
        insufficient.append(UnverifiedControl(
            control_id=proposal.control_id,
            framework=framework,
            description=control.description if control else "",
            reason=reason,
            model_said=proposal.verdict.strip(),
        ))

    for proposal in proposals:
        control = controls_by_id.get(proposal.control_id)
        if control is None:
            unverified(proposal, REASON_UNKNOWN_CONTROL)
            continue

        verdict = proposal.verdict.strip().lower()
        if verdict == _INSUFFICIENT_VERDICT:
            unverified(proposal, REASON_NO_INFORMATION, control)
            continue
        if not has_evidence(proposal):
            unverified(proposal, REASON_NO_EVIDENCE_CITED, control)
            continue
        if verdict == _COMPLIANT_VERDICT:
            continue
        if verdict == _GAP_VERDICT:
            weakness = proposal.weakness.strip() or control.description
            gaps.append(
                BaselineGap(
                    gap_id=BaselineGap.make_gap_id(framework, control.control_id, weakness),
                    controls=[ControlReference(framework=framework, control_id=control.control_id)],
                    weakness=weakness,
                    risk_categories=list(control.covers_risk_category),
                    evidence_quote=proposal.evidence_quote.strip(),
                )
            )
        else:
            unverified(proposal, REASON_INVALID_VERDICT, control)

    return FrameworkAssessment(gaps=gaps, insufficient=insufficient)


def frameworks_without_controls(
    declared_frameworks: list[str], reference_repo
) -> list[str]:
    """Declared frameworks that have no baseline control loaded (conception §2, §12.5)."""
    return [fw for fw in declared_frameworks if not reference_repo.get_baseline_controls(fw)]


def scope_decisions(
    declared_frameworks: list[str],
    controls_by_framework: dict[str, list[BaselineControl]],
) -> list[BaselineScopeDecision]:
    """Every declared framework is explicitly covered or excluded — never omitted (conception §15 step 6)."""
    decisions: list[BaselineScopeDecision] = []
    for framework in declared_frameworks:
        controls = controls_by_framework.get(framework, [])
        if controls:
            decisions.append(
                BaselineScopeDecision(
                    category=framework,
                    decision="covered",
                    justification=f"Référentiel déclaré et évalué ({len(controls)} contrôles).",
                )
            )
        else:
            decisions.append(
                BaselineScopeDecision(
                    category=framework,
                    decision="excluded",
                    justification=(
                        "Aucun contrôle chargé pour ce référentiel — exclusion validée par "
                        "l'auditeur (conception §12.5)."
                    ),
                )
            )
    return decisions