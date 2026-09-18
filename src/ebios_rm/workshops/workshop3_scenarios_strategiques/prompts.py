"""Instruction text for the Workshop 3 agent (conception §17).

Two passes, one agent: propose the strategic scenarios, then criticise its own
list and fold the near-duplicates. Both prompts state the rules the deterministic
side enforces, because a candidate that breaks one is deleted rather than
corrected — the prompt asks, assessment.py decides.
"""

from __future__ import annotations

import json

from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import Workshop3Input

SYSTEM_INSTRUCTIONS = """\
Tu es un assistant méthodologique EBIOS Risk Manager pour l'atelier 3 (scénarios \
stratégiques). Tu es assisté par l'humain, jamais l'inverse : tu proposes et tu \
argumentes, un auditeur décide.

Tes propositions passent ensuite par un filtre automatique. Ce qui enfreint une \
règle ci-dessous n'est pas corrigé : c'est supprimé, avec son motif de rejet.

Ce qu'est un scénario stratégique :
- Un chemin d'attaque de HAUT NIVEAU : une source de risque atteint l'organisation, \
éventuellement en passant par une partie prenante de son écosystème, pour \
atteindre l'objectif visé et provoquer un événement redouté.
- Il se raconte en termes de MÉTIER et d'ÉCOSYSTÈME : qui vient, par quel \
intermédiaire, pour obtenir quoi, et ce que cela coûterait à l'organisation.
- Il ne décrit JAMAIS le mode opératoire technique. « Hameçonnage », « injection \
SQL », « exploitation d'une faille », un identifiant CVE, un outil ou un nom de \
produit relèvent de l'atelier 4 et n'ont pas leur place ici.

Règles absolues :
- Un scénario porte sur UN couple SR/OV existant, dont tu reprends le couple_id \
tel quel. Tu n'inventes aucun couple, aucune source de risque et aucun objectif.
- Une partie prenante est une entité réelle du dossier : un prestataire, un \
fournisseur, un sous-traitant, un partenaire ou un canal d'accès effectivement \
mentionné dans le contexte. Reprends la formulation du contexte. Une partie \
prenante que le dossier ne mentionne pas fait supprimer le scénario.
- Un scénario peut n'avoir aucune partie prenante : c'est le cas où la source de \
risque atteint l'organisation directement. Laisse alors la liste vide plutôt que \
d'inventer un intermédiaire.
- Toute affirmation s'appuie sur le contexte fourni ; tu cites les champs utilisés \
dans derived_from_fact_fields, avec leur nom exact. Un scénario sans justification, \
sans résumé, ou sans aucun champ cité est supprimé.
- Tu n'inventes ni gravité, ni vraisemblance, ni pertinence, ni score, ni échelle. \
Elles sont reprises des ateliers 1 et 2 par le code, et ne t'appartiennent pas.
- Un scénario par couple : deux formulations du même couple ne font pas deux \
scénarios.
- Si aucun scénario n'est défendable, tu renvoies une liste vide plutôt qu'un \
contenu inventé.
- Tu réponds uniquement au format structuré demandé, sans texte hors schéma.
"""


def _context_block(w3_input: Workshop3Input) -> str:
    return json.dumps(
        {
            "organisation_nom": w3_input.organisation_nom,
            "secteur_activite": w3_input.secteur_activite,
            "contexte": w3_input.contexte,
        },
        ensure_ascii=False, indent=2, default=str,
    )


def _couples_block(w3_input: Workshop3Input) -> str:
    """Each couple with both its ends spelled out — the scenario is written from these.

    The feared events travel with the assets they concern. A scenario ends on what
    it would cost the organisation, and that sentence is already written in atelier
    1: without it the model invents its own consequence, in its own words, next to a
    gravité that was computed from the real one.
    """
    sources = {s.id: s for s in w3_input.sources_risque}
    objectifs = {o.id: o for o in w3_input.objectifs_vises}
    assets = {a.id: a for a in w3_input.biens_essentiels}
    events: dict[str, list[dict]] = {}
    for event in w3_input.evenements_redoutes:
        events.setdefault(event.bien_essentiel_id, []).append(
            {"description": event.description, "gravite": event.gravite.value}
        )
    return json.dumps(
        [
            {
                "couple_id": c.id,
                "evenements_redoutes_associes": [
                    e for b in c.biens_essentiels_ids for e in events.get(b, [])
                ],
                "source_de_risque": (
                    {"nom": sources[c.source_risque_id].nom,
                     "categorie": sources[c.source_risque_id].categorie_libelle,
                     "motivation": sources[c.source_risque_id].motivation}
                    if c.source_risque_id in sources else c.source_risque_id
                ),
                "objectif_vise": (
                    {"description": objectifs[c.objectif_vise_id].description,
                     "finalite": objectifs[c.objectif_vise_id].finalite_libelle}
                    if c.objectif_vise_id in objectifs else c.objectif_vise_id
                ),
                "biens_essentiels_vises": [
                    {"id": b, "nom": assets[b].nom} if b in assets else {"id": b}
                    for b in c.biens_essentiels_ids
                ],
                "valeurs_metier": c.valeurs_metier,
            }
            for c in w3_input.couples
        ],
        ensure_ascii=False, indent=2,
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


def _known_fields(w3_input: Workshop3Input) -> str:
    return json.dumps(sorted(w3_input.contexte), ensure_ascii=False)


def scenarios_prompt(w3_input: Workshop3Input, revision_notes: list[str] | None = None) -> str:
    """Pass 1 — propose one strategic scenario per plausible couple (§17 step 18)."""
    return (
        "Pour chacun des couples SR/OV retenus en atelier 2, écris le scénario "
        "stratégique correspondant : par quel chemin cette source de risque "
        "atteindrait-elle cette organisation, et qu'obtiendrait-elle ?\n"
        "Raisonne dans cet ordre : la source de risque, le chemin (direct, ou via "
        "une partie prenante nommée dans le contexte), le bien essentiel touché, "
        "puis ce que cela produit pour l'organisation.\n"
        "Pour chaque scénario :\n"
        "  - couple_id : repris tel quel dans la liste ci-dessous ;\n"
        "  - resume : le chemin en une à deux phrases, dans les termes de cette "
        "organisation, terminé par ce que cela produit — reprends l'événement "
        "redouté associé au couple plutôt que d'en formuler un autre ;\n"
        "  - parties_prenantes : les entités du dossier empruntées par ce chemin, "
        "avec la formulation du contexte ; liste vide si l'attaque est directe ;\n"
        "  - justification : pourquoi ce chemin est le plus plausible ici ;\n"
        "  - derived_from_fact_fields : au moins un champ, uniquement parmi : "
        f"{_known_fields(w3_input)}.\n"
        "Les parties prenantes se lisent dans le contexte, principalement sous "
        "interconnexions_tiers, fournisseurs_tiers_critiques, sous_traitants_donnees, "
        "fournisseurs_cloud et infogerance. Une entité qui n'y figure pas fait "
        "supprimer le scénario, même si elle est vraisemblable.\n"
        "Attendu : « le concurrent obtient la liste confidentielle en visant les "
        "échanges avec le ministère qui la fournit » — un chemin, avec qui il passe "
        "et ce qu'il obtient. Refusé : « exploitation d'une faille du portail de "
        "réservation » — une technique, qui relève de l'atelier 4.\n"
        "Un scénario par couple, au plus. Un couple pour lequel aucun chemin "
        "plausible ne se dégage est omis : c'est un résultat, pas un oubli."
        + _revision_block(revision_notes)
        + f"\n\nCOUPLES SR/OV RETENUS (atelier 2):\n{_couples_block(w3_input)}"
        + f"\n\nCONTEXTE DE L'ORGANISATION:\n{_context_block(w3_input)}"
    )


def critique_prompt(
    w3_input: Workshop3Input, scenarios: list[StrategicScenario],
) -> str:
    """Pass 2 — the same agent prunes its own near-duplicates (§17 step 18)."""
    scenarios_block = json.dumps(
        [
            {"id": s.id, "couple_id": s.couple_id, "resume": s.resume,
             "parties_prenantes": s.parties_prenantes,
             "biens_essentiels": s.biens_essentiels_ids}
            for s in scenarios
        ],
        ensure_ascii=False, indent=2,
    )
    return (
        "Relis la liste de scénarios stratégiques ci-dessous et signale les "
        "QUASI-DOUBLONS : deux scénarios qui raconteraient, pour l'auditeur, la "
        "même histoire — même type d'acteur, même chemin, même finalité — au point "
        "que les traiter séparément en atelier 4 produirait deux fois le même "
        "travail.\n"
        "Renvoie exactement un verdict par scénario de la liste, ni plus ni moins :\n"
        "  - scenario_id : son id ;\n"
        "  - raison : ce qui justifie ton verdict ;\n"
        "  - doublon_de : vide si le scénario doit être conservé ; sinon l'id du "
        "scénario qu'il répète.\n"
        "Deux scénarios portant sur des sources de risque, des objectifs ou des "
        "biens essentiels différents ne sont PAS des doublons, même si le chemin se "
        "ressemble : ils se traiteront différemment en atelier 4. Dans le doute, "
        "conserve — un scénario écarté à tort ne sera jamais étudié.\n"
        "Ne cherche pas à raccourcir la liste : signale un doublon seulement quand "
        "il en est un, et une liste sans aucun doublon est une réponse valide."
        + f"\n\nSCÉNARIOS PROPOSÉS:\n{scenarios_block}"
        + f"\n\nCONTEXTE DE L'ORGANISATION:\n{_context_block(w3_input)}"
    )
