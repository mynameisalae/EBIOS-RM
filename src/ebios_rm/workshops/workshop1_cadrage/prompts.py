"""Instruction text for the Workshop 1 agent (conception §2, §4, §5, §15, §15.1).

The system instruction encodes the principe directeur: the AI extracts, analyses,
proposes, and cites — it never invents information, never assumes a missing value,
never resolves a contradiction. Those are the auditor's, handled outside the model.
"""

from __future__ import annotations

import json

from ebios_rm.domain.essential_asset import EssentialAsset
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.repositories.reference_repository import BaselineControl

SYSTEM_INSTRUCTIONS = """\
Tu es un assistant méthodologique EBIOS Risk Manager pour l'atelier 1 (cadrage et \
socle de sécurité). Tu es assisté par l'humain, jamais l'inverse.

Règles absolues :
- Tu n'inventes JAMAIS une information. Toute affirmation sur l'organisation doit \
s'appuyer sur un fait présent dans le Mission Context fourni.
- Tu ne supposes JAMAIS une information manquante. Si une information manque, tu \
le signales, tu ne la complètes pas.
- Tu ne résous JAMAIS une contradiction toi-même ; ce n'est pas ton rôle ici.
- Évaluation par la preuve : tout verdict (contrôle conforme, écart, pertinence \
d'une disposition légale) doit citer le passage précis du Mission Context qui le \
justifie. Un verdict sans citation est invalide.
- La gravité d'un événement redouté est exactement l'une de ces quatre valeurs : \
Minimale, Significative, Grave, Critique.
- La catégorie d'impact est exactement l'une de ces cinq valeurs : financier, \
fonctionnement, image, juridique, vie_privee_personnes_concernees.
- Tu réponds uniquement au format structuré demandé, sans texte hors schéma.
"""


def _mission_context_block(mc: MissionContext) -> str:
    facts = [
        {
            "field_name": f.field_name,
            "value": f.value,
            "origin": f.origin.value,
            "confidence": f.confidence.value,
            "source_quote": f.source_quote,
        }
        for f in mc.facts
    ]
    return json.dumps(
        {
            "organisation_nom": mc.organisation_nom,
            "secteur_activite": mc.secteur_activite,
            "applicable_frameworks": mc.applicable_frameworks,
            "facts": facts,
        },
        ensure_ascii=False,
        indent=2,
    )


def _revision_block(revision_notes: list[str] | None) -> str:
    """The auditor's rejection reasons, injected only on a redo (conception §12.6)."""
    if not revision_notes:
        return ""
    joined = "\n".join(f"- {note}" for note in revision_notes if note and note.strip())
    if not joined:
        return ""
    return (
        "\n\nREMARQUES DE L'AUDITEUR SUR LA OU LES VERSIONS PRÉCÉDENTES (à corriger "
        "impérativement dans cette nouvelle proposition) :\n" + joined + "\n"
    )


def cadrage_prompt(mc: MissionContext, revision_notes: list[str] | None = None) -> str:
    revision = _revision_block(revision_notes)
    return (
        "À partir du Mission Context suivant (composé uniquement de faits validés), "
        "propose les biens essentiels, les biens supports, et les événements redoutés "
        "avec leur gravité et catégorie d'impact. Pour chaque élément, renseigne "
        "derived_from_fact_fields avec les field_name des faits utilisés. N'invente aucun "
        "bien ni événement qui ne découle pas d'un fait."
        + revision
        + f"\n\nMISSION CONTEXT:\n{_mission_context_block(mc)}"
    )


def controls_prompt(mc: MissionContext, framework: str, controls: list[BaselineControl],
                    revision_notes: list[str] | None = None) -> str:
    control_list = json.dumps(
        [{"control_id": c.control_id, "description": c.description, "category": c.category} for c in controls],
        ensure_ascii=False,
        indent=2,
    )
    return (
        f"Évalue le socle de sécurité de l'organisation contre le référentiel {framework}. "
        "Pour chaque contrôle, rends un verdict parmi 'compliant', 'gap', "
        "'insufficient_information'. Un verdict 'compliant' ou 'gap' DOIT citer, dans "
        "evidence_quote, le passage précis du Mission Context qui le justifie ; sans "
        "preuve, utilise 'insufficient_information'. Pour un 'gap', renseigne weakness "
        "(l'écart constaté, formulé sans référence au référentiel)."
        + _revision_block(revision_notes)
        + f"\n\nCONTRÔLES:\n{control_list}\n\n"
        f"MISSION CONTEXT:\n{_mission_context_block(mc)}"
    )


def legal_impacts_prompt(
    mc: MissionContext, events: list[FearedEvent], provisions: list[BaselineControl],
    revision_notes: list[str] | None = None, assets: list[EssentialAsset] | None = None,
) -> str:
    # The essential asset travels with its event: two events can read alike ("accès non
    # autorisé...") while concerning entirely different assets, and with only the
    # description to go on, the evidence of one gets attached to the other.
    by_id = {a.id: a for a in (assets or [])}
    events_block = json.dumps(
        [
            {
                "id": e.id,
                "description": e.description,
                "bien_essentiel": (
                    f"{by_id[e.bien_essentiel_id].nom} — {by_id[e.bien_essentiel_id].description}"
                    if e.bien_essentiel_id in by_id else e.bien_essentiel_id
                ),
            }
            for e in events
        ],
        ensure_ascii=False, indent=2,
    )
    provisions_block = json.dumps(
        [
            {"control_id": p.control_id, "framework": p.framework, "details": p.legal_impact_details}
            for p in provisions
        ],
        ensure_ascii=False,
        indent=2,
    )
    return (
        "Pour chaque événement redouté, indique quelles dispositions légales ci-dessous "
        "sont pertinentes, et pour chacune cite le fait précis du Mission Context qui "
        "établit cette pertinence (evidence_mission_context). N'associe une disposition "
        "que si un fait la justifie réellement."
        + _revision_block(revision_notes)
        + f"\n\nÉVÉNEMENTS REDOUTÉS:\n{events_block}\n\n"
        f"DISPOSITIONS LÉGALES:\n{provisions_block}\n\n"
        f"MISSION CONTEXT:\n{_mission_context_block(mc)}"
    )
