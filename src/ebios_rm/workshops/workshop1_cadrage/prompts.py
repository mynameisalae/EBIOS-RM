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

Règles méthodologiques absolues :
- Définition stricte des Biens Essentiels (BE) : Un bien essentiel est EXCLUSIVEMENT \
un processus métier critique ou une information sensible ayant de la valeur pour \
l'organisation. Un serveur, un équipement réseau, un logiciel, un terminal ou un \
site physique n'est JAMAIS un bien essentiel (ce sont des Biens Supports).
- Définition des Biens Supports (BS) : Ce sont les composants techniques et \
organisationnels (serveurs, logiciels, réseaux, postes, prestataires) qui \
supportent les biens essentiels.
- Règle de couverture totale des enjeux : CHACUN des biens essentiels identifiés \
(sans aucune exception) DOIT être ciblé par au moins un événement redouté (ER). \
Un bien essentiel sans événement redouté n'a pas de sens méthodologique.
- Règle de dépendance des supports : Tout bien support doit lister dans \
biens_essentiels_supportes les identifiants exacts des biens essentiels qu'il supporte.
- Calibrage de la gravité : La gravité d'un événement redouté (Minimale, Significative, \
Grave, Critique) doit découler strictement des faits d'impact du contexte (impact_arret, \
impact_divulgation, impact_alteration, seuil_incident_inacceptable).
- Catégories d'impact : exactement l'une de ces cinq valeurs : financier, \
fonctionnement, image, juridique, vie_privee_personnes_concernees.
- Évaluation par la preuve : Tout verdict ou proposition doit s'appuyer sur le Mission \
Context et citer les champs utilisés dans derived_from_fact_fields.
- Tu n'inventes AUCUNE information non mentionnée dans le contexte.
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
        "À partir du Mission Context fourni, propose le cadrage de l'organisation :\n"
        "1. Biens essentiels (id: BE-01, BE-02...) : Processus métiers et informations "
        "sensibles uniquement (JAMAIS d'infrastructure, de serveurs ou de logiciels ici).\n"
        "2. Biens supports (id: BS-01, BS-02...) : Composants informatiques ou humains "
        "qui supportent ces biens essentiels. Renseigne pour chacun 'biens_essentiels_supportes'.\n"
        "3. Événements redoutés (id: ER-01, ER-02...) : OBLIGATOIREMENT au moins un événement "
        "redouté par bien essentiel listé. Indique pour chacun le bien_essentiel_id exact, "
        "la categorie_impact, et la gravite motivée par les seuils d'impact décrits.\n"
        "Chaque élément doit citer dans derived_from_fact_fields les noms exacts des faits utilisés."
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