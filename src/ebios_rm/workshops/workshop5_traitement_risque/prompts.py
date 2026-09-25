"""Instruction text for the Workshop 5 agent (conception §19; méthode atelier 5).

Four calls, one per thing the method asks the agent for: the business wording of each
risk (5-1), the measures of the treatment plan (5-3), the residual likelihood once the
plan is counted (5-4), and the monitoring indicators (5-5). The two decisions the
method reserves for people — the treatment option per risk and the formal acceptance
of the residual risks — are never asked of the model.

Layout as in atelier 4: the long reference material first, the instructions last.
"""

from __future__ import annotations

import json

from ebios_rm.domain.operational_scenario import OperationalScenario
from ebios_rm.domain.risk_scenario import RiskScenario
from ebios_rm.repositories.attack_repository import AttackMitigation
from ebios_rm.workshops.workshop5_traitement_risque.models import (
    COUTS,
    EXPERT_QUESTION_PREFIX,
    THEMATIQUES,
    Workshop5Input,
    Workshop5Output,
)

SYSTEM_INSTRUCTIONS = """\
Tu es analyste EBIOS Risk Manager pour l'atelier 5 (traitement du risque). L'étude est faite : les \
risques sont chiffrés, la gravité vient de l'atelier 1, la vraisemblance de l'atelier 4. Ton travail \
est de préparer de quoi décider et de quoi agir. Tu proposes ; la direction et l'auditeur décident.

## Ce que tu ne fais jamais
- Tu ne décides pas du traitement d'un risque (réduire, maintenir, partager, éviter) : c'est une \
décision d'entreprise, prise par l'auditeur avec la direction.
- Tu n'acceptes aucun risque résiduel : l'acceptation est formelle et humaine.
- Tu ne changes ni la gravité, ni la vraisemblance initiale, ni les scénarios : ils viennent des \
ateliers précédents.
- Tu n'inventes rien sur l'organisation. Une mesure qui suppose un moyen, un outil ou une équipe \
que le dossier ne mentionne pas se propose comme une mesure à créer, jamais comme un existant.

## Les mesures de sécurité
- Une mesure agit sur la VRAISEMBLANCE, pas sur la gravité : si l'événement redouté se produit, il \
coûte autant qu'avant.
- Chaque mesure dit ce qu'elle empêche : l'étape d'un mode opératoire qu'elle casse, l'écart du \
socle qu'elle comble, ou le risque qu'elle réduit. Une mesure qui ne se rattache à rien est écartée.
- Une mesure peut servir plusieurs risques : c'est même souhaitable, le plan se mutualise.
- Le plan est rangé en quatre axes : gouvernance (et anticipation), protection, défense, résilience. \
Tu ranges chaque mesure dans un axe et sous l'une des thématiques fournies.
- Les identifiants de mesures MITRE ATT&CK (M####) ne peuvent venir que de la liste fournie pour les \
techniques réellement citées par les modes opératoires. Un identifiant hors de cette liste est \
supprimé. Une mesure sans identifiant ATT&CK reste valable : beaucoup de mesures sont \
organisationnelles.
- Tu ne proposes pas ce que le dossier décrit déjà comme en place ; tu proposes de le renforcer, en \
disant ce qui manque.

## Le vocabulaire du plan
- Coût / complexité : « + » faible, « ++ » moyen, « +++ » élevé.
- Charge estimée : en jours-homme, « 10 j/h ».
- Échéance : en mois, « 6 mois ».
- effet_vraisemblance : de combien de niveaux la mesure fait baisser la vraisemblance du risque \
(0, 1 ou 2), justifié. Deux niveaux est une revendication forte : réserve-la aux mesures qui cassent \
l'étape décisive du mode retenu.

## L'échelle de vraisemblance (rappel, atelier 4)
V1 peu vraisemblable, V2 vraisemblable, V3 très vraisemblable, V4 quasi certain ou déjà produit.

## Format
Uniquement l'objet JSON demandé : aucun texte autour, aucune balise Markdown.
"""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _context_block(w5_input: Workshop5Input) -> str:
    expert = [
        {"champ": f.field_name, "question": f.question, "reponse": f.value}
        for f in w5_input.faits_contexte
        if f.field_name.startswith(EXPERT_QUESTION_PREFIX) and f.value not in (None, "")
    ]
    return _json({
        "organisation_nom": w5_input.organisation_nom,
        "secteur_activite": w5_input.secteur_activite,
        "contexte": {k: v for k, v in w5_input.contexte.items()
                     if not k.startswith(EXPERT_QUESTION_PREFIX)},
        "questions_expertes": expert,
    })


def _mode_block(mode: OperationalScenario) -> dict:
    return {
        "id": mode.id,
        "mode": mode.variante,
        "voie": mode.voie,
        "retenu": mode.retenu,
        "vraisemblance": mode.revised_likelihood.value if mode.revised_likelihood else None,
        "etapes": [
            {"etape": f"{mode.id} étape {n}", "phase": step.phase, "tactic": step.tactic,
             "technique_id": step.technique_id, "technique": step.technique_name,
             "action": step.description, "bien_support": step.bien_support_id,
             "pourquoi_faisable": step.justification}
            for n, step in enumerate(mode.attack_path, 1)
        ],
        "ecarts_exploites": [
            {"gap_id": g.gap_id, "impact_type": g.impact_type.value, "effet": g.impact_on_scenario}
            for g in mode.baseline_gaps_considered
            if g.impact_type.value.startswith("increases")
        ],
    }


def _risques_block(w5_input: Workshop5Input, risques: list[RiskScenario], *, with_modes: bool) -> str:
    sources = {s.id: s for s in w5_input.sources_risque}
    objectifs = {o.id: o for o in w5_input.objectifs_vises}
    assets = {a.id: a for a in w5_input.biens_essentiels}
    events = {e.id: e for e in w5_input.evenements_redoutes}
    modes = {m.id: m for m in w5_input.modes_operatoires}
    scenarios = {s.id: s for s in w5_input.scenarios_strategiques}

    payload = []
    for risque in risques:
        scenario = scenarios.get(risque.scenario_strategique_id)
        entry = {
            "risque_id": risque.id,
            "libelle": risque.libelle,
            "source_de_risque": (sources[risque.source_risque_id].nom
                                 if risque.source_risque_id in sources else risque.source_risque_id),
            "objectif_vise": (objectifs[risque.objectif_vise_id].description
                              if risque.objectif_vise_id in objectifs else risque.objectif_vise_id),
            "scenario_strategique": scenario.resume if scenario else risque.scenario_strategique_id,
            "parties_prenantes": scenario.parties_prenantes if scenario else [],
            "biens_essentiels": [assets[a].nom if a in assets else a
                                 for a in risque.biens_essentiels_ids],
            "evenements_redoutes": [events[e].description for e in risque.evenements_redoutes_ids
                                    if e in events],
            "gravite": risque.gravite.value,
            "vraisemblance": risque.vraisemblance.value,
            "niveau_risque": risque.niveau_risque.value if risque.niveau_risque else None,
            "acceptabilite": risque.acceptabilite.value if risque.acceptabilite else None,
            "option_de_traitement_decidee": (risque.option_traitement.value
                                             if risque.option_traitement else None),
            "justification_de_l_auditeur": risque.justification_traitement,
        }
        if with_modes:
            entry["mode_retenu"] = (_mode_block(modes[risque.mode_retenu_id])
                                    if risque.mode_retenu_id in modes else None)
            entry["modes_alternatifs"] = [_mode_block(modes[m]) for m in risque.modes_alternatifs_ids
                                          if m in modes]
        payload.append(entry)
    return _json(payload)


def _gaps_block(w5_input: Workshop5Input) -> str:
    return _json([
        {"gap_id": g.gap_id, "weakness": g.weakness,
         "referentiels": [f"{c.framework}/{c.control_id}" for c in g.controls],
         "risk_categories": g.risk_categories}
        for g in w5_input.baseline_gaps
    ])


def _mitigations_block(mitigations: dict[str, list[AttackMitigation]]) -> str:
    return _json({
        technique_id: [{"mitigation_id": m.mitigation_id, "nom": m.name} for m in found]
        for technique_id, found in mitigations.items() if found
    })


def _thematiques_block() -> str:
    return "\n".join(f"  {axe} : " + " ; ".join(themes) for axe, themes in THEMATIQUES.items())


def formulations_prompt(w5_input: Workshop5Input, risques: list[RiskScenario]) -> str:
    """Activité 5-1 — write each risk the way a decision-maker reads it."""
    return (
        f"<risques>\n{_risques_block(w5_input, risques, with_modes=False)}\n</risques>\n\n"
        "<consignes>\n"
        "Formule chaque risque en une phrase, dans les termes du métier, telle qu'un dirigeant "
        "puisse la lire sans lexique : QUI agit, ce qu'il obtient ou provoque, par QUEL chemin en "
        "une incise, et la CONSÉQUENCE pour l'organisation.\n"
        "Attendu : « Un concurrent obtient la liste confidentielle en visant les échanges avec le "
        "ministère qui la fournit, ce qui expose l'organisation à la perte de son agrément. »\n"
        "Refusé : « Exfiltration via T1041 sur le bien support BS-3 » — des identifiants techniques "
        "à la place d'une phrase.\n"
        "Reprends le risque_id tel quel. Ni gravité, ni vraisemblance, ni mesure dans la phrase : "
        "elles figurent déjà à côté.\n"
        "</consignes>"
    )


def _revision_block(revision_notes: list[str] | None) -> str:
    """The auditor's rejection reasons, injected only on a redo (conception §12.6)."""
    joined = "\n".join(f"- {note}" for note in (revision_notes or []) if note and note.strip())
    if not joined:
        return ""
    return ("\n\nREMARQUES DE L'AUDITEUR SUR LE OU LES PLANS PRÉCÉDENTS (à corriger "
            "impérativement dans cette proposition) :\n" + joined + "\n")


def mesures_prompt(
    w5_input: Workshop5Input,
    output: Workshop5Output,
    risques: list[RiskScenario],
    mitigations: dict[str, list[AttackMitigation]],
    revision_notes: list[str] | None = None,
) -> str:
    """Activité 5-3 — the measures of the plan, for the risks the auditor decided to treat."""
    existing = _json([{"id": m.id, "axe": m.axe.value, "libelle": m.libelle} for m in output.mesures])
    return (
        f"<contexte_organisation>\n{_context_block(w5_input)}\n</contexte_organisation>\n\n"
        f"<risques_a_traiter>\n{_risques_block(w5_input, risques, with_modes=True)}\n"
        "</risques_a_traiter>\n\n"
        f"<ecarts_du_socle>\n{_gaps_block(w5_input)}\n</ecarts_du_socle>\n\n"
        f"<mesures_attck_disponibles>\n{_mitigations_block(mitigations)}\n</mesures_attck_disponibles>\n\n"
        f"<mesures_deja_retenues>\n{existing}\n</mesures_deja_retenues>\n\n"
        "<thematiques_du_plan>\n" + _thematiques_block() + "\n</thematiques_du_plan>\n\n"
        "<consignes>\n"
        "Propose les mesures de sécurité du plan de traitement pour les risques ci-dessus. Pars des "
        "étapes des modes opératoires : la mesure la plus utile est celle qui casse l'étape décisive "
        "du mode retenu. Traite aussi les modes alternatifs — un plan qui ferme la porte la plus "
        "facile et laisse les autres ouvertes ne réduit rien.\n\n"
        "Pour chaque mesure :\n"
        "  - axe : gouvernance, protection, defense ou resilience ;\n"
        "  - thematique : l'une de celles listées pour cet axe ;\n"
        "  - libelle : la mesure en une ligne, action concrète et vérifiable ;\n"
        "  - description : ce qu'elle change, dans les termes du dossier ;\n"
        "  - risques_ids : les risques qu'elle réduit (identifiants R…) ;\n"
        "  - modes_ids et etapes_visees : les modes opératoires et les étapes qu'elle casse "
        "(« SO-02 étape 3 ») ;\n"
        "  - gap_ids : les écarts du socle qu'elle comble, s'il y en a ;\n"
        "  - mitigation_ids_attck : uniquement des identifiants de <mesures_attck_disponibles> ;\n"
        "  - origine : atelier1_socle, atelier3_ecosysteme ou atelier4_vulnerabilite ;\n"
        "  - freins : ce qui rendra la mise en œuvre difficile ici (validation, contrat, budget) ;\n"
        f"  - cout_complexite : {', '.join(COUTS)} ; charge_estimee en j/h ; echeance en mois ;\n"
        "  - justification : pourquoi cette mesure, sur cette étape, dans ce dossier ;\n"
        "  - effet_vraisemblance : 0, 1 ou 2 niveaux de baisse revendiqués.\n\n"
        "Mutualise : une mesure qui sert trois risques vaut mieux que trois mesures. N'énumère pas "
        "un catalogue de bonnes pratiques — chaque mesure se rattache à une étape, un écart ou un "
        "risque de cette étude. Ne reprends pas une mesure déjà retenue.\n"
        "</consignes>"
        + _revision_block(revision_notes)
    )


def residuel_prompt(
    w5_input: Workshop5Input, output: Workshop5Output, risques: list[RiskScenario]
) -> str:
    """Activité 5-4 — the likelihood that remains once the plan is in place."""
    plan = _json([
        {"id": m.id, "axe": m.axe.value, "libelle": m.libelle, "risques": m.risques_ids,
         "etapes_visees": m.etapes_visees, "gap_ids": m.gap_ids,
         "effet_vraisemblance": m.effet_vraisemblance, "echeance": m.echeance}
        for m in output.mesures
    ])
    return (
        f"<risques>\n{_risques_block(w5_input, risques, with_modes=True)}\n</risques>\n\n"
        f"<plan_de_traitement>\n{plan}\n</plan_de_traitement>\n\n"
        "<consignes>\n"
        "Pour chaque risque, évalue la vraisemblance qui subsiste une fois les mesures du plan "
        "réellement en place.\n"
        "  - risque_id : repris tel quel ;\n"
        "  - motif : quelles mesures cassent quelle étape, et ce qui reste ouvert — notamment les "
        "modes alternatifs qu'aucune mesure ne touche ;\n"
        "  - vraisemblance_residuelle : \"V1\", \"V2\", \"V3\" ou \"V4\".\n\n"
        "La gravité ne bouge pas : l'événement redouté coûte autant qu'avant. La vraisemblance ne "
        "peut que baisser, et seulement si une mesure casse une étape dont le mode a besoin. Un "
        "risque dont le mode retenu est fermé mais dont un mode alternatif reste ouvert ne descend "
        "pas au niveau le plus bas : dis-le.\n"
        "</consignes>"
    )


def indicateurs_prompt(w5_input: Workshop5Input, output: Workshop5Output) -> str:
    """Activité 5-5 — the indicators that will say whether the plan works."""
    plan = _json([
        {"id": m.id, "axe": m.axe.value, "libelle": m.libelle, "echeance": m.echeance,
         "priorite": m.priorite.value if m.priorite else None}
        for m in output.mesures
    ])
    return (
        f"<plan_de_traitement>\n{plan}\n</plan_de_traitement>\n\n"
        f"<contexte_organisation>\n{_context_block(w5_input)}\n</contexte_organisation>\n\n"
        "<consignes>\n"
        "Propose les indicateurs qui permettront de suivre ce plan et le maintien en condition de "
        "sécurité. Chaque indicateur se mesure : un coût, une durée, un nombre ou un taux.\n"
        "  - libelle : ce qui est mesuré, en une ligne ;\n"
        "  - type_valeur : cout, duree, nombre ou taux ;\n"
        "  - cible : la valeur visée, chiffrée (« 100 % des postes », « moins de 30 jours ») ;\n"
        "  - frequence : à quelle fréquence il est relevé ;\n"
        "  - mesures_ids : les mesures du plan qu'il surveille.\n\n"
        "Reste proportionné à cette organisation : peu d'indicateurs, relevables avec les moyens que "
        "le dossier décrit, et chacun rattaché à au moins une mesure du plan.\n"
        "</consignes>"
    )
