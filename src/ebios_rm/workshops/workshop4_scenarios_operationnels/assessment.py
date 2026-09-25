"""Deterministic atelier 4 methodology (conception §18).

Pure functions, no LLM and no I/O. Everything that decides rather than proposes is
here: validating the atelier 3 output, checking each sub-agent's answer against the
ATT&CK base and the baseline gaps it was given (§18 steps 23-24), reading the risk
level off the gravité and the likelihood, applying the auditor's review and the
coherence findings, and the quality checker.

The sub-agents write the attack path and argue the likelihood; they cannot talk
their way past this module, and nothing they got wrong is repaired in silence —
it becomes an anomaly in front of the auditor.
"""

from __future__ import annotations

import re
from typing import Iterable

from ebios_rm.domain.enums import Gravite, ImpactType, NiveauRisque, VraisemblanceInitiale
from ebios_rm.domain.operational_scenario import (
    STATUT_A_ANALYSER,
    STATUT_ANALYSE,
    STATUT_CONFIRME,
    STATUTS_EN_ATTENTE,
    Anomaly,
    AttackStep,
    GapConsideration,
    NewBaselineGap,
    OperationalScenario,
)
from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.repositories.attack_repository import AttackCatalogue
from ebios_rm.workshops.workshop1_cadrage.human_interface import is_meaningful
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGapForW4, Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.assessment import normalise
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Output
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import (
    ACTION_RUN,
    ACTION_RUN_ANYWAY,
    Workshop3Output,
)
from ebios_rm.workshops.workshop4_scenarios_operationnels.models import (
    COHERENCE_APPLIQUEE,
    CONSTAT_LABELS,
    CONSTAT_REVISION,
    REASON_ANALYSE_REMPLACEE,
    REASON_CONSTAT_INVALIDE,
    REASON_ENTREE_ECART_INCONNU,
    REASON_MODE_DOUBLON,
    REASON_MODE_SANS_ANCRAGE,
    REASON_MODE_VOIE_INCONNUE,
    REASON_NOUVEL_ECART_SANS_ANCRAGE,
    RISK_CATEGORIES,
    VOIE_CONTEXT_FIELDS,
    VOIE_LABELS,
    VOIES,
    STATUT_AVERTISSEMENT,
    STATUT_ERREUR,
    STATUT_OK,
    AtelierAlert,
    CoherenceFinding,
    CoherenceFindingProposal,
    ElementEcarte,
    GapConsiderationProposal,
    ModeCandidateProposal,
    QualityCheck,
    QualityReport,
    ScenarioAnalysisProposal,
    Workshop4Input,
    Workshop4Output,
)

# The per-scenario loop cap (§18 step 27, « Loop max_iterations=3 »): past it, sending
# a scenario back takes a typed confirmation, like the rollback cap of §12.6.
MAX_ITERATIONS = 3

# Modes opératoires developed per strategic scenario before the auditor has to insist.
# Not a target — the enumeration decides how many the dossier holds — but a runaway
# guard: a model that keeps finding « one more way in » cannot order forty analyses
# on its own. Passing it takes a typed confirmation, like the rollback cap of §12.6.
MAX_MODES_PER_SCENARIO = 6

# --- Phases: how EBIOS RM reads an ATT&CK path ------------------------------

PHASE_CONNAITRE = "Connaître"
PHASE_RENTRER = "Rentrer"
PHASE_TROUVER = "Trouver"
PHASE_EXPLOITER = "Exploiter"

_PHASES = {
    "reconnaissance": PHASE_CONNAITRE,
    "resource-development": PHASE_CONNAITRE,
    "initial-access": PHASE_RENTRER,
    "execution": PHASE_TROUVER,
    "persistence": PHASE_TROUVER,
    "privilege-escalation": PHASE_TROUVER,
    "stealth": PHASE_TROUVER,
    "defense-impairment": PHASE_TROUVER,
    "credential-access": PHASE_TROUVER,
    "discovery": PHASE_TROUVER,
    "lateral-movement": PHASE_TROUVER,
    "command-and-control": PHASE_TROUVER,
    "collection": PHASE_EXPLOITER,
    "exfiltration": PHASE_EXPLOITER,
    "impact": PHASE_EXPLOITER,
}


def phase_of(tactic: str) -> str:
    return _PHASES.get(tactic, "")


def normalise_tactic(raw: str) -> str:
    """« Initial Access », « initial_access » and « initial-access » are one tactic."""
    return re.sub(r"[\s_]+", "-", (raw or "").strip().casefold())


# covers_risk_category is written in the controls' own vocabulary. Most of it is an
# ATT&CK tactic with underscores; two entries are not, and ATT&CK v18 split
# defense-evasion in two.
_CATEGORY_TACTICS = {
    "defense_evasion": ("stealth", "defense-impairment"),
    "data_destruction": ("impact",),
}


def tactics_of_category(category: str) -> tuple[str, ...]:
    return _CATEGORY_TACTICS.get(category, (category.replace("_", "-"),))


def pertinent_gap_ids(gaps: list[BaselineGapForW4], tactics: Iterable[str]) -> list[str]:
    """The gaps whose risk categories meet a tactic of the path — the ones §18 step 24 requires."""
    present = set(tactics)
    return [
        g.gap_id for g in gaps
        if any(t in present for c in g.risk_categories for t in tactics_of_category(c))
    ]


# --- The two checks of the fiche de test (§18) ------------------------------

def unknown_technique_ids(cited_ids: Iterable[str], returned_ids: Iterable[str]) -> list[str]:
    """Cited technique ids the ATT&CK base never returned, in citation order (§18 step 23)."""
    known = set(returned_ids)
    return [i for i in cited_ids if i not in known]


def is_weak_entry(entry: GapConsiderationProposal | GapConsideration) -> bool:
    """A gap entry that says nothing — whatever its impact_type, no_impact included (§18 step 24)."""
    return not is_meaningful(entry.impact_on_scenario or "")


# --- Value readers: lenient on form, strict on meaning ----------------------

_NO_TECHNIQUE = {"", "NULL", "NONE", "N/A", "NA", "AUCUN", "AUCUNE", "-"}
_TECHNIQUE_ID = re.compile(r"T\d{4}(?:\.\d{3})?")
_LIKELIHOOD = re.compile(r"\bV\s*([1-4])\b")


def read_technique_id(raw: str | None) -> tuple[str | None, bool]:
    """(the id, readable). « T1566.001 Spearphishing Attachment » reads as T1566.001;
    two ids in one field, or text with none, is unreadable rather than guessed."""
    text = (raw or "").strip().upper()
    if text in _NO_TECHNIQUE:
        return None, True
    found = set(_TECHNIQUE_ID.findall(text))
    if len(found) == 1:
        return found.pop(), True
    return None, False


def read_likelihood(raw: str | None) -> VraisemblanceInitiale | None:
    """« V3 » and « V3 (très vraisemblable) » read as V3; « V2-V3 » is not a value."""
    found = set(_LIKELIHOOD.findall((raw or "").upper()))
    return VraisemblanceInitiale(f"V{found.pop()}") if len(found) == 1 else None


def read_impact_type(raw: str | None) -> ImpactType | None:
    text = normalise_tactic(raw).replace("-", "_")
    return next((t for t in ImpactType if t.value == text), None)


def _rank(value: VraisemblanceInitiale) -> int:
    return int(value.value[1])


_GRAVITE_RANK = {Gravite.MINIMALE: 1, Gravite.SIGNIFICATIVE: 2, Gravite.GRAVE: 3, Gravite.CRITIQUE: 4}


def risk_level(gravite: Gravite, vraisemblance: VraisemblanceInitiale | None) -> NiveauRisque | None:
    """The risk level of a scenario, read off gravité x vraisemblance (§18 step 29).

    Code, never the model: the scale is part of the business layer (§16 step 9).

    ponytail: product of the two 1..4 ranks, banded — the same construction as
    atelier 2's pertinence_of. It is the calibration knob: replace the bands here
    (one function, one test) when the mission adopts its own risk matrix.
    """
    if vraisemblance is None:
        return None
    score = _GRAVITE_RANK[gravite] * _rank(vraisemblance)
    if score <= 2:
        return NiveauRisque.FAIBLE
    if score <= 4:
        return NiveauRisque.MOYEN
    if score <= 8:
        return NiveauRisque.ELEVE
    return NiveauRisque.CRITIQUE


# --- Étape 0: the approved atelier 3 output must hold up --------------------

def validate_atelier3(w3: Workshop3Output, w2: Workshop2Output, w1: Workshop1Output) -> list[AtelierAlert]:
    """Check that every scenario resolves to what ateliers 1 and 2 actually hold (§2).

    Produces alerts, never repairs: a scenario pointing at a source de risque that no
    longer exists is fixed in atelier 3, not quietly worked around by N sub-agents.
    """
    alerts: list[AtelierAlert] = []
    if not w3.scenarios:
        alerts.append(AtelierAlert(
            reference="atelier3",
            probleme="Aucun scénario stratégique : l'atelier 4 n'a rien à analyser."))
    if w3.gate_decision.action not in {ACTION_RUN, ACTION_RUN_ANYWAY}:
        alerts.append(AtelierAlert(
            reference="point_de_comptage",
            probleme=(f"Le point de comptage n'a pas validé la liste (décision « "
                      f"{w3.gate_decision.action or 'aucune'} ») : l'atelier 4 n'en a pas le droit (§17)."),
        ))

    sources = {s.id for s in w2.sources_risque}
    objectifs = {o.id for o in w2.objectifs_vises}
    assets = {a.id for a in w1.biens_essentiels}
    events = {e.id for e in w1.evenements_redoutes}
    seen: set[str] = set()
    for scenario in w3.scenarios:
        if scenario.id in seen:
            alerts.append(AtelierAlert(reference=scenario.id, probleme="Identifiant de scénario en double."))
        seen.add(scenario.id)
        if scenario.source_risque_id not in sources:
            alerts.append(AtelierAlert(
                reference=scenario.id,
                probleme=f"Source de risque inconnue de l'atelier 2 : '{scenario.source_risque_id}'."))
        if scenario.objectif_vise_id not in objectifs:
            alerts.append(AtelierAlert(
                reference=scenario.id,
                probleme=f"Objectif visé inconnu de l'atelier 2 : '{scenario.objectif_vise_id}'."))
        unknown = [b for b in scenario.biens_essentiels_ids if b not in assets]
        unknown += [e for e in scenario.evenements_redoutes_ids if e not in events]
        if unknown:
            alerts.append(AtelierAlert(
                reference=scenario.id,
                probleme=f"Biens essentiels ou événements redoutés inconnus de l'atelier 1 : {unknown}."))

    if w3.scenarios and not w1.baseline_gaps_for_w4():
        alerts.append(AtelierAlert(
            reference="atelier1",
            probleme=("Aucun écart du socle transmis : la vraisemblance sera appréciée sur le seul "
                      "contexte. Vérifiez que c'est un socle sans écart, et non un socle non évalué."),
            bloquant=False,
        ))
    return alerts


# --- Étape 22a: the enumeration -> the modes opératoires to develop ----------

def _answered(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def dossier_voies(w4_input: Workshop4Input) -> list[str]:
    """The ways into this organisation the dossier actually names (§18).

    What the modes opératoires of a mission should cover between them. Read to tell
    the auditor which way in nobody explored — never to invent a mode.
    """
    return [
        voie for voie, fields in VOIE_CONTEXT_FIELDS.items()
        if any(_answered(w4_input.contexte.get(f)) for f in fields)
    ]


def build_modes(
    scenario: StrategicScenario,
    candidates: list[ModeCandidateProposal],
    w4_input: Workshop4Input,
) -> tuple[list[OperationalScenario], list[ElementEcarte]]:
    """Turn one scenario's enumeration into modes to develop, or justified rejects (§18).

    Four rules, code-enforced: a label; a justification anchored in a context field
    or a gap the mission actually holds; a voie from the fixed list; and one mode per
    way in — a second mode entering the same way at the same place is a wording of
    the first, not another route. Ids are assigned afterwards by ``number_modes``,
    once every scenario has been enumerated.
    """
    known = (set(w4_input.contexte)
             | {f.field_name for f in w4_input.faits_contexte}
             | {g.gap_id for g in w4_input.baseline_gaps})
    labels = {normalise(c.libelle) for c in candidates if c.libelle.strip()}
    kept: list[OperationalScenario] = []
    ecartes: list[ElementEcarte] = []
    seen: dict[tuple[str, str], str] = {}

    def reject(candidate: ModeCandidateProposal, raison: str, detail: str = "") -> None:
        ecartes.append(ElementEcarte(
            type="mode_operatoire", reference=scenario.id,
            libelle=candidate.libelle.strip() or "(sans libellé)",
            raison=raison, detail=detail or candidate.justification.strip()))

    for candidate in candidates:
        cited = [f.strip() for f in candidate.derived_from_fact_fields if f.strip() in known]
        if not candidate.libelle.strip() or not is_meaningful(candidate.justification) or not cited:
            reject(candidate, REASON_MODE_SANS_ANCRAGE,
                   f"Champs cités : {candidate.derived_from_fact_fields}")
            continue
        voie = normalise_tactic(candidate.voie).replace("-", "_")
        if voie not in VOIES:
            reject(candidate, REASON_MODE_VOIE_INCONNUE, f"Voie proposée : « {candidate.voie} »")
            continue
        if candidate.doublon_de.strip() and normalise(candidate.doublon_de) in labels:
            reject(candidate, REASON_MODE_DOUBLON,
                   f"Déclaré par l'agent comme reprenant « {candidate.doublon_de.strip()} »")
            continue
        key = (voie, normalise(candidate.point_entree) or voie)
        if key in seen:
            reject(candidate, REASON_MODE_DOUBLON,
                   f"Même voie et même point d'entrée que « {seen[key]} »")
            continue
        seen[key] = candidate.libelle.strip()
        entry = candidate.point_entree.strip()
        kept.append(OperationalScenario(
            id="",
            scenario_strategique_id=scenario.id,
            source_risque_id=scenario.source_risque_id,
            objectif_vise_id=scenario.objectif_vise_id,
            variante=candidate.libelle.strip(),
            voie=voie,
            variante_justification=(f"{entry} — " if entry else "")
                                   + f"{candidate.justification.strip()} ({', '.join(cited)})",
            biens_essentiels_ids=list(scenario.biens_essentiels_ids),
            evenements_redoutes_ids=list(scenario.evenements_redoutes_ids),
            gravite=scenario.gravite,
            vraisemblance_initiale=scenario.vraisemblance_initiale,
        ))
    return kept, ecartes


def number_modes(modes: list[OperationalScenario], *, start: int = 1) -> list[OperationalScenario]:
    """Assign SO-01.. in list order.

    Plain numbers, no SO-01a: ids are upper-cased wherever the auditor types one, so
    a letter suffix would stop matching.
    """
    return [m.model_copy(update={"id": f"SO-{n:02d}"}) for n, m in enumerate(modes, start)]


def remove_modes(
    output: Workshop4Output, ids: Iterable[str], raison: str, detail: str = ""
) -> Workshop4Output:
    """Drop modes not developed yet, each leaving an écarté entry (§16, §19).

    A developed analysis is never removed this way — it is reviewed, not deleted.
    """
    chosen = set(ids)
    dropped = [s for s in output.scenarios
               if s.id in chosen and s.statut == STATUT_A_ANALYSER]
    return output.model_copy(update={
        "scenarios": [s for s in output.scenarios if s not in dropped],
        "elements_ecartes": [
            *output.elements_ecartes,
            *(ElementEcarte(type="mode_operatoire", reference=s.scenario_strategique_id,
                            libelle=f"{s.id} {s.variante}", raison=raison, detail=detail)
              for s in dropped),
        ],
    })


def modes_beyond_cap(output: Workshop4Output, cap: int) -> list[str]:
    """The ids a strategic scenario has past ``cap`` modes, in enumeration order (§18 step 27)."""
    seen: dict[str, int] = {}
    beyond: list[str] = []
    for scenario in output.scenarios:
        seen[scenario.scenario_strategique_id] = seen.get(scenario.scenario_strategique_id, 0) + 1
        if seen[scenario.scenario_strategique_id] > cap and scenario.statut == STATUT_A_ANALYSER:
            beyond.append(scenario.id)
    return beyond


# --- Étapes 23-24: one sub-agent's answer -> an analysed scenario ------------

def _same_name(cited: str, official: str) -> bool:
    a, b = normalise(cited), normalise(official)
    return a == b or a in b or b in a


def build_analysis(
    proposal: ScenarioAnalysisProposal,
    pending: OperationalScenario,
    w4_input: Workshop4Input,
    catalogue: AttackCatalogue,
) -> tuple[OperationalScenario, list[ElementEcarte]]:
    """Check one sub-agent's answer and turn it into an analysed scenario (§18 steps 23-24).

    Nothing is rejected wholesale: the auditor reviews every analysis, so each
    problem becomes an anomaly on it. What cannot stand in the output is removed
    and said so — a technique id the base never returned is dropped from its step
    (the action stays described), an entry on a gap that was never transmitted goes
    to the écartés. Blocking anomalies make confirming the scenario an explicit
    override.
    """
    anomalies: list[Anomaly] = []
    ecartes: list[ElementEcarte] = []

    def flag(code: str, message: str, *, bloquante: bool = True) -> None:
        anomalies.append(Anomaly(code=code, message=message, bloquante=bloquante))

    supports = {s.id for s in w4_input.biens_supports}
    tactics = set(catalogue.tactics)

    # --- the attack path, step by step (§18 step 23) ---
    steps: list[AttackStep] = []
    cited: dict[str, list[int]] = {}  # technique id -> the steps citing it
    for n, raw in enumerate(proposal.attack_path, 1):
        technique_id, readable = read_technique_id(raw.technique_id)
        if not readable:
            flag("identifiant_illisible",
                 f"Étape {n} : « {raw.technique_id} » n'est pas un identifiant de technique exploitable.")
        technique = catalogue.techniques.get(technique_id) if technique_id else None
        if technique_id:
            cited.setdefault(technique_id, []).append(n)

        tactic = normalise_tactic(raw.tactic)
        if tactic not in tactics:
            if technique is not None:
                flag("tactique_hors_catalogue",
                     f"Étape {n} : tactique « {raw.tactic} » absente du catalogue, remplacée par celle "
                     f"de {technique.technique_id} ({technique.tactics[0]}).", bloquante=False)
                tactic = technique.tactics[0]
            else:
                flag("tactique_inconnue", f"Étape {n} : « {raw.tactic} » n'est pas une tactique du catalogue ATT&CK.")
        elif technique is not None and tactic not in technique.tactics:
            flag("tactique_incoherente",
                 f"Étape {n} : {technique.technique_id} ({technique.name}) relève de "
                 f"{', '.join(technique.tactics)}, pas de {tactic} — tactique corrigée.", bloquante=False)
            # FIX bug n°1 : la tactique auto-déclarée par le LLM était retenue telle quelle
            # même quand elle contredit le catalogue ATT&CK pour cette technique (ex. T1090
            # Proxy déclaré en "initial-access" alors qu'il relève de "command-and-control").
            # Sans cette ligne, phase_of(tactic) plus bas se base sur une tactique fausse et
            # peut faire croire à une étape "Rentrer" ou "Exploiter" qui n'existe pas vraiment.
            tactic = technique.tactics[0]

        if technique is not None and raw.technique_name.strip() and not _same_name(raw.technique_name, technique.name):
            flag("nom_technique_divergent",
                 f"Étape {n} : « {raw.technique_name.strip()} » cité sous {technique.technique_id}, "
                 f"dont le nom ATT&CK est « {technique.name} » — l'identifiant est peut-être le mauvais.",
                 bloquante=False)

        support = raw.bien_support_id.strip()
        if support and support not in supports:
            flag("bien_support_inconnu",
                 f"Étape {n} : « {support} » n'est pas un bien support de l'atelier 1.", bloquante=False)
            support = ""

        description = raw.description.strip()
        if not description:
            flag("etape_sans_description", f"Étape {n} : aucune action décrite.")
        steps.append(AttackStep(
            phase=phase_of(tactic),
            tactic=tactic,
            technique_id=technique.technique_id if technique else None,
            technique_name=technique.name if technique else "",
            description=description,
            bien_support_id=support,
            justification=raw.justification.strip(),
        ))

    for technique_id in unknown_technique_ids(cited, catalogue.techniques):
        flag("technique_inconnue",
             f"Étape {', '.join(map(str, cited[technique_id]))} : {technique_id} n'est pas une technique "
             f"active du catalogue ATT&CK ({catalogue.version}) — identifiant retiré, l'action reste décrite.")

    if not steps:
        flag("chemin_vide", "Aucune étape : le mode opératoire n'est pas décrit.")
    else:
        phases = {s.phase for s in steps}
        # FIX bug lié au n°1 : ces deux checks passaient en bloquante=False, donc une
        # chaîne sans vrai accès initial (ex. SO-01, une fois T1090 correctement reclassé
        # en command-and-control) pouvait quand même être confirmée par l'auditeur sans
        # override explicite. Une kill chain sans "Rentrer" ou sans "Exploiter" n'est pas
        # une kill chain complète au sens même du prompt (§18) — ça doit bloquer.
        if PHASE_RENTRER not in phases:
            flag("phase_absente", "Aucune étape « Rentrer » (initial-access) : par où la source de risque entre-t-elle ?",
                 bloquante=True)
        if PHASE_EXPLOITER not in phases:
            flag("phase_absente",
                 "Aucune étape « Exploiter » (collection, exfiltration, impact) : l'événement redouté n'est pas atteint.",
                 bloquante=True)
    if not proposal.resume.strip():
        flag("resume_absent", "Aucun résumé du mode opératoire.", bloquante=False)

    # --- the baseline gaps (§18 step 24) ---
    gaps = {g.gap_id: g for g in w4_input.baseline_gaps}
    considered: list[GapConsideration] = []
    examined: set[str] = set()
    for entry in proposal.baseline_gaps_considered:
        gap_id = entry.gap_id.strip()
        if gap_id not in gaps:
            ecartes.append(ElementEcarte(
                type="entree_ecart", reference=gap_id or "(sans gap_id)", libelle=pending.id,
                raison=REASON_ENTREE_ECART_INCONNU, detail=entry.impact_on_scenario.strip()))
            flag("ecart_inconnu", f"Entrée sur « {gap_id} », qui n'est pas un écart transmis — écartée.",
                 bloquante=False)
            continue
        if gap_id in examined:
            continue
        examined.add(gap_id)
        impact_type = read_impact_type(entry.impact_type)
        if impact_type is None:
            flag("impact_type_invalide", f"{gap_id} : « {entry.impact_type} » n'est pas un impact_type autorisé.")
            continue
        if is_weak_entry(entry):
            flag("impact_vide", f"{gap_id} ({impact_type.value}) : impact_on_scenario vide — un « "
                 f"{impact_type.value} » doit aussi être justifié.")
        considered.append(GapConsideration(
            gap_id=gap_id, impact_type=impact_type, impact_on_scenario=entry.impact_on_scenario.strip()))

    missing = [g for g in pertinent_gap_ids(w4_input.baseline_gaps, (s.tactic for s in steps))
               if g not in examined]
    if missing:
        flag("ecarts_pertinents_absents",
             f"Écarts liés aux tactiques du chemin mais non examinés : {', '.join(missing)}.")
    unexamined = [g for g in gaps if g not in examined and g not in missing]
    if unexamined:
        flag("ecarts_non_examines", f"{len(unexamined)} autre(s) écart(s) non examiné(s) : {', '.join(unexamined)}.",
             bloquante=False)

    # --- the likelihood ---
    reason = proposal.likelihood_revision_reason.strip()
    if not is_meaningful(reason):
        flag("motif_revision_absent", "Aucun motif de révision de la vraisemblance, même pour la maintenir.")
    revised = read_likelihood(proposal.revised_likelihood)
    if revised is None:
        flag("vraisemblance_invalide",
             f"« {proposal.revised_likelihood} » n'est pas une valeur de l'échelle V1 à V4 — niveau de risque non calculé.")
    elif abs(_rank(revised) - _rank(pending.vraisemblance_initiale)) >= 2:
        flag("revision_forte",
             f"Vraisemblance révisée de {pending.vraisemblance_initiale.value} à {revised.value} : "
             "plus d'un niveau d'écart, à examiner.", bloquante=False)

    # --- a new gap, only when the dossier supports it ---
    new_gap = None
    raw_gap = proposal.new_baseline_gap_identified
    if raw_gap is not None and (raw_gap.weakness.strip() or raw_gap.justification.strip()):
        known = set(w4_input.contexte) | {f.field_name for f in w4_input.faits_contexte}
        fields = [f.strip() for f in raw_gap.derived_from_fact_fields if f.strip() in known]
        if raw_gap.weakness.strip() and fields:
            new_gap = NewBaselineGap(
                weakness=raw_gap.weakness.strip(),
                risk_categories=[c for c in raw_gap.risk_categories if c in RISK_CATEGORIES],
                justification=raw_gap.justification.strip(),
                derived_from_fact_fields=fields,
            )
        else:
            ecartes.append(ElementEcarte(
                type="nouvel_ecart", reference=pending.id, libelle=raw_gap.weakness.strip(),
                raison=REASON_NOUVEL_ECART_SANS_ANCRAGE,
                detail=f"Champs cités : {raw_gap.derived_from_fact_fields}"))

    # The analysis this one replaces leaves a trace, with what the auditor objected to.
    if pending.iterations:
        ecartes.insert(0, ElementEcarte(
            type="analyse", reference=f"{pending.id} (analyse {pending.iterations})",
            libelle=pending.resume, raison=REASON_ANALYSE_REMPLACEE,
            detail=f"{(pending.motifs_auditeur or [''])[-1]} — chemin : {path_summary(pending)}"))

    analysed = pending.model_copy(update={
        "resume": proposal.resume.strip(),
        "attack_path": steps,
        "likelihood_revision_reason": reason,
        "revised_likelihood": revised,
        "revised_risk_level": risk_level(pending.gravite, revised),
        "baseline_gaps_considered": considered,
        "new_baseline_gap_identified": new_gap,
        "anomalies": anomalies,
        "statut": STATUT_ANALYSE,
        "iterations": pending.iterations + 1,
    })
    return analysed, ecartes


def path_summary(scenario: OperationalScenario) -> str:
    return " > ".join(s.technique_id or s.tactic or "?" for s in scenario.attack_path) or "(vide)"


# --- Étapes 25-27: the auditor's review --------------------------------------

def confirm(output: Workshop4Output, ids: Iterable[str]) -> Workshop4Output:
    chosen = set(ids)
    return output.model_copy(update={"scenarios": [
        s.model_copy(update={"statut": STATUT_CONFIRME}) if s.id in chosen else s
        for s in output.scenarios
    ]})


def send_back(output: Workshop4Output, ids: Iterable[str], motif: str, mode: str) -> Workshop4Output:
    """Send scenarios back to their sub-agent, with the auditor's reason (§18 step 25).

    The rejected analysis stays on the scenario until its redo replaces it, so the
    redo prompt can show it as the answer not to give again. Any reopening voids the
    coherence review: it is only valid over a stable set (§18 step 27).
    """
    if not is_meaningful(motif):
        raise ValueError("Un motif non vide est obligatoire pour renvoyer une analyse (§8).")
    if mode not in STATUTS_EN_ATTENTE:
        raise ValueError(f"Mode de reprise inconnu : {mode}")
    chosen = set(ids)
    return output.model_copy(update={
        "scenarios": [
            s.model_copy(update={"statut": mode, "motifs_auditeur": [*s.motifs_auditeur, motif.strip()]})
            if s.id in chosen else s
            for s in output.scenarios
        ],
        "coherence": None,
    })


# --- Étape 28: the coherence findings ----------------------------------------

def build_coherence(
    proposals: list[CoherenceFindingProposal], scenarios: list[OperationalScenario]
) -> tuple[list[CoherenceFinding], list[ElementEcarte]]:
    """Keep the findings that name real scenarios and say what is wrong.

    Coherence is relational, so a finding names at least two scenarios. A revision
    names which of them to revise and to what — a different value on the V1..V4 scale.
    """
    by_id = {s.id: s for s in scenarios}
    findings: list[CoherenceFinding] = []
    ecartes: list[ElementEcarte] = []
    for proposal in proposals:
        kind = proposal.type.strip()
        ids = list(dict.fromkeys(i.strip().upper() for i in proposal.scenario_ids if i.strip().upper() in by_id))
        target = proposal.scenario_a_reviser.strip().upper()
        proposed = read_likelihood(proposal.vraisemblance_proposee)
        valid = kind in CONSTAT_LABELS and len(ids) >= 2 and is_meaningful(proposal.explication)
        if valid and kind == CONSTAT_REVISION:
            valid = target in ids and proposed is not None and proposed != by_id[target].revised_likelihood
        if not valid:
            ecartes.append(ElementEcarte(
                type="constat_coherence", reference=", ".join(proposal.scenario_ids) or "(aucun)",
                libelle=kind, raison=REASON_CONSTAT_INVALIDE, detail=proposal.explication.strip()))
            continue
        is_revision = kind == CONSTAT_REVISION
        findings.append(CoherenceFinding(
            type=kind, scenario_ids=ids, explication=proposal.explication.strip(),
            scenario_a_reviser=target if is_revision else "",
            vraisemblance_proposee=proposed.value if is_revision else "",
        ))
    return findings, ecartes


def apply_coherence(output: Workshop4Output) -> Workshop4Output:
    """Apply the accepted revisions: new likelihood, reason extended, risk level re-read.

    ponytail: two revisions of the same scenario — the first one wins. The coherence
    pass is asked for one finding per problem; handle conflicts if real runs show them.
    """
    review = output.coherence
    revisions: dict[str, CoherenceFinding] = {}
    for finding in (review.constats if review else []):
        if finding.type == CONSTAT_REVISION:
            revisions.setdefault(finding.scenario_a_reviser, finding)

    scenarios = []
    for scenario in output.scenarios:
        finding = revisions.get(scenario.id)
        if finding is None:
            scenarios.append(scenario)
            continue
        new = VraisemblanceInitiale(finding.vraisemblance_proposee)
        before = scenario.revised_likelihood.value if scenario.revised_likelihood else "—"
        scenarios.append(scenario.model_copy(update={
            "revised_likelihood": new,
            "revised_risk_level": risk_level(scenario.gravite, new),
            "likelihood_revision_reason": (
                f"{scenario.likelihood_revision_reason} [Cohérence : {before} -> {new.value}, "
                f"{finding.explication}]").strip(),
        }))
    decided = review.model_copy(update={"decision": COHERENCE_APPLIQUEE}) if review else None
    return output.model_copy(update={"scenarios": scenarios, "coherence": decided})


# --- Étape 29a: which mode opératoire drives the risk -------------------------

def _mode_number(scenario_id: str) -> int:
    digits = "".join(c for c in scenario_id if c.isdigit())
    return int(digits) if digits else 0


def _selection_key(scenario: OperationalScenario) -> tuple:
    """Most likely first; ties broken on evidence, never on chance."""
    return (
        _rank(scenario.revised_likelihood) if scenario.revised_likelihood else 0,
        -len(scenario.blocking_anomalies),
        sum(1 for g in scenario.baseline_gaps_considered
            if g.impact_type is ImpactType.INCREASES_LIKELIHOOD),
        -len(scenario.attack_path),
        -_mode_number(scenario.id),
    )


def select_driving(scenarios: list[OperationalScenario]) -> list[OperationalScenario]:
    """Per strategic scenario, the most likely developed mode drives the risk (§18 step 29).

    The ANSSI rule: a strategic scenario may have several modes opératoires, and its
    likelihood is the one of its easiest route. The others stay written, with why
    they do not drive it — an alternative route is what atelier 5 still has to cover.

    A choice the auditor made (``retenu_par_auditeur``) is never recomputed: they
    outrank this function (§2).
    """
    groups: dict[str, list[OperationalScenario]] = {}
    for scenario in scenarios:
        groups.setdefault(scenario.scenario_strategique_id, []).append(scenario)

    decided: dict[str, OperationalScenario] = {}
    for strategic_id, modes in groups.items():
        overridden = next((m for m in modes if m.retenu_par_auditeur), None)
        developed = [m for m in modes
                     if m.revised_likelihood is not None and m.statut not in STATUTS_EN_ATTENTE]
        driving = overridden or (max(developed, key=_selection_key) if developed else None)
        others = [m.revised_likelihood.value for m in developed
                  if driving is not None and m.id != driving.id and m.revised_likelihood]
        for mode in modes:
            if driving is not None and mode.id == driving.id:
                motif = mode.motif_selection if overridden else (
                    f"Mode le plus vraisemblable de {strategic_id} : "
                    f"{mode.revised_likelihood.value if mode.revised_likelihood else '?'}"
                    + (f" contre {', '.join(others)}" if others else " (seul mode développé)")
                )
                decided[mode.id] = mode.model_copy(update={"retenu": True, "motif_selection": motif})
                continue
            if driving is None:
                motif = "Aucun mode développé pour ce scénario stratégique."
            elif mode.statut in STATUTS_EN_ATTENTE or mode.revised_likelihood is None:
                motif = f"Pas encore développé — {driving.id} mène pour l'instant."
            elif mode.revised_likelihood is driving.revised_likelihood:
                motif = (f"Vraisemblance identique à {driving.id} "
                         f"({mode.revised_likelihood.value}) — départagé sur les anomalies, "
                         "les écarts exploités puis la longueur du chemin.")
            else:
                motif = (f"Vraisemblance {mode.revised_likelihood.value} contre "
                         f"{driving.revised_likelihood.value if driving.revised_likelihood else '?'} "
                         f"pour le mode retenu {driving.id}.")
            decided[mode.id] = mode.model_copy(update={"retenu": False, "motif_selection": motif})
    return [decided.get(s.id, s) for s in scenarios]


def set_driving(output: Workshop4Output, mode_id: str, reason: str) -> Workshop4Output:
    """The auditor designates which mode drives the risk of its scenario (§2, §8)."""
    if not is_meaningful(reason):
        raise ValueError("Un motif non vide est obligatoire pour changer le mode retenu (§8).")
    target = next((s for s in output.scenarios if s.id == mode_id), None)
    if target is None:
        raise ValueError(f"Mode opératoire inconnu : {mode_id}")

    def updated(mode: OperationalScenario) -> OperationalScenario:
        if mode.scenario_strategique_id != target.scenario_strategique_id:
            return mode
        if mode.id == target.id:
            return mode.model_copy(update={
                "retenu": True, "retenu_par_auditeur": True,
                "motif_selection": f"Retenu par l'auditeur : {reason.strip()}"})
        return mode.model_copy(update={
            "retenu": False, "retenu_par_auditeur": False,
            "motif_selection": f"Écarté au profit de {target.id} par l'auditeur : {reason.strip()}"})

    return output.model_copy(update={"scenarios": [updated(s) for s in output.scenarios]})


def driving_modes(output: Workshop4Output) -> list[OperationalScenario]:
    """The retained mode of each strategic scenario — what coherence and atelier 5 read first."""
    return [s for s in output.scenarios if s.retenu]


# --- Étape 29: the final merge and the quality checker ------------------------

def finalize(output: Workshop4Output, catalogue: AttackCatalogue) -> Workshop4Output:
    """Re-derive what is code's to derive, whatever edited the output since.

    Phases come from tactics, names from the ATT&CK base, the risk level from the
    matrix. An auditor who corrects a likelihood by hand gets the risk level that
    follows from it, not the one printed before the correction.
    """
    scenarios = []
    for scenario in output.scenarios:
        steps = [
            step.model_copy(update={
                "phase": phase_of(step.tactic),
                "technique_name": (catalogue.techniques[step.technique_id].name
                                   if step.technique_id in catalogue.techniques else step.technique_name),
            })
            for step in scenario.attack_path
        ]
        scenarios.append(scenario.model_copy(update={
            "attack_path": steps,
            "revised_risk_level": risk_level(scenario.gravite, scenario.revised_likelihood),
        }))
    return output.model_copy(update={"scenarios": select_driving(scenarios)})


def run_quality_checks(
    w4_input: Workshop4Input, output: Workshop4Output, catalogue: AttackCatalogue
) -> QualityReport:
    """Re-check the assembled result on its content, rather than trusting the checks that ran.

    Anomalies describe what a sub-agent handed back; this describes what is about
    to be approved — including anything an auditor typed in by hand since.
    """
    checks: list[QualityCheck] = []
    scenarios = output.scenarios

    def check(controle: str, problems: list[str], *, statut: str = STATUT_ERREUR, ok_message: str = "") -> None:
        checks.append(QualityCheck(
            controle=controle,
            statut=statut if problems else STATUT_OK,
            message="; ".join(problems) if problems else ok_message,
        ))

    # 1. Couverture — every strategic scenario has at least one developed mode, and
    #    exactly one of them drives its risk (§18 step 29).
    developed: dict[str, list[OperationalScenario]] = {}
    for scenario in scenarios:
        if scenario.statut not in STATUTS_EN_ATTENTE:
            developed.setdefault(scenario.scenario_strategique_id, []).append(scenario)
    coverage = [f"scénario stratégique sans mode opératoire développé : {s.id}"
                for s in w4_input.scenarios if s.id not in developed]
    for strategic_id, modes in developed.items():
        retained = [m.id for m in modes if m.retenu]
        if len(retained) != 1:
            coverage.append(f"{strategic_id} : {len(retained)} mode(s) retenu(s) au lieu d'un ({retained})")
    check("Couverture", coverage,
          ok_message=f"{len(scenarios)} mode(s) opératoire(s) pour {len(developed)} scénario(s) "
                     "stratégique(s), un mode retenu par scénario.")

    # 2. Sélection — the driving mode is the most likely one, unless the auditor said otherwise (§2).
    selection = []
    for strategic_id, modes in developed.items():
        driving = next((m for m in modes if m.retenu), None)
        if driving is None or driving.retenu_par_auditeur:
            continue
        best = max(modes, key=_selection_key)
        if best.id != driving.id:
            selection.append(
                f"{strategic_id} : {driving.id} retenu alors que {best.id} est plus vraisemblable")
    check("Sélection du mode retenu", selection,
          ok_message="Le mode retenu de chaque scénario est le plus vraisemblable, "
                     "ou celui que l'auditeur a désigné.")

    # 3. Voies d'entrée — the ways in the dossier names that no mode explored.
    explored = {s.voie for s in scenarios if s.voie}
    unexplored = [VOIE_LABELS.get(v, v) for v in dossier_voies(w4_input) if v not in explored]
    check("Voies d'entrée explorées",
          [f"aucun mode opératoire n'emprunte : {', '.join(unexplored)}"] if unexplored else [],
          statut=STATUT_AVERTISSEMENT,
          ok_message="Chaque voie d'entrée nommée par le dossier est explorée par un mode au moins.")

    # 4. Écarts exploités — a gap that raises no likelihood anywhere is either
    #    irrelevant to the study, or a mode opératoire is missing.
    exploited = {g.gap_id for s in scenarios for g in s.baseline_gaps_considered
                 if g.impact_type in {ImpactType.INCREASES_LIKELIHOOD, ImpactType.INCREASES_IMPACT}}
    idle = [g.gap_id for g in w4_input.baseline_gaps if g.gap_id not in exploited]
    check("Écarts du socle exploités",
          [f"aucun mode ne s'appuie sur : {', '.join(idle)}"] if idle else [],
          statut=STATUT_AVERTISSEMENT,
          ok_message="Chaque écart du socle pèse sur au moins un mode opératoire.")

    # 5. Revue — nothing pending, everything confirmed by the auditor (§18 steps 25-27).
    pending = [s.id for s in scenarios if s.statut in STATUTS_EN_ATTENTE]
    unconfirmed = [s.id for s in scenarios if s.statut == STATUT_ANALYSE]
    check("Revue de l'auditeur",
          ([f"analyses en attente : {pending}"] if pending else [])
          + ([f"analyses non confirmées : {unconfirmed}"] if unconfirmed else []),
          ok_message="Chaque analyse a été confirmée par l'auditeur.")

    # 6. Techniques — every id is one the base returned (§18 step 23).
    invalid = [f"{s.id} étape {n} : {step.technique_id}"
               for s in scenarios for n, step in enumerate(s.attack_path, 1)
               if step.technique_id and step.technique_id not in catalogue.techniques]
    check("Techniques ATT&CK", invalid,
          ok_message=f"Tous les identifiants existent dans le catalogue {catalogue.version}.")

    # 7. Chemins — described, on known tactics.
    paths = [f"{s.id} sans étape" for s in scenarios if s.statut not in STATUTS_EN_ATTENTE and not s.attack_path]
    paths += [f"{s.id} étape {n} : {'tactique inconnue' if not step.phase else 'action non décrite'}"
              for s in scenarios for n, step in enumerate(s.attack_path, 1)
              if not step.phase or not step.description.strip()]
    check("Modes opératoires", paths, ok_message="Chaque étape a une tactique connue et une action décrite.")

    # 8. Écarts du socle — pertinent ones examined, no entry left without a sentence (§18 step 24).
    gaps_problems = []
    for s in scenarios:
        if s.statut in STATUTS_EN_ATTENTE:
            continue
        weak = [g.gap_id for g in s.baseline_gaps_considered if is_weak_entry(g)]
        if weak:
            gaps_problems.append(f"{s.id} : impact_on_scenario vide pour {weak}")
        examined = {g.gap_id for g in s.baseline_gaps_considered}
        absent = [g for g in pertinent_gap_ids(w4_input.baseline_gaps, (st.tactic for st in s.attack_path))
                  if g not in examined]
        if absent:
            gaps_problems.append(f"{s.id} : écarts pertinents non examinés {absent}")
    check("Écarts du socle", gaps_problems,
          ok_message="Écarts pertinents examinés, chaque impact justifié.")

    # 9. Vraisemblance et niveau de risque.
    rating = []
    for s in scenarios:
        if s.statut in STATUTS_EN_ATTENTE:
            continue
        if s.revised_likelihood is None:
            rating.append(f"{s.id} sans vraisemblance révisée")
        elif s.revised_risk_level is not risk_level(s.gravite, s.revised_likelihood):
            rating.append(f"{s.id} : niveau de risque incohérent avec {s.gravite.value} x {s.revised_likelihood.value}")
        if not is_meaningful(s.likelihood_revision_reason):
            rating.append(f"{s.id} sans motif de révision")
    check("Vraisemblance et niveau de risque", rating,
          ok_message="Vraisemblance V1..V4 motivée, niveau lu dans la matrice.")

    # 10. Cotations reprises — gravité and initial likelihood come from atelier 3.
    strategic = {s.id: s for s in w4_input.scenarios}
    carried = [
        f"{s.id} ne reprend pas la cotation de {s.scenario_strategique_id}"
        for s in scenarios
        if s.scenario_strategique_id in strategic
        and (s.gravite, s.vraisemblance_initiale) != (strategic[s.scenario_strategique_id].gravite,
                                                      strategic[s.scenario_strategique_id].vraisemblance_initiale)
    ]
    check("Cotations reprises", carried,
          ok_message="Gravité et vraisemblance initiale reprises des ateliers 1 à 3.")

    # 11. Cohérence — run once the set was stable, and ruled on (§18 step 28).
    coherence = []
    if len(scenarios) >= 2:
        if output.coherence is None:
            coherence.append("vérification de cohérence non effectuée")
        elif not output.coherence.decision:
            coherence.append("constats de cohérence en attente de décision")
    check("Cohérence d'ensemble", coherence,
          ok_message="Vérification de cohérence effectuée et tranchée.")

    # 12. Anomalies levées par l'auditeur — confirmed anyway; the report must say so.
    overridden = [f"{s.id} ({', '.join(sorted({a.code for a in s.blocking_anomalies}))})"
                  for s in scenarios if s.statut == STATUT_CONFIRME and s.blocking_anomalies]
    check("Anomalies confirmées malgré tout", overridden, statut=STATUT_AVERTISSEMENT,
          ok_message="Aucune analyse confirmée avec une anomalie bloquante.")

    # 13. Nouveaux écarts — proposals only, atelier 1 is not modified.
    proposed = [f"{s.id} : {s.new_baseline_gap_identified.weakness}"
                for s in scenarios if s.new_baseline_gap_identified]
    check("Nouveaux écarts proposés", proposed, statut=STATUT_AVERTISSEMENT,
          ok_message="Aucun écart nouveau proposé.")
    # 14. Cohérence de la gravité par rapport aux enjeux — Empêche les risques majeurs sous-évalués
    gravite_critique_problemes = []
    for s in scenarios:
        if s.statut in STATUTS_EN_ATTENTE:
            continue
        # Si la gravité est Minimale mais que le scénario concerne des données bancaires ou des pannes critiques
        if s.gravite == Gravite.MINIMALE and any("bancaire" in (a or "").casefold() or "vente" in (a or "").casefold() for a in s.biens_essentiels_ids):
            gravite_critique_problemes.append(
                f"Scénario {s.id} ({s.id}) : Gravité 'Minimale' incohérente pour des données bancaires ou un processus de vente critique."
            )
            
    check(
        "Cohérence de la gravité",
        gravite_critique_problemes,
        statut=STATUT_ERREUR,
        ok_message="La gravité des scénarios est cohérente avec les enjeux métiers."
    )
    return QualityReport(checks=checks)
