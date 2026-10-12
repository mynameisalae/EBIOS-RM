"""Instruction text for the Workshop 5 agent (conception §19; méthode atelier 5).

Four calls, one per thing the method asks the agent for: the business wording of each
risk (5-1), the measures of the treatment plan (5-3), the residual likelihood once the
plan is counted (5-4), and the monitoring indicators (5-5). The two decisions the
method reserves for people — the treatment option per risk and the formal acceptance
of the residual risks — are never asked of the model.

Layout as in atelier 4: the long reference material first, the instructions last, one
accepted and one refused example where the model is most tempted to drift.
"""

from __future__ import annotations

import json

from ebios_rm.domain.operational_scenario import OperationalScenario
from ebios_rm.domain.risk_scenario import RiskScenario
from ebios_rm.repositories.attack_repository import AttackMitigation
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import VOIE_LABELS
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
décision d'entreprise, prise par l'auditeur avec la direction. Tu appliques celle qui t'est donnée.
- Tu n'acceptes aucun risque résiduel : l'acceptation est formelle et humaine.
- Tu ne changes ni la gravité, ni la vraisemblance initiale, ni les scénarios : ils viennent des \
ateliers précédents.
- Tu n'inventes rien sur l'organisation. Une mesure qui suppose un moyen, un outil ou une équipe \
que le dossier ne mentionne pas se propose comme une mesure à créer, jamais comme un existant. Un \
champ que le dossier ne permet pas de remplir reste vide : l'auditeur le complétera.

## Les options de traitement (ISO 27005), telles que tu les appliques
- reduction : des mesures cassent les étapes des modes opératoires ; la vraisemblance baisse.
- partage : une partie du risque est transférée (assurance, contrat, tiers) ; l'attaque n'en devient \
pas moins probable.
- evitement : l'activité ou l'exposition est abandonnée ; les étapes qui en dépendaient disparaissent.
- maintien : le risque est gardé en l'état ; il n'appelle aucune mesure.

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

## Échelle de vraisemblance (celle de l'atelier 4)
- V1 Peu vraisemblable — la source de risque a peu de chances d'atteindre son objectif par ce mode opératoire.
- V2 Vraisemblable — elle est susceptible de l'atteindre.
- V3 Très vraisemblable — elle l'atteindra probablement.
- V4 Quasi certain — elle l'atteindra très certainement.
La vraisemblance d'un risque est celle de son mode opératoire le plus vraisemblable : c'est la \
règle qui a choisi le mode retenu à l'atelier 4, et celle qui fixe le risque résiduel ici.

## Format
Uniquement l'objet JSON demandé : aucun texte autour, aucune balise Markdown.
"""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _filled(entry: dict) -> dict:
    """Drop what says nothing: an empty field is noise the model will try to use."""
    return {k: v for k, v in entry.items() if v not in (None, "", [], {})}


def _revision_block(revision_notes: list[str] | None) -> str:
    """The auditor's reasons, injected only on a redo (conception §12.6)."""
    joined = "\n".join(f"- {note}" for note in (revision_notes or []) if note and note.strip())
    if not joined:
        return ""
    return ("\n\n<remarques_de_l_auditeur>\nL'auditeur a refusé ou fait compléter une version "
            "précédente de ce travail. Chaque remarque ci-dessous est à traiter dans cette "
            "proposition ; celles qui portent sur une autre partie de l'atelier ne te concernent "
            "pas ici.\n" + joined + "\n</remarques_de_l_auditeur>")


def _context_block(w5_input: Workshop5Input) -> str:
    expert = [
        {"champ": f.field_name, "question": f.question, "reponse": f.value}
        for f in w5_input.faits_contexte
        if f.field_name.startswith(EXPERT_QUESTION_PREFIX) and f.value not in (None, "")
    ]
    return _json(_filled({
        "organisation_nom": w5_input.organisation_nom,
        "secteur_activite": w5_input.secteur_activite,
        "contexte": {k: v for k, v in w5_input.contexte.items()
                     if not k.startswith(EXPERT_QUESTION_PREFIX)},
        "questions_expertes": expert,
    }))


def _mode_block(mode: OperationalScenario, supports: dict[str, str]) -> dict:
    return _filled({
        "id": mode.id,
        "mode": mode.variante,
        "voie": VOIE_LABELS.get(mode.voie, mode.voie),
        "retenu": mode.retenu,
        "vraisemblance": mode.revised_likelihood.value if mode.revised_likelihood else None,
        "etapes": [
            _filled({"etape": f"{mode.id} étape {n}", "phase": step.phase, "tactic": step.tactic,
                     "technique_id": step.technique_id, "technique": step.technique_name,
                     "action": step.description,
                     "bien_support": (f"{step.bien_support_id} — {supports[step.bien_support_id]}"
                                      if step.bien_support_id in supports else step.bien_support_id),
                     "pourquoi_faisable": step.justification})
            for n, step in enumerate(mode.attack_path, 1)
        ],
        "ecarts_exploites": [
            {"gap_id": g.gap_id, "effet": g.impact_on_scenario}
            for g in mode.baseline_gaps_considered
            if g.impact_type.value.startswith("increases")
        ],
    })


def _risques_block(
    w5_input: Workshop5Input, risques: list[RiskScenario], *,
    with_modes: bool, with_mesures: bool = False,
) -> str:
    """The risks as the model needs them: who, what for, by which route, to what effect.

    Without modes (formulation) the retained route is given as one line; with modes
    (plan, residual) every step of every mode is there, since that is what a measure
    breaks. Empty fields are dropped — a decision not yet taken is not « null ».
    """
    sources = {s.id: s.nom for s in w5_input.sources_risque}
    objectifs = {o.id: o.description for o in w5_input.objectifs_vises}
    assets = {a.id: a.nom for a in w5_input.biens_essentiels}
    supports = {s.id: s.nom for s in w5_input.biens_supports}
    events = {e.id: e.description for e in w5_input.evenements_redoutes}
    modes = {m.id: m for m in w5_input.modes_operatoires}
    scenarios = {s.id: s for s in w5_input.scenarios_strategiques}

    payload = []
    for risque in risques:
        scenario = scenarios.get(risque.scenario_strategique_id)
        retenu = modes.get(risque.mode_retenu_id)
        entry = {
            "risque_id": risque.id,
            "libelle": risque.libelle,
            "source_de_risque": sources.get(risque.source_risque_id, risque.source_risque_id),
            "objectif_vise": objectifs.get(risque.objectif_vise_id, risque.objectif_vise_id),
            "scenario_strategique": scenario.resume if scenario else risque.scenario_strategique_id,
            "parties_prenantes": scenario.parties_prenantes if scenario else [],
            "biens_essentiels": [assets.get(a, a) for a in risque.biens_essentiels_ids],
            "evenements_redoutes": [events[e] for e in risque.evenements_redoutes_ids if e in events],
            "gravite": risque.gravite.value,
            "vraisemblance": risque.vraisemblance.value,
            "niveau_risque": risque.niveau_risque.value if risque.niveau_risque else None,
            "acceptabilite": risque.acceptabilite.value if risque.acceptabilite else None,
            "option_de_traitement_decidee": (risque.option_traitement.value
                                             if risque.option_traitement else None),
            "justification_de_l_auditeur": risque.justification_traitement,
        }
        if with_modes:
            entry["mode_retenu"] = _mode_block(retenu, supports) if retenu else None
            entry["modes_alternatifs"] = [_mode_block(modes[m], supports)
                                          for m in risque.modes_alternatifs_ids if m in modes]
        elif retenu is not None:
            entry["chemin_retenu"] = f"{retenu.variante} ({VOIE_LABELS.get(retenu.voie, retenu.voie)})"
        if with_mesures:
            entry["mesures_retenues"] = risque.mesures_ids
        payload.append(_filled(entry))
    return _json(payload)


def _gaps_block(w5_input: Workshop5Input) -> str:
    return _json([
        _filled({"gap_id": g.gap_id, "weakness": g.weakness,
                 "referentiels": [f"{c.framework} {c.control_id}" for c in g.controls],
                 "preuve": g.evidence_quote})
        for g in w5_input.baseline_gaps
    ])


def _mitigations_block(mitigations: dict[str, list[AttackMitigation]]) -> str:
    return _json({
        technique_id: [{"mitigation_id": m.mitigation_id, "nom": m.name} for m in found]
        for technique_id, found in mitigations.items() if found
    })


def _thematiques_block() -> str:
    return "\n".join(f"  {axe} : " + " ; ".join(themes) for axe, themes in THEMATIQUES.items())


# --- Activité 5-1 -----------------------------------------------------------

def formulations_prompt(
    w5_input: Workshop5Input, risques: list[RiskScenario], revision_notes: list[str] | None = None,
) -> str:
    """Activité 5-1 — write each risk the way a decision-maker reads it."""
    return (
        f"<risques>\n{_risques_block(w5_input, risques, with_modes=False)}\n</risques>\n\n"
        "<consignes>\n"
        "Écris chaque risque en une phrase qu'un dirigeant lit sans lexique, dans cet ordre : QUI "
        "agit (la source de risque), ce qu'il cherche (l'objectif visé), PAR QUEL CHEMIN en une "
        "incise (le scénario stratégique et le chemin retenu, dans les mots du métier), et la "
        "CONSÉQUENCE pour l'organisation (l'événement redouté, sur le bien essentiel).\n\n"
        "Règles :\n"
        "- fidèle au dossier : la conséquence est celle des événements redoutés listés, jamais une "
        "autre, et aucun fait qui n'est pas dans le risque ;\n"
        "- deux risques ne se lisent jamais pareil : quand la source et l'objectif sont les mêmes, "
        "c'est le chemin qui les distingue — écris-le ;\n"
        "- trente-cinq mots au plus, aucun identifiant (SR-…, BS-…, T1…, V3), ni gravité ni "
        "vraisemblance : elles figurent déjà à côté ;\n"
        "- risque_id repris tel quel.\n\n"
        "Attendu : « Un concurrent obtient le fichier des patients en passant par le prestataire "
        "d'infogérance qui administre le système hospitalier, ce qui expose la clinique à une "
        "violation de données de santé. »\n"
        "Refusé : « Exfiltration via T1041 sur le bien support BS-3 » — des identifiants techniques "
        "à la place d'une phrase.\n"
        "</consignes>"
        + _revision_block(revision_notes)
    )


# --- Activité 5-3 -----------------------------------------------------------

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
        "Propose le plan de traitement : le plus petit ensemble de mesures qui fait baisser les "
        "risques ci-dessus et remet le socle de sécurité en conformité.\n\n"
        "Procède dans cet ordre :\n"
        "1. Chaque risque, selon l'option décidée par l'auditeur :\n"
        "   - reduction : dans le mode retenu puis dans chaque mode alternatif, repère l'étape sans "
        "laquelle le mode échoue — souvent l'accès initial, ou l'étape qui exploite un écart du "
        "socle — et propose la mesure qui la casse. Un mode alternatif laissé ouvert maintient le "
        "risque : il lui faut sa mesure, ou une mesure commune ;\n"
        "   - partage : la mesure organise le transfert (clause contractuelle, assurance, "
        "prestataire), axe gouvernance, thématique « maîtrise de l'écosystème », "
        "effet_vraisemblance 0 ;\n"
        "   - evitement : la mesure décrit le renoncement (service retiré, flux supprimé, activité "
        "abandonnée) et les étapes qu'il fait disparaître.\n"
        "2. Chaque écart de <ecarts_du_socle> appelle une mesure qui le comble (origine "
        "atelier1_socle), même s'il ne sert aucun risque à traiter : le plan est aussi l'endroit "
        "où le socle est remis en conformité. Nomme le référentiel dans la description.\n"
        "3. Pour chaque partie prenante par laquelle passe un scénario, vois si une mesure "
        "d'écosystème (clause de sécurité, audit du prestataire, accès restreint et tracé) fait "
        "baisser la menace qu'elle porte (origine atelier3_ecosysteme).\n"
        "4. Mutualise : une mesure qui casse la même étape dans trois modes vaut mieux que trois "
        "mesures. Ne reprends pas une mesure de <mesures_deja_retenues>.\n\n"
        "Calibre sur l'organisation : maturite_securite, moyens_traitement, contraintes_calendrier "
        "et ce que le dossier décrit comme déjà en place. Une mesure au-delà de ses moyens n'est "
        "pas mise en œuvre : propose ce qu'elle peut porter, et dis dans freins ce qui manque.\n"
        "Échéance selon l'acceptabilité du risque servi : Inacceptable, court terme (six mois au "
        "plus) — la méthode rend ces mesures obligatoires ; Tolérable sous contrôle, moyen terme "
        "(douze mois) ; le socle seul, selon la charge.\n\n"
        "Pour chaque mesure :\n"
        "  - axe : gouvernance, protection, defense ou resilience ;\n"
        "  - thematique : l'une de celles listées pour cet axe ;\n"
        "  - libelle : l'action en une ligne, concrète et vérifiable ;\n"
        "  - description : ce qu'elle change, dans les termes du dossier ;\n"
        "  - risques_ids : les risques qu'elle réduit (identifiants R…) ;\n"
        "  - modes_ids et etapes_visees : les modes opératoires et les étapes qu'elle casse "
        "(« SO-02 étape 3 ») ;\n"
        "  - gap_ids : les écarts du socle qu'elle comble ;\n"
        "  - mitigation_ids_attck : uniquement des identifiants de <mesures_attck_disponibles> ;\n"
        "  - origine : atelier1_socle, atelier3_ecosysteme ou atelier4_vulnerabilite ;\n"
        "  - freins : ce qui rendra la mise en œuvre difficile ici (validation, contrat, budget) ;\n"
        "  - responsable : le rôle qui la portera, pris dans responsables_mesures du contexte ; "
        "vide si le contexte ne le dit pas ;\n"
        f"  - cout_complexite : {', '.join(COUTS)} ; charge_estimee en j/h ; echeance en mois ;\n"
        "  - justification : pourquoi cette mesure, sur cette étape, dans ce dossier ;\n"
        "  - effet_vraisemblance : 2 seulement si elle casse l'étape décisive de TOUS les modes du "
        "risque ; 1 si elle casse l'étape décisive du mode retenu ; 0 si elle ne casse aucune étape "
        "(gouvernance, partage, résilience, suivi). Une mesure de détection ne revendique une "
        "baisse que si la réponse arrive avant l'étape qui produit l'événement redouté.\n\n"
        "Attendu : libelle « Imposer un second facteur d'authentification sur le VPN et les "
        "comptes d'administration », etapes_visees [« SO-01 étape 1 », « SO-02 étape 1 »], "
        "mitigation_ids_attck [« M1032 »], justification « les deux modes entrent avec un compte "
        "valide volé : sans second facteur l'étape réussit, avec lui elle échoue », "
        "effet_vraisemblance 2.\n"
        "Refusé : « Sensibiliser les utilisateurs à la cybersécurité » sans étape, écart ni risque "
        "— un vœu, pas une mesure.\n"
        "</consignes>"
        + _revision_block(revision_notes)
    )


# --- Activité 5-4 -----------------------------------------------------------

def residuel_prompt(
    w5_input: Workshop5Input, output: Workshop5Output, risques: list[RiskScenario]
) -> str:
    """Activité 5-4 — the likelihood that remains once the plan is in place."""
    plan = _json([
        _filled({"id": m.id, "libelle": m.libelle, "risques": m.risques_ids, "modes": m.modes_ids,
                 "etapes_visees": m.etapes_visees, "effet_vraisemblance": m.effet_vraisemblance})
        for m in output.mesures
    ])
    return (
        f"<risques>\n{_risques_block(w5_input, risques, with_modes=True, with_mesures=True)}\n"
        "</risques>\n\n"
        f"<plan_de_traitement>\n{plan}\n</plan_de_traitement>\n\n"
        "<consignes>\n"
        "Évalue chaque risque tel qu'il sera une fois TOUTES ses mesures_retenues en place, quelle "
        "que soit leur échéance.\n\n"
        "Procède ainsi :\n"
        "1. Pour chaque mode — le retenu et les alternatifs — reprends ses étapes : une étape visée "
        "par une mesure retenue sur ce risque est cassée si la mesure l'empêche réellement pour les "
        "moyens de cette source ; sinon elle reste faisable.\n"
        "2. Donne à chaque mode sa vraisemblance après le plan : un mode dont une étape "
        "indispensable est cassée baisse, un mode intact garde la sienne.\n"
        "3. La vraisemblance résiduelle du risque est celle de son mode le plus vraisemblable "
        "après le plan. Fermer le mode retenu en laissant un alternatif ouvert ramène le risque à "
        "la vraisemblance de cet alternatif, pas plus bas.\n\n"
        "Le code vérifie : jamais au-dessus de la vraisemblance initiale ; aucune baisse sans "
        "mesure retenue ; pas plus bas que ce que revendiquent les effet_vraisemblance de ces "
        "mesures. La gravité ne bouge pas.\n\n"
        "Pour chaque risque :\n"
        "  - risque_id : repris tel quel ;\n"
        "  - motif : mode par mode, quelle mesure casse quelle étape et ce qui reste ouvert, en deux "
        "phrases au plus ;\n"
        "  - vraisemblance_residuelle : \"V1\", \"V2\", \"V3\" ou \"V4\", écrite après le motif.\n"
        "</consignes>"
    )


# --- Activité 5-5 -----------------------------------------------------------

def indicateurs_prompt(
    w5_input: Workshop5Input, output: Workshop5Output, revision_notes: list[str] | None = None,
) -> str:
    """Activité 5-5 — the indicators that will say whether the plan works."""
    plan = _json([
        _filled({"id": m.id, "axe": m.axe.value, "libelle": m.libelle, "risques": m.risques_ids,
                 "echeance": m.echeance, "priorite": m.priorite.value if m.priorite else None})
        for m in output.mesures
    ])
    cadre = output.cadre_suivi
    instance = _json(_filled({"comite": cadre.comite, "cycles": cadre.cycles}) if cadre else {})
    return (
        f"<plan_de_traitement>\n{plan}\n</plan_de_traitement>\n\n"
        f"<instance_de_suivi>\n{instance}\n</instance_de_suivi>\n\n"
        f"<contexte_organisation>\n{_context_block(w5_input)}\n</contexte_organisation>\n\n"
        "<consignes>\n"
        "Propose les indicateurs du cadre de suivi : de quoi dire, à chaque réunion de l'instance, si "
        "le plan avance et si les risques baissent comme prévu.\n\n"
        "Trois familles, dans cet ordre :\n"
        "1. l'avancement du plan : au moins un indicateur d'ensemble (taux de mesures terminées à "
        "leur échéance, charge ou coût engagé) ;\n"
        "2. l'efficacité des mesures P1 : pour chacune, un indicateur qui dit si elle produit son "
        "effet (part des comptes sous second facteur, délai de correction des vulnérabilités "
        "critiques…) ;\n"
        "3. le maintien en condition de sécurité : ce qui dérive avec le temps (comptes inactifs, "
        "restaurations testées, correctifs en retard).\n\n"
        "Chaque indicateur se mesure — un coût, une durée, un nombre ou un taux — avec une cible "
        "chiffrée. Il se relève au moins aussi souvent que l'instance se réunit. Il est relevable "
        "avec les moyens que le dossier décrit : un indicateur qui suppose un outil absent le dit "
        "dans son libellé. Entre trois et huit indicateurs : une instance n'en lit pas plus.\n\n"
        "Pour chaque indicateur :\n"
        "  - libelle : ce qui est mesuré, en une ligne ;\n"
        "  - type_valeur : cout, duree, nombre ou taux ;\n"
        "  - cible : la valeur visée, chiffrée (« 100 % des postes », « moins de 30 jours ») ;\n"
        "  - frequence : à quelle fréquence il est relevé ;\n"
        "  - mesures_ids : les mesures du plan qu'il surveille (vide pour un indicateur d'ensemble).\n\n"
        "Attendu : libelle « Part des comptes d'accès distant protégés par un second facteur », "
        "type_valeur taux, cible « 100 % », frequence « mensuelle », mesures_ids [« M-01 »].\n"
        "Refusé : « Amélioration de la posture de sécurité » — rien ne s'y mesure.\n"
        "</consignes>"
        + _revision_block(revision_notes)
    )
