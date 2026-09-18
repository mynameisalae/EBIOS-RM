"""Deterministic atelier 3 methodology (conception §17).

Pure functions, no LLM and no I/O. Everything that decides rather than proposes
lives here: validating the atelier 2 output, turning candidate scenarios into
retained ones or justified rejects, carrying gravité and the atelier 2 ratings
forward without re-judging them, applying the critique pass, applying the count
gate's merge and subset, and running the quality checker.

The agent writes the route and argues it; it cannot talk its way past this module.
"""

from __future__ import annotations

from ebios_rm.domain.enums import Gravite, Origin, Pertinence, VraisemblanceInitiale
from ebios_rm.domain.strategic_scenario import StrategicScenario
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.assessment import normalise
from ebios_rm.workshops.workshop2_sources_risque.models import Workshop2Output
from ebios_rm.workshops.workshop3_scenarios_strategiques.models import (
    ACTION_CHOOSE_SUBSET,
    ACTION_MERGE,
    ACTION_RUN_ANYWAY,
    REASON_COUPLE_INCONNU,
    REASON_DOUBLON,
    REASON_FUSIONNE,
    REASON_HORS_SOUS_ENSEMBLE,
    REASON_PARTIE_PRENANTE_INCONNUE,
    REASON_QUASI_DOUBLON,
    REASON_SANS_ANCRAGE_CONTEXTE,
    REASON_SANS_JUSTIFICATION,
    STATUT_AVERTISSEMENT,
    STATUT_ERREUR,
    STATUT_OK,
    AtelierAlert,
    CritiqueVerdict,
    ElementEcarte,
    GateDecision,
    QualityCheck,
    QualityReport,
    ScenarioProposal,
    Workshop3Input,
)

# Worst-first ordering of the four gravité values (conception §15).
_GRAVITE_RANK = {
    Gravite.MINIMALE: 0, Gravite.SIGNIFICATIVE: 1, Gravite.GRAVE: 2, Gravite.CRITIQUE: 3,
}
_PERTINENCE_RANK = {Pertinence.FAIBLE: 0, Pertinence.MOYEN: 1, Pertinence.ELEVE: 2}

# Gate actions that change the list or override a threshold: those owe a reason (§8).
_ACTIONS_NEEDING_A_REASON = frozenset({ACTION_RUN_ANYWAY, ACTION_MERGE, ACTION_CHOOSE_SUBSET})

# Words too common to prove that a stakeholder name came from the dossier:
# « prestataire » appears in half the contexts ever written.
_GENERIC_WORDS = frozenset({
    "prestataire", "prestataires", "fournisseur", "fournisseurs", "partenaire",
    "partenaires", "societe", "entreprise", "groupe", "service", "services",
    "client", "clients", "sous", "traitant", "traitants", "externe", "externes",
    "tiers", "cloud", "editeur", "editeurs", "operateur", "operateurs",
})


# --- Étape 0: validate the atelier 2 output before reasoning ---------------

def validate_atelier2(w2: Workshop2Output, w1: Workshop1Output) -> list[AtelierAlert]:
    """Check that the approved atelier 2 output can be reasoned on (§17, white-box §4).

    Produces alerts; never repairs. A couple pointing at a source that does not
    exist is an atelier 2 defect, and building a scenario on it would carry the
    defect into atelier 4 wearing an atelier 3 id.
    """
    alerts: list[AtelierAlert] = []
    sources = {s.id for s in w2.sources_risque}
    objectifs = {o.id: o for o in w2.objectifs_vises}
    known_be = {a.id for a in w1.biens_essentiels}

    if not w2.couples:
        alerts.append(AtelierAlert(
            reference="atelier2",
            probleme="Aucun couple SR/OV retenu : l'atelier 3 n'a aucun scénario à construire.",
        ))

    seen: set[str] = set()
    for couple in w2.couples:
        if couple.id in seen:
            alerts.append(AtelierAlert(
                reference=couple.id, probleme="Identifiant de couple SR/OV en double."))
        seen.add(couple.id)
        if couple.source_risque_id not in sources:
            alerts.append(AtelierAlert(
                reference=couple.id,
                probleme=f"Le couple référence une source de risque inconnue : '{couple.source_risque_id}'.",
            ))
        if couple.objectif_vise_id not in objectifs:
            alerts.append(AtelierAlert(
                reference=couple.id,
                probleme=f"Le couple référence un objectif visé inconnu : '{couple.objectif_vise_id}'.",
            ))
        unknown = [b for b in couple.biens_essentiels_ids if b not in known_be]
        if unknown:
            alerts.append(AtelierAlert(
                reference=couple.id,
                probleme=f"Le couple vise des biens essentiels inconnus de l'atelier 1 : {unknown}.",
            ))

    # Non-blocking: without a feared event the scenario still holds, but its gravité
    # falls back to the lowest value and the auditor should know why.
    with_events = {e.bien_essentiel_id for e in w1.evenements_redoutes}
    orphans = sorted({
        be for c in w2.couples for be in c.biens_essentiels_ids
        if be in known_be and be not in with_events
    })
    if orphans:
        alerts.append(AtelierAlert(
            reference="atelier1",
            probleme=(
                "Aucun événement redouté sur ces biens essentiels, la gravité des scénarios "
                f"concernés ne peut pas être reprise : {orphans}."
            ),
            bloquant=False,
        ))
    return alerts


# --- Étape 1: candidate scenarios -> retained scenarios or justified rejects -

def gravite_of(w3_input: Workshop3Input, biens_essentiels_ids: list[str]) -> tuple[Gravite, list[str]]:
    """The worst gravité among the feared events on those assets, and their ids.

    Read from atelier 1, never re-judged: atelier 3 tells the route, it does not
    re-rate the consequence. Assets with no feared event contribute nothing, which
    is why validate_atelier2 warns about them.
    """
    events = [e for e in w3_input.evenements_redoutes if e.bien_essentiel_id in biens_essentiels_ids]
    if not events:
        return Gravite.MINIMALE, []
    worst = max(events, key=lambda e: _GRAVITE_RANK[e.gravite])
    return worst.gravite, [e.id for e in events]


def vraisemblance_pertinence(pertinence: Pertinence, vraisemblance: VraisemblanceInitiale) -> str:
    """« pertinence / vraisemblance », composed in code from atelier 2's own values (§17)."""
    return f"{pertinence.value} / {vraisemblance.value}"


def _significant_words(text: str) -> set[str]:
    """Words distinctive enough to prove a name came from the dossier.

    Acronyms count — SIH, ERP and VPN are three letters and are exactly what a
    stakeholder is called in practice. When a name is made only of common words
    (« l'éditeur du SIH » is « editeur » plus an acronym), the common ones are kept
    rather than leaving nothing to match on: an empty word set would reject every
    party whose name happens to be ordinary.
    """
    words = {w for w in normalise(text).split() if len(w) >= 3}
    distinctive = words - _GENERIC_WORDS
    return distinctive or words


def grounded_parties(parties: list[str], haystack: str) -> tuple[list[str], list[str]]:
    """Split stakeholder names into those the mission context knows and those it does not.

    A name counts as grounded when one of its distinctive words appears in the
    context. Deliberately permissive — « l'éditeur du SIH » and « SIH (éditeur) »
    are the same party, and rejecting the second would throw away a real route over
    wording. It still catches a party invented whole, which is what §2 forbids.
    """
    known: list[str] = []
    unknown: list[str] = []
    for party in parties:
        name = party.strip()
        if not name:
            continue
        words = _significant_words(name)
        (known if words & _significant_words(haystack) else unknown).append(name)
    return known, unknown


def context_haystack(w3_input: Workshop3Input) -> str:
    """Every context value as one searchable string — what a stakeholder must appear in."""
    return " ".join(str(value) for value in w3_input.contexte.values())


def build_scenarios(
    proposals: list[ScenarioProposal], w3_input: Workshop3Input
) -> tuple[list[StrategicScenario], list[ElementEcarte]]:
    """Turn candidate scenarios into retained ones, or into justified rejects (§17).

    Four rules, all code-enforced:
      * the couple must be one atelier 2 retained — never invented here;
      * a scenario carries a justification and at least one cited context field;
      * a stakeholder route must be one the dossier knows about;
      * one scenario per couple: a second is a duplicate, not a variant.

    Everything the model is not entitled to decide is looked up: the assets, the
    feared events, the gravité, the pertinence and the initial likelihood all come
    from the ateliers before this one.
    """
    couples = {c.id: c for c in w3_input.couples}
    haystack = context_haystack(w3_input)
    known_fields = {f.field_name for f in w3_input.faits_contexte} | set(w3_input.contexte)

    retained: list[StrategicScenario] = []
    discarded: list[ElementEcarte] = []
    seen_couples: dict[str, str] = {}

    def reject(proposal: ScenarioProposal, raison: str, detail: str = "") -> None:
        discarded.append(ElementEcarte(
            reference=proposal.couple_id or "(sans couple)",
            libelle=proposal.resume,
            raison=raison,
            detail=detail or proposal.justification.strip(),
        ))

    for proposal in proposals:
        couple = couples.get(proposal.couple_id.strip())
        if couple is None:
            reject(proposal, REASON_COUPLE_INCONNU, f"Couple proposé : '{proposal.couple_id}'.")
            continue
        if not proposal.justification.strip() or not proposal.resume.strip():
            reject(proposal, REASON_SANS_JUSTIFICATION)
            continue
        cited = [f.strip() for f in proposal.derived_from_fact_fields if f.strip() in known_fields]
        if not cited:
            reject(proposal, REASON_SANS_ANCRAGE_CONTEXTE,
                   f"Champs proposés : {proposal.derived_from_fact_fields}.")
            continue
        known_parties, unknown_parties = grounded_parties(proposal.parties_prenantes, haystack)
        if proposal.parties_prenantes and not known_parties:
            reject(proposal, REASON_PARTIE_PRENANTE_INCONNUE,
                   f"Parties proposées : {unknown_parties}.")
            continue
        if proposal.couple_id in seen_couples:
            reject(proposal, REASON_DOUBLON, f"Déjà décrit par {seen_couples[proposal.couple_id]}.")
            continue

        gravite, event_ids = gravite_of(w3_input, couple.biens_essentiels_ids)
        seen_couples[proposal.couple_id] = couple.id
        retained.append(StrategicScenario(
            id="",  # assigned below, once the list is in priority order
            source_risque_id=couple.source_risque_id,
            objectif_vise_id=couple.objectif_vise_id,
            couple_id=couple.id,
            resume=proposal.resume.strip(),
            justification=proposal.justification.strip(),
            parties_prenantes=known_parties,
            biens_essentiels_ids=list(couple.biens_essentiels_ids),
            evenements_redoutes_ids=event_ids,
            gravite=gravite,
            pertinence=couple.pertinence,
            vraisemblance_initiale=couple.vraisemblance_initiale,
            vraisemblance_pertinence=vraisemblance_pertinence(
                couple.pertinence, couple.vraisemblance_initiale
            ),
            origin=Origin.ASSESSMENT,
        ))
    return renumber(retained), discarded


def renumber(scenarios: list[StrategicScenario]) -> list[StrategicScenario]:
    """Order worst-first and assign SS-01.. in that order.

    Gravité leads: atelier 4 works down this list, and what would hurt most is what
    an interrupted study most needs to have covered. Ids are assigned after the
    sort, so SS-01 is the first scenario a reader should look at.
    """
    ordered = sorted(
        scenarios,
        key=lambda s: (
            -_GRAVITE_RANK[s.gravite],
            -_PERTINENCE_RANK[s.pertinence],
            -int(s.vraisemblance_initiale.value[1]),
            s.couple_id,
        ),
    )
    return [s.model_copy(update={"id": f"SS-{i:02d}"}) for i, s in enumerate(ordered, 1)]


# --- Étape 2: the critique pass prunes near-duplicates (§17 step 18) --------

def apply_critique(
    scenarios: list[StrategicScenario], verdicts: list[CritiqueVerdict]
) -> tuple[list[StrategicScenario], list[ElementEcarte]]:
    """Fold the scenarios the critique pass calls near-duplicates into the ones they repeat.

    A verdict is applied only when both ends exist and differ, and only when it
    carries a reason: « quasi-doublon » with no argument is the model shortening
    its own output, not a methodology finding. Chains are not followed — folding A
    into B while B is itself folded into C would silently empty the list, so a
    scenario that is itself being removed cannot receive another.
    """
    by_id = {s.id: s for s in scenarios}
    removed: dict[str, CritiqueVerdict] = {}
    for verdict in verdicts:
        target = verdict.doublon_de.strip()
        source = verdict.scenario_id.strip()
        if not target or source == target:
            continue
        if source not in by_id or target not in by_id:
            continue
        if not verdict.raison.strip():
            continue
        if target in removed or source in removed:
            continue
        removed[source] = verdict

    kept: list[StrategicScenario] = []
    discarded: list[ElementEcarte] = []
    for scenario in scenarios:
        verdict = removed.get(scenario.id)
        if verdict is None:
            kept.append(scenario)
            continue
        discarded.append(ElementEcarte(
            reference=scenario.id,
            libelle=scenario.resume,
            raison=REASON_QUASI_DOUBLON,
            detail=f"Repris par {verdict.doublon_de.strip()} : {verdict.raison.strip()}",
        ))
    return renumber(kept), discarded


# --- Étape 3: the count gate's own operations (§17 steps 20-21) -------------

def merge_scenarios(
    scenarios: list[StrategicScenario], group: list[str], justification: str
) -> tuple[list[StrategicScenario], list[ElementEcarte]]:
    """Merge a group of scenarios into the first of them (§17 step 21).

    The survivor keeps its own wording and gains the others' route and stakes; the
    merged ones leave an écarté entry carrying their summary, so nothing a reader
    might look for later has been deleted. Raises rather than merging silently when
    the justification is empty — §8 applies to the gate like everywhere else.
    """
    if not justification.strip():
        raise ValueError("Une justification non vide est obligatoire pour fusionner (§8).")
    by_id = {s.id: s for s in scenarios}
    members = [by_id[i] for i in group if i in by_id]
    if len(members) < 2:
        return scenarios, []

    survivor, folded = members[0], members[1:]
    merged = survivor.model_copy(update={
        "parties_prenantes": _union(survivor.parties_prenantes, *(f.parties_prenantes for f in folded)),
        "biens_essentiels_ids": _union(survivor.biens_essentiels_ids,
                                       *(f.biens_essentiels_ids for f in folded)),
        "evenements_redoutes_ids": _union(survivor.evenements_redoutes_ids,
                                          *(f.evenements_redoutes_ids for f in folded)),
        "gravite": max([survivor.gravite, *(f.gravite for f in folded)], key=lambda g: _GRAVITE_RANK[g]),
        "issu_de": _union(survivor.issu_de, [survivor.id], *([f.id] for f in folded)),
        "justification": f"{survivor.justification} (fusion : {justification.strip()})",
    })
    discarded = [
        ElementEcarte(reference=f.id, libelle=f.resume, raison=REASON_FUSIONNE,
                      detail=f"Fusionné dans {survivor.id} : {justification.strip()}")
        for f in folded
    ]
    kept = [merged if s.id == survivor.id else s for s in scenarios if s.id not in {f.id for f in folded}]
    return renumber(kept), discarded


def choose_subset(
    scenarios: list[StrategicScenario], keep_ids: list[str], justification: str
) -> tuple[list[StrategicScenario], list[ElementEcarte]]:
    """Keep only the named scenarios (§17 step 21), the rest écartés with the reason."""
    if not justification.strip():
        raise ValueError("Une justification non vide est obligatoire pour choisir un sous-ensemble (§8).")
    keep = set(keep_ids)
    kept = [s for s in scenarios if s.id in keep]
    discarded = [
        ElementEcarte(reference=s.id, libelle=s.resume, raison=REASON_HORS_SOUS_ENSEMBLE,
                      detail=justification.strip())
        for s in scenarios if s.id not in keep
    ]
    return renumber(kept), discarded


def _union(*lists: list[str]) -> list[str]:
    """Concatenate preserving order, without repeats."""
    seen: dict[str, None] = {}
    for item in [x for sub in lists for x in sub]:
        seen.setdefault(item, None)
    return list(seen)


# --- Étape 4: the quality checker ------------------------------------------

def run_quality_checks(
    w3_input: Workshop3Input,
    scenarios: list[StrategicScenario],
    gate: GateDecision,
) -> QualityReport:
    """Re-check the assembled result rather than trusting that the filters ran.

    Independent of the generation, like atelier 2's: a future change that loosens a
    filter still surfaces here instead of shipping silently.
    """
    checks: list[QualityCheck] = []
    couples = {c.id: c for c in w3_input.couples}
    known_be = {a.id for a in w3_input.biens_essentiels}
    haystack = context_haystack(w3_input)

    def check(controle: str, problems: list[str], *, statut: str = STATUT_ERREUR,
              ok_message: str = "") -> None:
        checks.append(QualityCheck(
            controle=controle,
            statut=statut if problems else STATUT_OK,
            message="; ".join(problems) if problems else ok_message,
        ))

    # 1. Traçabilité — every scenario resolves back to a retained atelier 2 couple.
    trace = [f"{s.id} référence le couple inconnu {s.couple_id}" for s in scenarios
             if s.couple_id not in couples]
    check("Traçabilité", trace, ok_message="Chaque scénario remonte à un couple SR/OV retenu.")

    # 2. Périmètre — the assets a scenario ends on belong to the study.
    scope = [
        f"{s.id} vise des biens essentiels hors atelier 1 : "
        f"{[b for b in s.biens_essentiels_ids if b not in known_be]}"
        for s in scenarios if any(b not in known_be for b in s.biens_essentiels_ids)
    ]
    check("Périmètre", scope, ok_message="Tous les scénarios restent dans le périmètre étudié.")

    # 3. Écosystème — the route names parties the dossier knows.
    ungrounded = []
    for scenario in scenarios:
        _, unknown = grounded_parties(scenario.parties_prenantes, haystack)
        if unknown:
            ungrounded.append(f"{scenario.id} cite {unknown}, absentes du contexte")
    check("Écosystème", ungrounded, statut=STATUT_AVERTISSEMENT,
          ok_message="Les parties prenantes citées viennent toutes du dossier.")

    # 4. Cotations reprises — nothing re-rated here (§17).
    carried = []
    for scenario in scenarios:
        couple = couples.get(scenario.couple_id)
        if couple is None:
            continue
        if (scenario.pertinence, scenario.vraisemblance_initiale) != (
            couple.pertinence, couple.vraisemblance_initiale
        ):
            carried.append(f"{scenario.id} ne reprend pas la cotation de l'atelier 2")
        expected, _ = gravite_of(w3_input, scenario.biens_essentiels_ids)
        if scenario.issu_de:
            continue  # a merged scenario carries the worst gravité of its members
        if scenario.gravite is not expected:
            carried.append(f"{scenario.id} ne reprend pas la gravité de l'atelier 1")
    check("Cotations reprises", carried,
          ok_message="Gravité, pertinence et vraisemblance viennent des ateliers 1 et 2.")

    # 5. Doublons — one scenario per couple.
    per_couple: dict[str, list[str]] = {}
    for scenario in scenarios:
        per_couple.setdefault(scenario.couple_id, []).append(scenario.id)
    duplicates = [f"{couple_id} décrit par {ids}" for couple_id, ids in per_couple.items()
                  if len(ids) > 1]
    check("Doublons", duplicates, ok_message="Un scénario au plus par couple SR/OV.")

    # 6. Couverture — a retained couple with no scenario is a gap in the study, but
    #    the auditor may have reduced the list on purpose at the gate.
    covered = {s.couple_id for s in scenarios}
    missing = sorted(c.id for c in w3_input.couples if c.id not in covered)
    check("Couverture", [f"couples sans scénario : {missing}"] if missing else [],
          statut=STATUT_AVERTISSEMENT,
          ok_message="Chaque couple retenu en atelier 2 a son scénario.")

    # 7. Point de comptage — the decision matches the list it is about (§17).
    gate_problems = []
    if gate.n != len(scenarios):
        gate_problems.append(
            f"la décision porte sur {gate.n} scénario(s), la liste en compte {len(scenarios)}")
    if gate.action and gate.options_offertes and gate.action not in gate.options_offertes:
        gate_problems.append(f"l'action « {gate.action} » n'était pas proposée")
    # An empty action means nobody has ruled yet — the state a fresh run is in until
    # the gate is put to the auditor, not a defect. Only the actions that change or
    # override the list owe a justification (§8).
    if gate.action in _ACTIONS_NEEDING_A_REASON and not gate.justification.strip():
        gate_problems.append("décision sans justification (§8)")
    check("Point de comptage", gate_problems,
          ok_message=f"{len(scenarios)} scénario(s), décision « {gate.action} ».")

    # 8. Liste non vide — atelier 4 fans out over this list.
    check("Scénarios", [] if scenarios else ["aucun scénario retenu : l'atelier 4 n'aurait rien à traiter"],
          ok_message=f"{len(scenarios)} scénario(s) transmis à l'atelier 4.")

    return QualityReport(checks=checks)
