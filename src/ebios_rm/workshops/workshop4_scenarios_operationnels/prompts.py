"""Instruction text for the Workshop 4 sub-agents and the coherence pass (conception §18).

Every rule stated here is also enforced in assessment.py: the prompt asks, the code
decides, and what breaks a rule reaches the auditor as an anomaly.

Layout, deliberately unlike ateliers 2 and 3: the long reference material comes
first and the instructions last, each block in its own tag. An analysis prompt is
mostly catalogue — about 24 000 characters of ATT&CK — and instructions placed
after a long document are followed better than instructions buried in front of
it. It also makes the first ~80 % of the prompt identical across the N sub-agents
of a run, which providers that cache prefixes reuse instead of billing N times.
"""

from __future__ import annotations

import json

from ebios_rm.domain.enums import ImpactType
from ebios_rm.domain.operational_scenario import STATUT_A_REFAIRE, OperationalScenario
from ebios_rm.repositories.attack_repository import AttackCatalogue, AttackTechnique
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import (
    EXPERT_QUESTION_PREFIX,
    RISK_CATEGORIES,
    Workshop4Input,
)

SYSTEM_INSTRUCTIONS = """\
Tu es analyste EBIOS Risk Manager pour l'atelier 4 (scénarios opérationnels). On te confie UN \
scénario stratégique déjà validé par l'auditeur. D'autres analystes traitent les autres scénarios \
en parallèle sans que vous vous voyiez : ton analyse doit se suffire à elle-même. Tu proposes et \
tu argumentes ; l'auditeur décide.

## Ce que tu produis
Le scénario opérationnel : la manière concrète dont la source de risque réaliserait ce scénario \
stratégique contre CETTE organisation — la suite des actions élémentaires qu'elle mènerait sur ses \
biens supports, du premier contact jusqu'à l'événement redouté, exprimée en tactiques et techniques \
MITRE ATT&CK. Il se lit en quatre temps :
- Connaître — se renseigner sur la cible, seulement si cela conditionne la suite (repérer un service \
exposé, identifier les personnes à piéger).
- Rentrer — obtenir un premier accès, par le chemin que désigne le scénario stratégique (une partie \
prenante, un service exposé, un accès distant…). Une source interne, ou un prestataire, qui dispose \
déjà d'un accès l'utilise : c'est son étape « Rentrer ».
- Trouver — progresser jusqu'aux biens supports du bien essentiel visé : reconnaissance interne, \
identifiants, privilèges, déplacement, persistance, discrétion.
- Exploiter — l'action qui produit l'événement redouté : vol, altération, destruction, chiffrement, \
indisponibilité.

## Règles absolues
Le code vérifie chacune. Un manquement n'est pas corrigé en silence : il apparaît comme anomalie \
devant l'auditeur, qui renvoie l'analyse.
1. Identifiants ATT&CK — uniquement ceux du catalogue fourni, recopiés avec leur nom exact. Jamais \
de mémoire : le catalogue est la version de référence de la mission, et des identifiants d'anciennes \
versions en ont été retirés ou déplacés (la tactique « defense-evasion », par exemple, n'y existe \
plus). Si aucune technique du catalogue ne correspond à une action, technique_id vaut null et la \
description porte l'action : c'est accepté. Un identifiant approximatif ne l'est pas.
2. Tactiques — le nom court d'une tactique du catalogue (« initial-access »), et la technique retenue \
figure sous cette tactique dans le catalogue. Une technique par étape.
3. Ancrage — chaque étape repose sur ce que le dossier dit de cette organisation : un bien support, \
un élément du contexte technique, un écart du socle. Tu n'inventes ni équipement, ni logiciel, ni \
produit, ni partie prenante, ni mesure de sécurité. Quand le dossier ne dit pas si une protection \
existe, tu ne la supposes ni présente ni absente : tu le dis, et cette incertitude figure dans le \
motif de révision.
4. Écarts du socle — exactement une entrée par écart transmis. impact_on_scenario n'est JAMAIS vide, \
quel que soit impact_type : « no_impact » et « not_relevant » sont des affirmations et se \
justifient comme les autres.
5. Vraisemblance — une valeur de l'échelle V1 à V4 et elle seule, écrite après son motif. Tu ne \
calcules pas le niveau de risque : le code le lit dans la matrice gravité × vraisemblance.
6. Périmètre — tu ne changes ni la source de risque, ni l'objectif visé, ni les biens essentiels, ni \
la gravité : ils viennent des ateliers précédents. Tu ne recommandes aucune mesure : c'est l'atelier 5.

## Échelle de vraisemblance
- V1 Peu vraisemblable — la source de risque a peu de chances d'atteindre son objectif par ce mode opératoire.
- V2 Vraisemblable — elle est susceptible de l'atteindre.
- V3 Très vraisemblable — elle l'atteindra probablement.
- V4 Quasi certain — elle l'atteindra très certainement.
La vraisemblance initiale (atelier 2) répond seulement à « cette source vise-t-elle cette \
organisation ? ». La vraisemblance révisée répond à « réussirait-elle par ce chemin, ici ? ». Elle \
monte quand des écarts rendent faciles, pour les moyens de cette source, les étapes décisives ; elle \
baisse quand une étape décisive exige des moyens que la source n'a pas, ou bute sur une protection \
que le dossier atteste. Le maillon le plus difficile du chemin borne l'ensemble.

## Effet d'un écart sur le scénario (impact_type)
- increases_likelihood — l'écart rend possible ou facilite une étape du chemin : nomme l'étape.
- increases_impact — l'écart aggrave la conséquence (propagation, durée, restauration impossible) \
sans faciliter l'accès.
- no_impact — l'écart touche un domaine que le chemin traverse, mais ne change ici ni sa difficulté \
ni sa conséquence : dis pourquoi.
- not_relevant — l'écart ne concerne aucune étape ni aucune conséquence de ce scénario : dis en une \
phrase ce qu'il concerne.

## Format
Uniquement l'objet JSON demandé : aucun texte autour, aucune balise Markdown.
"""

COHERENCE_INSTRUCTIONS = """\
Tu es le relecteur de cohérence de l'atelier 4 d'une étude EBIOS Risk Manager. Les scénarios \
opérationnels qu'on te soumet ont été construits séparément — un analyste par scénario, sans qu'ils \
se voient — puis confirmés un par un par l'auditeur. Ton seul travail : repérer ce qui ne tient pas \
quand on les lit ensemble. Tu ne réécris aucun scénario et tu ne recommandes aucune mesure.

Trois constats possibles :
- techniques_contradictoires — deux scénarios font des hypothèses incompatibles sur le même élément \
du système : l'un franchit une protection que l'autre juge bloquante, le même bien support est jugé \
facile d'accès ici et difficile là, le même accès est supposé avec et sans authentification forte.
- doublon — deux scénarios suivent pour l'essentiel le même chemin (même entrée, même progression, \
même action finale) vers le même bien essentiel : l'atelier 5 ferait deux fois le même travail.
- revision_niveau_risque — deux scénarios partagent leurs étapes décisives et leurs écarts, pour des \
sources aux moyens comparables, mais n'ont pas la même vraisemblance révisée sans que leurs motifs \
expliquent la différence : tu proposes, pour l'un des deux, la valeur qui rétablit la cohérence.

Ce qui n'est PAS une incohérence : des sources de risque différentes — moyens, motivation, point de \
départ — justifient des vraisemblances différentes sur un chemin semblable ; des objectifs différents \
font des scénarios distincts même quand l'entrée est la même.

Une liste vide est la bonne réponse quand l'ensemble tient. N'invente pas de constat pour paraître \
utile : chaque constat oblige l'auditeur à rouvrir des analyses.

Format : uniquement l'objet JSON demandé, sans texte autour, sans balise Markdown.
"""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def catalogue_block(catalogue: AttackCatalogue) -> str:
    """Every active technique under each of its tactics, sub-techniques inline.

    A technique with several tactics is listed under each: a path is written tactic
    by tactic, and a technique missing from the tactic being looked at gets replaced
    by one remembered from an older version.
    """
    children: dict[str, list[AttackTechnique]] = {}
    for technique in catalogue.techniques.values():
        if technique.parent_id in catalogue.techniques:
            children.setdefault(technique.parent_id, []).append(technique)

    lines: list[str] = []
    for tactic in catalogue.tactics:
        lines.append(f"## {tactic}")
        for technique in catalogue.techniques.values():
            if technique.parent_id in catalogue.techniques or tactic not in technique.tactics:
                continue
            subs = "; ".join(f".{s.technique_id.split('.')[1]} {s.name}"
                             for s in children.get(technique.technique_id, []))
            lines.append(f"{technique.technique_id} {technique.name}" + (f" [{subs}]" if subs else ""))
    return "\n".join(lines)


def _context_block(w4_input: Workshop4Input) -> str:
    expert = [
        {"champ": f.field_name, "question": f.question, "reponse": f.value}
        for f in w4_input.faits_contexte
        if f.field_name.startswith(EXPERT_QUESTION_PREFIX) and f.value not in (None, "")
    ]
    return _json({
        "organisation_nom": w4_input.organisation_nom,
        "secteur_activite": w4_input.secteur_activite,
        "contexte": {k: v for k, v in w4_input.contexte.items() if not k.startswith(EXPERT_QUESTION_PREFIX)},
        "questions_expertes": expert,
    })


def _supports_block(w4_input: Workshop4Input) -> str:
    return _json([
        {"id": s.id, "nom": s.nom, "type_support": s.type_support, "description": s.description,
         "biens_essentiels_supportes": s.biens_essentiels_supportes}
        for s in w4_input.biens_supports
    ])


def _gaps_block(w4_input: Workshop4Input) -> str:
    return _json([
        {"gap_id": g.gap_id, "weakness": g.weakness, "risk_categories": g.risk_categories}
        for g in w4_input.baseline_gaps
    ])


def _scenario_block(w4_input: Workshop4Input, pending: OperationalScenario) -> str:
    scenario = next(s for s in w4_input.scenarios if s.id == pending.scenario_strategique_id)
    sources = {s.id: s for s in w4_input.sources_risque}
    objectifs = {o.id: o for o in w4_input.objectifs_vises}
    assets = {a.id: a for a in w4_input.biens_essentiels}
    source = sources.get(scenario.source_risque_id)
    objectif = objectifs.get(scenario.objectif_vise_id)
    return _json({
        "id": scenario.id,
        "resume": scenario.resume,
        "justification": scenario.justification,
        "source_de_risque": (
            {"nom": source.nom, "categorie": source.categorie_libelle, "motivation": source.motivation,
             "description": source.description}
            if source else scenario.source_risque_id
        ),
        "objectif_vise": (
            {"description": objectif.description, "finalite": objectif.finalite_libelle}
            if objectif else scenario.objectif_vise_id
        ),
        "parties_prenantes": scenario.parties_prenantes,
        "biens_essentiels_vises": [
            {"id": a, "nom": assets[a].nom, "description": assets[a].description} if a in assets else {"id": a}
            for a in scenario.biens_essentiels_ids
        ],
        "biens_supports_des_biens_vises": [
            s.id for s in w4_input.biens_supports
            if set(s.biens_essentiels_supportes) & set(scenario.biens_essentiels_ids)
        ],
        "evenements_redoutes": [
            {"id": e.id, "description": e.description, "gravite": e.gravite.value}
            for e in w4_input.evenements_redoutes if e.id in scenario.evenements_redoutes_ids
        ],
        "gravite": scenario.gravite.value,
        "vraisemblance_initiale": scenario.vraisemblance_initiale.value,
    })


def _previous_analysis(pending: OperationalScenario) -> dict:
    return {
        "resume": pending.resume,
        "attack_path": [
            {"tactic": s.tactic, "technique_id": s.technique_id, "technique_name": s.technique_name,
             "description": s.description, "bien_support_id": s.bien_support_id}
            for s in pending.attack_path
        ],
        "baseline_gaps_considered": [
            {"gap_id": g.gap_id, "impact_type": g.impact_type.value, "impact_on_scenario": g.impact_on_scenario}
            for g in pending.baseline_gaps_considered
        ],
        "likelihood_revision_reason": pending.likelihood_revision_reason,
        "revised_likelihood": pending.revised_likelihood.value if pending.revised_likelihood else None,
        "anomalies_relevees_par_le_code": [a.message for a in pending.anomalies],
    }


def revision_block(pending: OperationalScenario) -> str:
    """The redo of a scenario the auditor sent back (§18 step 25).

    The rejected answer is shown so that it can be explicitly excluded (§21): at low
    temperature, a model asked the same question again gives the same answer again.
    """
    if not pending.iterations or not pending.motifs_auditeur:
        return ""
    motifs = "\n".join(f"- {m}" for m in pending.motifs_auditeur)
    if pending.statut == STATUT_A_REFAIRE:
        mode, instruction = "refaire", (
            "L'analyse précédente est écartée dans son ensemble. Construis un autre mode opératoire : "
            "un autre point d'entrée, ou une autre progression vers les biens supports. Si le dossier "
            "n'en permet réellement aucun autre, reprends le même chemin et explique pourquoi dans "
            "likelihood_revision_reason."
        )
    else:
        mode, instruction = "reviser", (
            "Corrige chaque point visé par un motif. Ce qu'aucun motif ne vise peut être conservé s'il "
            "reste exact ; ce qu'un motif vise doit changer — reproduire la même réponse sur ce point "
            "ferait renvoyer l'analyse une nouvelle fois."
        )
    return (
        f'<reprise mode="{mode}" analyse_precedente="{pending.iterations}">\n'
        f"L'auditeur a renvoyé l'analyse précédente de ce scénario. Ses motifs :\n{motifs}\n\n"
        f"Analyse précédente :\n{_json(_previous_analysis(pending))}\n\n"
        f"Consigne de reprise : {instruction}\n"
        "</reprise>\n\n"
    )


def analysis_prompt(w4_input: Workshop4Input, pending: OperationalScenario, catalogue: AttackCatalogue) -> str:
    """One sub-agent, one strategic scenario (§18 step 22) — the same template for all N."""
    gaps = (
        "3. baseline_gaps_considered — une entrée par écart de <ecarts_socle>, dans l'ordre de la liste : "
        "gap_id repris tel quel ; impact_type parmi "
        f"{', '.join(t.value for t in ImpactType)} ; impact_on_scenario, une phrase propre à ce scénario "
        "(pour increases_likelihood, l'étape concernée).\n\n"
        if w4_input.baseline_gaps else
        "3. baseline_gaps_considered — liste vide : aucun écart du socle n'a été transmis.\n\n"
    )
    return (
        f'<catalogue_attck version="{catalogue.version}">\n'
        "Sous chaque tactique, les techniques qui en relèvent, sous-techniques entre crochets : "
        "« T1566 Phishing [.001 Spearphishing Attachment] » signifie que T1566.001 existe et "
        "s'appelle Spearphishing Attachment.\n"
        f"{catalogue_block(catalogue)}\n"
        "</catalogue_attck>\n\n"
        f"<contexte_technique>\n{_context_block(w4_input)}\n</contexte_technique>\n\n"
        f"<biens_supports>\n{_supports_block(w4_input)}\n</biens_supports>\n\n"
        f"<ecarts_socle>\n{_gaps_block(w4_input)}\n</ecarts_socle>\n\n"
        f"<scenario_strategique>\n{_scenario_block(w4_input, pending)}\n</scenario_strategique>\n\n"
        + revision_block(pending)
        + "<consignes>\n"
        f"Analyse le scénario stratégique {pending.scenario_strategique_id}. Travaille dans cet ordre, "
        "qui est celui des champs à remplir.\n\n"
        "1. resume — le mode opératoire en une ou deux phrases, dans les termes de l'organisation : par "
        "où la source entre, comment elle progresse, ce qu'elle fait à la fin, et l'événement redouté "
        "qui en résulte.\n\n"
        "2. attack_path — les étapes dans l'ordre chronologique, en général 4 à 8 : chaque maillon "
        "décisif doit apparaître, mais ce n'est pas l'inventaire des techniques possibles. Un seul "
        "chemin, le plus plausible pour cette source dans ce dossier. Pour chaque étape :\n"
        "   - tactic : le nom court d'une tactique du catalogue ;\n"
        "   - technique_id et technique_name : tels qu'ils figurent au catalogue sous cette tactique — "
        "la sous-technique quand le dossier permet de la préciser, sinon la technique parente ; null "
        "et \"\" si aucune ne convient ;\n"
        "   - description : l'action concrète, avec les mots du dossier — « se connecter au VPN des "
        "portables itinérants avec le mot de passe d'un salarié », pas « accès initial » ;\n"
        "   - bien_support_id : l'identifiant, pris dans <biens_supports>, du bien support sur lequel "
        "porte l'action ; \"\" si elle ne porte sur aucun d'eux ;\n"
        "   - justification : ce qui rend l'étape réalisable ICI — le champ du contexte, le bien "
        "support ou le gap_id sur lequel elle s'appuie, et ce qu'il dit.\n\n"
        + gaps
        + "4. likelihood_revision_reason — pars de la vraisemblance initiale "
        f"({pending.vraisemblance_initiale.value}). Nomme le maillon le plus difficile du chemin, ce "
        "qui le rend facile ou difficile pour cette source (écarts, protections attestées, moyens de "
        "la source) et ce que le dossier ne permet pas de savoir. Dis explicitement si tu maintiens "
        "le niveau, et pourquoi.\n\n"
        "5. revised_likelihood — \"V1\", \"V2\", \"V3\" ou \"V4\", cohérent avec ce motif.\n\n"
        "6. new_baseline_gap_identified — null dans la plupart des cas. Seulement si un fait du "
        "dossier révèle une faiblesse qui compte dans ton chemin ET qu'aucun écart transmis ne couvre, "
        "même en partie : weakness (formulée sans nom de référentiel ni de norme), risk_categories "
        f"(parmi {', '.join(RISK_CATEGORIES)}), justification, derived_from_fact_fields (les noms exacts "
        "des champs de <contexte_technique> qui l'établissent, « AUD-… » compris).\n"
        "</consignes>"
    )


def coherence_prompt(w4_input: Workshop4Input, scenarios: list[OperationalScenario]) -> str:
    """The single coherence call over the stable set (§18 step 28)."""
    sources = {s.id: s for s in w4_input.sources_risque}
    objectifs = {o.id: o for o in w4_input.objectifs_vises}
    assets = {a.id: a for a in w4_input.biens_essentiels}
    weakness = {g.gap_id: g.weakness for g in w4_input.baseline_gaps}
    block = _json([
        {
            "id": s.id,
            "scenario_strategique": s.scenario_strategique_id,
            "source_de_risque": (
                {"nom": sources[s.source_risque_id].nom, "categorie": sources[s.source_risque_id].categorie_libelle}
                if s.source_risque_id in sources else s.source_risque_id
            ),
            "objectif_vise": objectifs[s.objectif_vise_id].description if s.objectif_vise_id in objectifs else s.objectif_vise_id,
            "biens_essentiels": [assets[a].nom if a in assets else a for a in s.biens_essentiels_ids],
            "gravite": s.gravite.value,
            "vraisemblance_initiale": s.vraisemblance_initiale.value,
            "revised_likelihood": s.revised_likelihood.value if s.revised_likelihood else None,
            "revised_risk_level": s.revised_risk_level.value if s.revised_risk_level else None,
            "likelihood_revision_reason": s.likelihood_revision_reason,
            "attack_path": [
                {"ordre": n, "phase": step.phase, "tactic": step.tactic, "technique_id": step.technique_id,
                 "technique_name": step.technique_name, "description": step.description,
                 "bien_support_id": step.bien_support_id}
                for n, step in enumerate(s.attack_path, 1)
            ],
            "ecarts_exploites": [
                {"gap_id": g.gap_id, "weakness": weakness.get(g.gap_id, ""), "impact_type": g.impact_type.value,
                 "impact_on_scenario": g.impact_on_scenario}
                for g in s.baseline_gaps_considered
                if g.impact_type in {ImpactType.INCREASES_LIKELIHOOD, ImpactType.INCREASES_IMPACT}
            ],
        }
        for s in scenarios
    ])
    return (
        f"<scenarios_operationnels>\n{block}\n</scenarios_operationnels>\n\n"
        "<consignes>\n"
        f"Relis ensemble ces {len(scenarios)} scénarios opérationnels. Pour chaque constat :\n"
        "- type : techniques_contradictoires, doublon ou revision_niveau_risque ;\n"
        "- scenario_ids : les identifiants SO-… concernés, au moins deux ;\n"
        "- explication : les étapes, techniques ou écarts précis en cause, et en quoi ils ne tiennent "
        "pas ensemble ;\n"
        "- scenario_a_reviser et vraisemblance_proposee : pour revision_niveau_risque seulement — "
        "l'identifiant à réviser (parmi scenario_ids) et la valeur V1 à V4 proposée, différente de "
        "l'actuelle ; \"\" pour les deux autres types.\n"
        "Un seul constat par problème. Aucun constat : renvoie une liste vide.\n"
        "</consignes>"
    )
