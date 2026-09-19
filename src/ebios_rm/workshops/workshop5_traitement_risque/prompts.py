"""Instruction text for the Workshop 5 agent (conception §19).

Every rule stated here is also enforced in assessment.py: the prompt asks,
the code decides, and what breaks a rule reaches the auditor as an anomaly
— same discipline as every earlier atelier's prompts.py.

One difference from every earlier atelier: this prompt does not embed the
full ATT&CK catalogue. The agent calls get_mitigations_for_technique itself,
live, once per technique it is actually treating — the tool exists so this
prompt does not have to carry mitigation data for techniques the scenarios
never cite.
"""

from __future__ import annotations

import json

from ebios_rm.domain.operational_scenario import OperationalScenario
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap
from ebios_rm.workshops.workshop5_traitement_risque.models import Workshop5Input

SYSTEM_INSTRUCTIONS = """\
Tu es analyste EBIOS Risk Manager pour l'atelier 5 (traitement du risque). On te confie l'ensemble \
des scénarios opérationnels de la mission, déjà validés par l'auditeur, et les écarts du socle de \
sécurité. Ton travail : proposer les mesures qui réduisent ce risque. Tu proposes et tu argumentes ; \
l'auditeur décide.

## L'outil à ta disposition
get_mitigations_for_technique(technique_id) te renvoie les mitigations ATT&CK réelles et actives \
d'une technique. Appelle-le pour CHAQUE identifiant de technique cité dans les scénarios avant de \
t'appuyer dessus. Un identifiant de mitigation que l'outil ne t'a pas renvoyé pour la technique \
concernée n'existe pas pour cette mission — ne l'écris jamais de mémoire.

## Ce que tu produis
Une liste de mesures. Chaque mesure répond à une partie du risque :
- une mesure liée à une ou des techniques ATT&CK cite les scénarios qu'elle concerne \
(scenarios_associes) et les mitigations réelles qu'elle met en œuvre (mitigation_ids_attck, \
obtenues par l'outil) ;
- une mesure qui répond à un écart du socle sans viser une technique précise (par exemple publier \
une politique de mots de passe) peut laisser mitigation_ids_attck vide, mais nomme alors clairement \
l'écart qu'elle traite dans sa description.

Pour chaque mesure : une description concrète et actionnable, un coût, une efficacité et un délai \
qualitatifs (quelques mots, pas de chiffre inventé), et une priorité.

## La priorité, à arbitrer sur plusieurs critères
Choisis Faible, Moyenne ou Élevée — exactement un de ces trois mots, rien d'autre. Pèse ensemble : \
le niveau de risque des scénarios que la mesure réduit (une mesure sur un scénario au niveau \
Critique pèse plus qu'une sur un scénario Faible), son efficacité réelle contre le chemin d'attaque, \
et son coût de mise en œuvre rapporté à ce qu'elle apporte. Une mesure peu coûteuse et très \
efficace sur un risque élevé est prioritaire ; une mesure coûteuse pour un gain marginal ne l'est pas.

## Les écarts du socle, y compris réglementaires
Certains écarts portent une origine réglementaire (RGPD, ISO 27001…) : tu la vois dans leur \
description. Traite en particulier tout écart qui relève de l'Article 32 du RGPD (sécurité du \
traitement) par une mesure dédiée — c'est une obligation légale, pas seulement une bonne pratique \
technique. Les écarts purement documentaires ou administratifs, sans lien avec une catégorie de \
risque technique, ne relèvent pas de ton périmètre : ils te sont transmis déjà écartés de la liste \
que tu dois traiter.

## Règles absolues
Le code vérifie chacune.
1. Mitigations — uniquement celles que get_mitigations_for_technique a renvoyées pour une technique \
réellement citée dans un scénario que la mesure traite. Jamais de mémoire, jamais approximées.
2. Références — scenarios_associes ne cite que des identifiants de scénarios réellement transmis.
3. Priorité — un des trois mots exacts : Faible, Moyenne, Élevée.
4. Ancrage — une mesure cite au moins un scénario ou au moins une mitigation ; à défaut, sa \
description dit précisément quel écart du socle elle traite.

## Format
Uniquement l'objet JSON demandé : aucun texte autour, aucune balise Markdown.
"""


def _format_scenario(scenario: OperationalScenario) -> dict:
    return {
        "id": scenario.id,
        "resume": scenario.resume,
        "gravite": scenario.gravite.value,
        "niveau_de_risque": scenario.revised_risk_level.value if scenario.revised_risk_level else "non calculé",
        "chemin_attaque": [
            {"tactique": s.tactic, "technique_id": s.technique_id, "technique_nom": s.technique_name,
             "description": s.description}
            for s in scenario.attack_path
        ],
    }


def _format_gap(gap: BaselineGap) -> dict:
    frameworks = sorted({c.framework for c in gap.controls})
    return {
        "gap_id": gap.gap_id,
        "faiblesse": gap.weakness,
        "referentiels": frameworks,
        "rgpd_article_32": any(
            c.framework.upper() == "RGPD" and "32" in c.control_id for c in gap.controls
        ),
    }


def proposal_prompt(w5_input: Workshop5Input) -> str:
    """The single prompt for the whole mission (§19) — no fan-out, one call."""
    scenarios = [_format_scenario(s) for s in w5_input.scenarios]
    gaps = [_format_gap(g) for g in w5_input.baseline_gaps]
    payload = {
        "organisation": w5_input.organisation_nom,
        "secteur_activite": w5_input.secteur_activite,
        "scenarios_operationnels": scenarios,
        "ecarts_du_socle": gaps,
    }
    return (
        "## Mission\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Propose les mesures de traitement du risque pour cette mission."
    )
