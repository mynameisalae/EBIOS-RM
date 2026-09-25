"""Deterministic atelier 5 methodology (conception §19; méthode atelier 5).

Pure functions, no LLM and no I/O. What the method fixes lives here: the risk map
built from the ateliers before it, the acceptability scale, the treatment options, the
checks on every measure, the priority rule, the residual re-evaluation and its bounds,
and the quality checker.

Three rules of the method the code enforces rather than trusts:
  * a risk inherits its gravité from atelier 1 and its vraisemblance from atelier 4 —
    nothing is re-rated here, and the risk level is read off the matrix;
  * security measures lower the vraisemblance, never the gravité: if the feared event
    happens it hurts exactly as much, so the residual evaluation may only move the
    likelihood, and only downwards, and only when a measure is actually retained;
  * a risk the scale calls unacceptable cannot be kept as it is without the auditor
    writing why — the method's alternative is refusing the activity.
"""

from __future__ import annotations

from typing import Iterable

from ebios_rm.domain.enums import (
    Acceptabilite,
    AxeMesure,
    Gravite,
    NiveauRisque,
    OptionTraitement,
    Priorite,
    VraisemblanceInitiale,
)
from ebios_rm.domain.operational_scenario import OperationalScenario
from ebios_rm.domain.risk_scenario import (
    CadreSuivi,
    IndicateurSuivi,
    MesureSecurite,
    RiskScenario,
)
from ebios_rm.repositories.attack_repository import AttackMitigation
from ebios_rm.workshops.workshop1_cadrage.human_interface import is_meaningful
from ebios_rm.workshops.workshop2_sources_risque.assessment import normalise
from ebios_rm.workshops.workshop4_scenarios_operationnels.assessment import (
    read_likelihood,
    risk_level,
)
from ebios_rm.workshops.workshop5_traitement_risque.models import (
    COUTS,
    ORIGINE_ECOSYSTEME,
    ORIGINE_SOCLE,
    ORIGINE_VULNERABILITE,
    REASON_INDICATEUR_NON_MESURABLE,
    REASON_MESURE_AXE_INCONNU,
    REASON_MESURE_DOUBLON,
    REASON_MESURE_RISQUE_INCONNU,
    REASON_MESURE_SANS_LIEN,
    REASON_RESIDUEL_AGGRAVE,
    REASON_RESIDUEL_INCONNU,
    REASON_RESIDUEL_SANS_MESURE,
    STATUT_AVERTISSEMENT,
    STATUT_ERREUR,
    STATUT_OK,
    AtelierAlert,
    CouvertureER,
    ElementEcarte,
    IndicatorProposal,
    MeasureProposal,
    QualityCheck,
    QualityReport,
    ResidualProposal,
    RiskFormulationProposal,
    Workshop5Input,
    Workshop5Output,
)

# How much of the likelihood one measure may be credited with taking away. Two levels
# is already a strong claim; more is a plan promising what no single measure delivers.
MAX_EFFET_MESURE = 2

_VALEURS_INDICATEUR = ("cout", "duree", "nombre", "taux")

_GRAVITE_RANK = {Gravite.MINIMALE: 1, Gravite.SIGNIFICATIVE: 2, Gravite.GRAVE: 3, Gravite.CRITIQUE: 4}
_NIVEAU_RANK = {NiveauRisque.FAIBLE: 1, NiveauRisque.MOYEN: 2, NiveauRisque.ELEVE: 3,
                NiveauRisque.CRITIQUE: 4}
_AXE_ORDER = {AxeMesure.GOUVERNANCE: 0, AxeMesure.PROTECTION: 1, AxeMesure.DEFENSE: 2,
              AxeMesure.RESILIENCE: 3}


def _rank(value: VraisemblanceInitiale) -> int:
    return int(value.value[1])


def _lower(value: VraisemblanceInitiale, levels: int) -> VraisemblanceInitiale:
    return VraisemblanceInitiale(f"V{max(1, _rank(value) - max(0, levels))}")


# --- Étape 0: the approved atelier 4 output must hold up ---------------------

def validate_atelier4(modes: list[OperationalScenario], strategic_ids: Iterable[str]) -> list[AtelierAlert]:
    """Check that atelier 4's result can be treated (§2).

    Alerts, never repairs: a plan built on a mode whose likelihood was never settled,
    or on a strategic scenario with no retained mode, would price measures against a
    risk level nobody computed.
    """
    alerts: list[AtelierAlert] = []
    if not modes:
        alerts.append(AtelierAlert(
            reference="atelier4",
            probleme="Aucun mode opératoire : l'atelier 5 n'a aucun risque à traiter."))

    known = set(strategic_ids)
    by_scenario: dict[str, list[OperationalScenario]] = {}
    for mode in modes:
        by_scenario.setdefault(mode.scenario_strategique_id, []).append(mode)
        if mode.scenario_strategique_id not in known:
            alerts.append(AtelierAlert(
                reference=mode.id,
                probleme=f"Mode opératoire rattaché à un scénario stratégique inconnu : "
                         f"'{mode.scenario_strategique_id}'."))
    for scenario_id, group in by_scenario.items():
        retenus = [m for m in group if m.retenu]
        if len(retenus) != 1:
            alerts.append(AtelierAlert(
                reference=scenario_id,
                probleme=f"{len(retenus)} mode(s) retenu(s) au lieu d'un : le risque de ce scénario "
                         "n'a pas de vraisemblance déterminée."))
        elif retenus[0].revised_likelihood is None:
            alerts.append(AtelierAlert(
                reference=retenus[0].id,
                probleme="Le mode retenu n'a pas de vraisemblance révisée."))
    return alerts


# --- Activité 5-1: the risks, their level, their acceptability ---------------

_ACCEPTABILITE = {
    NiveauRisque.FAIBLE: Acceptabilite.ACCEPTABLE,
    NiveauRisque.MOYEN: Acceptabilite.TOLERABLE,
    NiveauRisque.ELEVE: Acceptabilite.INACCEPTABLE,
    NiveauRisque.CRITIQUE: Acceptabilite.INACCEPTABLE,
}


def acceptabilite_of(niveau: NiveauRisque | None) -> Acceptabilite | None:
    """The acceptability the scale gives that risk level (atelier 5-2).

    ponytail: the scale of the method's own example — acceptable, tolérable sous
    contrôle, inacceptable. It is the calibration knob: an organisation that sets its
    threshold lower changes this table, and nothing else.
    """
    return _ACCEPTABILITE.get(niveau) if niveau is not None else None


def build_risques(w5_input: Workshop5Input) -> list[RiskScenario]:
    """One risk per strategic scenario, worst first (atelier 5-1).

    The gravité comes down from atelier 1 through atelier 3, the vraisemblance up from
    atelier 4 — the likelihood of the mode it retained, which is the most likely way in.
    The alternative modes travel with the risk: they are other ways to the same
    consequence, and the plan has to cover them too.
    """
    risques: list[RiskScenario] = []
    by_scenario: dict[str, list[OperationalScenario]] = {}
    for mode in w5_input.modes_operatoires:
        by_scenario.setdefault(mode.scenario_strategique_id, []).append(mode)

    for scenario in w5_input.scenarios_strategiques:
        modes = by_scenario.get(scenario.id, [])
        driving = next((m for m in modes if m.retenu), None)
        if driving is None or driving.revised_likelihood is None:
            continue
        niveau = risk_level(driving.gravite, driving.revised_likelihood)
        risques.append(RiskScenario(
            id="",
            scenario_strategique_id=scenario.id,
            mode_retenu_id=driving.id,
            modes_alternatifs_ids=[m.id for m in modes if m.id != driving.id],
            source_risque_id=driving.source_risque_id,
            objectif_vise_id=driving.objectif_vise_id,
            biens_essentiels_ids=list(driving.biens_essentiels_ids),
            evenements_redoutes_ids=list(driving.evenements_redoutes_ids),
            gravite=driving.gravite,
            vraisemblance=driving.revised_likelihood,
            niveau_risque=niveau,
            acceptabilite=acceptabilite_of(niveau),
        ))
    return number_risques(risques)


def number_risques(risques: list[RiskScenario]) -> list[RiskScenario]:
    """R1.. worst first: the risk map is read from the top, and so is the plan."""
    ordered = sorted(
        risques,
        key=lambda r: (-_NIVEAU_RANK.get(r.niveau_risque, 0), -_GRAVITE_RANK[r.gravite],
                       -_rank(r.vraisemblance), r.scenario_strategique_id),
    )
    return [r.model_copy(update={"id": f"R{n}"}) for n, r in enumerate(ordered, 1)]


def apply_formulations(
    risques: list[RiskScenario], proposals: list[RiskFormulationProposal]
) -> list[RiskScenario]:
    """Take the business wording the agent proposed for each risk (atelier 5-1).

    Wording only: the ids, the levels and the links are the code's. A risk the decision
    maker cannot read is a risk nobody rules on, which is why the method insists the
    formulation is in business terms.
    """
    proposed = {p.risque_id.strip().upper(): p.libelle.strip()
                for p in proposals if p.libelle.strip()}
    return [
        r.model_copy(update={"libelle": proposed[r.id]}) if r.id in proposed else r
        for r in risques
    ]


def couverture_er(w5_input: Workshop5Input, risques: list[RiskScenario]) -> list[CouvertureER]:
    """Which feared events of atelier 1 ended up in a risk, and which did not (atelier 5-1).

    The method's completeness pass: a serious or critical feared event covered by no
    risk scenario means ateliers 2 to 4 must be iterated — it is not a detail to note
    at the end of the report.
    """
    return [
        CouvertureER(
            evenement_redoute_id=event.id,
            description=event.description,
            gravite=event.gravite.value,
            risques_ids=[r.id for r in risques if event.id in r.evenements_redoutes_ids],
        )
        for event in w5_input.evenements_redoutes
    ]


def er_graves_non_couverts(couverture: list[CouvertureER]) -> list[CouvertureER]:
    return [c for c in couverture
            if not c.couvert and c.gravite in {Gravite.GRAVE.value, Gravite.CRITIQUE.value}]


# --- Activité 5-2: the treatment strategy -----------------------------------

def option_proposee(risque: RiskScenario) -> OptionTraitement:
    """What the scale points at — a proposal, never a decision (§2).

    Unacceptable and tolerable risks point at reduction; an acceptable one at keeping
    it as it is. Sharing and avoiding are business calls the auditor makes, so they are
    never proposed here.
    """
    if risque.acceptabilite is Acceptabilite.ACCEPTABLE:
        return OptionTraitement.MAINTIEN
    return OptionTraitement.REDUCTION


def set_traitement(
    output: Workshop5Output, risque_id: str, option: OptionTraitement, justification: str
) -> Workshop5Output:
    """The auditor's decision on one risk, with its mandatory reason (§2, §8)."""
    if not is_meaningful(justification):
        raise ValueError("Une justification non vide est obligatoire pour décider du traitement (§8).")
    if not any(r.id == risque_id for r in output.risques):
        raise ValueError(f"Risque inconnu : {risque_id}")
    return output.model_copy(update={"risques": [
        r.model_copy(update={"option_traitement": option,
                             "justification_traitement": justification.strip()})
        if r.id == risque_id else r
        for r in output.risques
    ]})


# --- Activité 5-3: the measures and the plan ---------------------------------

def read_axe(raw: str) -> AxeMesure | None:
    text = normalise(raw).replace(" ", "_")
    for axe in AxeMesure:
        if text.startswith(axe.value) or axe.value in text:
            return axe
    return None


def build_mesures(
    proposals: list[MeasureProposal],
    output: Workshop5Output,
    w5_input: Workshop5Input,
    mitigations: dict[str, list[AttackMitigation]],
    *,
    start: int = 1,
) -> tuple[list[MesureSecurite], list[ElementEcarte]]:
    """Check the proposed measures and file them in the plan (atelier 5-3).

    Four rules, code-enforced: one of the four axes of the plan; something real to act
    on — a risk of this study, a step of a mode opératoire, or a baseline gap of
    atelier 1; only ATT&CK mitigation ids that came out of the base for the techniques
    actually cited; and no measure said twice.
    """
    known_risques = {r.id for r in output.risques}
    known_modes = {m.id for m in w5_input.modes_operatoires}
    known_gaps = {g.gap_id for g in w5_input.baseline_gaps}
    known_mitigations = {m.mitigation_id for found in mitigations.values() for m in found}
    seen: dict[str, str] = {}

    kept: list[MesureSecurite] = []
    ecartes: list[ElementEcarte] = []

    def reject(proposal: MeasureProposal, raison: str, detail: str = "") -> None:
        ecartes.append(ElementEcarte(
            type="mesure", reference=proposal.libelle.strip() or "(sans libellé)",
            libelle=proposal.libelle.strip(), raison=raison,
            detail=detail or proposal.justification.strip()))

    for proposal in proposals:
        libelle = proposal.libelle.strip()
        axe = read_axe(proposal.axe)
        if not libelle or axe is None:
            reject(proposal, REASON_MESURE_AXE_INCONNU if libelle else REASON_MESURE_SANS_LIEN,
                   f"Axe proposé : « {proposal.axe} »")
            continue

        risques_ids = [r.strip().upper() for r in proposal.risques_ids if r.strip().upper() in known_risques]
        unknown_risques = [r.strip() for r in proposal.risques_ids
                           if r.strip().upper() not in known_risques and r.strip()]
        modes_ids = [m.strip().upper() for m in proposal.modes_ids if m.strip().upper() in known_modes]
        gap_ids = [g.strip() for g in proposal.gap_ids if g.strip() in known_gaps]
        if not risques_ids and not modes_ids and not gap_ids:
            reject(proposal, REASON_MESURE_RISQUE_INCONNU if unknown_risques else REASON_MESURE_SANS_LIEN,
                   f"Références proposées : risques {proposal.risques_ids}, modes {proposal.modes_ids}, "
                   f"écarts {proposal.gap_ids}")
            continue

        key = normalise(libelle)
        if key in seen:
            reject(proposal, REASON_MESURE_DOUBLON, f"Déjà retenue sous « {seen[key]} »")
            continue
        seen[key] = libelle

        origine = proposal.origine.strip()
        if origine not in {ORIGINE_SOCLE, ORIGINE_ECOSYSTEME, ORIGINE_VULNERABILITE}:
            origine = ORIGINE_SOCLE if gap_ids and not modes_ids else (
                ORIGINE_VULNERABILITE if modes_ids else ORIGINE_ECOSYSTEME)

        kept.append(MesureSecurite(
            id="",
            axe=axe,
            thematique=proposal.thematique.strip(),
            libelle=libelle,
            description=proposal.description.strip(),
            risques_ids=list(dict.fromkeys(risques_ids)),
            modes_ids=list(dict.fromkeys(modes_ids)),
            etapes_visees=[e.strip() for e in proposal.etapes_visees if e.strip()],
            gap_ids=list(dict.fromkeys(gap_ids)),
            # An id the base never returned for the techniques cited is dropped, not kept
            # on trust — same rule as atelier 4's technique ids (§19 fiche de test).
            mitigation_ids_attck=[m.strip().upper() for m in proposal.mitigation_ids_attck
                                  if m.strip().upper() in known_mitigations],
            origine=origine,
            freins=proposal.freins.strip(),
            cout_complexite=proposal.cout_complexite.strip() if proposal.cout_complexite.strip() in COUTS else "",
            charge_estimee=proposal.charge_estimee.strip(),
            echeance=proposal.echeance.strip(),
            effet_vraisemblance=max(0, min(MAX_EFFET_MESURE, proposal.effet_vraisemblance)),
            justification=proposal.justification.strip(),
        ))
    return number_mesures(kept, output.risques, start=start), ecartes


def priorite_of(mesure: MesureSecurite, risques: list[RiskScenario]) -> Priorite:
    """Priority of a measure: the risk level it serves first, its cost second (atelier 5-3).

    The method's order — « on priorise les mesures d'abord par rapport au niveau de
    risque et ensuite en prenant en compte leur complexité et délais ». A measure that
    serves no risk directly (a baseline or ecosystem measure) is ranked on the level of
    the risks its modes belong to, and P3 when it belongs to none.
    """
    served = [r for r in risques if r.id in mesure.risques_ids
              or any(m in r.modes_alternatifs_ids + [r.mode_retenu_id] for m in mesure.modes_ids)]
    worst = max((_NIVEAU_RANK.get(r.niveau_risque, 0) for r in served), default=0)
    cheap = mesure.cout_complexite in {"", "+", "++"}
    if worst >= 3:                       # élevé or critique — the method's short term
        return Priorite.P1 if cheap else Priorite.P2
    if worst == 2:                       # moyen — tolerable under control
        return Priorite.P2 if cheap else Priorite.P3
    return Priorite.P3


def number_mesures(
    mesures: list[MesureSecurite], risques: list[RiskScenario], *, start: int = 1
) -> list[MesureSecurite]:
    """M-01.. grouped by axis in the plan's order, priority computed for each."""
    ordered = sorted(mesures, key=lambda m: (_AXE_ORDER[m.axe], m.libelle))
    return [
        m.model_copy(update={"id": f"M-{n:02d}", "priorite": priorite_of(m, risques)})
        for n, m in enumerate(ordered, start)
    ]


def link_mesures(output: Workshop5Output) -> Workshop5Output:
    """Write each risk's measure list from the measures themselves — one source of truth."""
    by_risque: dict[str, list[str]] = {}
    for mesure in output.mesures:
        for risque_id in mesure.risques_ids:
            by_risque.setdefault(risque_id, []).append(mesure.id)
        for risque in output.risques:
            if mesure.id in by_risque.get(risque.id, []):
                continue
            if any(m == risque.mode_retenu_id or m in risque.modes_alternatifs_ids
                   for m in mesure.modes_ids):
                by_risque.setdefault(risque.id, []).append(mesure.id)
    return output.model_copy(update={"risques": [
        r.model_copy(update={"mesures_ids": list(dict.fromkeys(by_risque.get(r.id, [])))})
        for r in output.risques
    ]})


def remove_mesures(
    output: Workshop5Output, ids: Iterable[str], raison: str, detail: str = ""
) -> Workshop5Output:
    """Drop measures the auditor does not want, each leaving its reason (§16, §19)."""
    chosen = set(ids)
    dropped = [m for m in output.mesures if m.id in chosen]
    return link_mesures(output.model_copy(update={
        "mesures": [m for m in output.mesures if m.id not in chosen],
        "elements_ecartes": [
            *output.elements_ecartes,
            *(ElementEcarte(type="mesure", reference=m.id, libelle=m.libelle, raison=raison,
                            detail=detail) for m in dropped),
        ],
    }))


# --- Activité 5-4: the residual risks ----------------------------------------

def apply_residuel(
    output: Workshop5Output, proposals: list[ResidualProposal]
) -> tuple[Workshop5Output, list[ElementEcarte]]:
    """Re-evaluate each risk with the plan counted (atelier 5-4).

    Bounds the method imposes, all checked here: the gravité never moves — a feared
    event that happens hurts as much as before; the likelihood only falls, never rises;
    it falls only when measures are actually retained on that risk; and it cannot fall
    further than the effect those measures claim. The reason is mandatory, and names
    which measure breaks which step.
    """
    by_id = {r.id: r for r in output.risques}
    effets = {m.id: m.effet_vraisemblance for m in output.mesures}
    updated: dict[str, RiskScenario] = {}
    ecartes: list[ElementEcarte] = []

    for proposal in proposals:
        risque_id = proposal.risque_id.strip().upper()
        risque = by_id.get(risque_id)
        if risque is None:
            ecartes.append(ElementEcarte(
                type="residuel", reference=proposal.risque_id.strip() or "(sans risque)",
                libelle=proposal.motif.strip(), raison=REASON_RESIDUEL_INCONNU))
            continue
        proposed = read_likelihood(proposal.vraisemblance_residuelle)
        if proposed is None or not is_meaningful(proposal.motif):
            ecartes.append(ElementEcarte(
                type="residuel", reference=risque_id, libelle=proposal.motif.strip(),
                raison=REASON_RESIDUEL_SANS_MESURE if proposed else REASON_RESIDUEL_AGGRAVE,
                detail=f"Vraisemblance proposée : « {proposal.vraisemblance_residuelle} »"))
            continue
        if _rank(proposed) > _rank(risque.vraisemblance):
            ecartes.append(ElementEcarte(
                type="residuel", reference=risque_id, libelle=proposal.motif.strip(),
                raison=REASON_RESIDUEL_AGGRAVE,
                detail=f"{proposed.value} proposé contre {risque.vraisemblance.value} en initial"))
            continue
        credit = sum(effets.get(m, 0) for m in risque.mesures_ids)
        if _rank(proposed) < _rank(risque.vraisemblance) and credit == 0:
            ecartes.append(ElementEcarte(
                type="residuel", reference=risque_id, libelle=proposal.motif.strip(),
                raison=REASON_RESIDUEL_SANS_MESURE,
                detail="Aucune mesure retenue sur ce risque ne réduit la vraisemblance"))
            continue
        floor = _lower(risque.vraisemblance, credit)
        retained = proposed if _rank(proposed) >= _rank(floor) else floor
        niveau = risk_level(risque.gravite, retained)
        motif = proposal.motif.strip()
        if retained is not proposed:
            motif += (f" [borné à {retained.value} : les mesures retenues revendiquent "
                      f"{credit} niveau(x) de réduction]")
        updated[risque_id] = risque.model_copy(update={
            "vraisemblance_residuelle": retained,
            "motif_residuel": motif,
            "niveau_risque_residuel": niveau,
            "acceptabilite_residuelle": acceptabilite_of(niveau),
        })

    return output.model_copy(update={
        "risques": [updated.get(r.id, r) for r in output.risques],
        "elements_ecartes": [*output.elements_ecartes, *ecartes],
    }), ecartes


def keep_initial_residuel(output: Workshop5Output) -> Workshop5Output:
    """A risk nobody treats keeps its level: the residual equals the initial (atelier 5-4)."""
    return output.model_copy(update={"risques": [
        r if r.vraisemblance_residuelle is not None else r.model_copy(update={
            "vraisemblance_residuelle": r.vraisemblance,
            "niveau_risque_residuel": r.niveau_risque,
            "acceptabilite_residuelle": r.acceptabilite,
            "motif_residuel": r.motif_residuel or "Aucune mesure retenue : le risque reste au niveau initial.",
        })
        for r in output.risques
    ]})


def accept_residuel(output: Workshop5Output, risque_ids: Iterable[str], accepte_par: str) -> Workshop5Output:
    """Record the formal acceptance of residual risks by the decision-maker (atelier 5-4)."""
    if not is_meaningful(accepte_par):
        raise ValueError("L'acceptation d'un risque résiduel doit nommer qui l'accepte (§8).")
    chosen = set(risque_ids)
    return output.model_copy(update={"risques": [
        r.model_copy(update={"accepte_par": accepte_par.strip()}) if r.id in chosen else r
        for r in output.risques
    ]})


# --- Activité 5-5: the monitoring framework ----------------------------------

def build_cadre(
    proposals: list[IndicatorProposal], output: Workshop5Output, *,
    comite: str = "", cycles: str = "", prochaine_revue: str = "",
) -> tuple[CadreSuivi, list[ElementEcarte]]:
    """Keep the indicators that measure something (atelier 5-5).

    The method's four kinds of value: a cost, a duration, a count or a rate. An
    indicator without one of those cannot be followed, so it is set aside with its reason.
    """
    known = {m.id for m in output.mesures}
    indicateurs: list[IndicateurSuivi] = []
    ecartes: list[ElementEcarte] = []
    for n, proposal in enumerate(proposals, 1):
        valeur = normalise(proposal.type_valeur)
        libelle = proposal.libelle.strip()
        if not libelle or valeur not in _VALEURS_INDICATEUR or not proposal.cible.strip():
            ecartes.append(ElementEcarte(
                type="indicateur", reference=libelle or "(sans libellé)", libelle=libelle,
                raison=REASON_INDICATEUR_NON_MESURABLE,
                detail=f"type_valeur « {proposal.type_valeur} », cible « {proposal.cible} »"))
            continue
        indicateurs.append(IndicateurSuivi(
            id=f"IND-{len(indicateurs) + 1:02d}",
            libelle=libelle,
            type_valeur=valeur,
            cible=proposal.cible.strip(),
            frequence=proposal.frequence.strip(),
            mesures_ids=[m.strip().upper() for m in proposal.mesures_ids
                         if m.strip().upper() in known],
        ))
    return CadreSuivi(indicateurs=indicateurs, comite=comite.strip(), cycles=cycles.strip(),
                      prochaine_revue=prochaine_revue.strip()), ecartes


# --- The quality checker -----------------------------------------------------

def run_quality_checks(w5_input: Workshop5Input, output: Workshop5Output) -> QualityReport:
    """Re-check the assembled plan on its content, whatever produced or edited it."""
    checks: list[QualityCheck] = []
    risques = output.risques
    mesures = output.mesures

    def check(controle: str, problems: list[str], *, statut: str = STATUT_ERREUR,
              ok_message: str = "") -> None:
        checks.append(QualityCheck(controle=controle, statut=statut if problems else STATUT_OK,
                                   message="; ".join(problems) if problems else ok_message))

    # 1. Couverture des scénarios — one risk per strategic scenario atelier 4 settled.
    treated = {r.scenario_strategique_id for r in risques}
    expected = {m.scenario_strategique_id for m in w5_input.modes_operatoires if m.retenu}
    missing = sorted(expected - treated)
    unwritten = [r.id for r in risques if not r.libelle.strip()]
    check("Couverture des scénarios",
          ([f"scénarios stratégiques sans risque : {missing}"] if missing else [])
          + ([f"risques sans formulation métier : {unwritten}"] if unwritten else []),
          ok_message=f"{len(risques)} risque(s) formulés, un par scénario stratégique retenu.")

    # 2. Couverture des événements redoutés — the method's completeness pass (5-1).
    serious = er_graves_non_couverts(output.couverture_er)
    light = [c.evenement_redoute_id for c in output.couverture_er if not c.couvert and c not in serious]
    check("Couverture des événements redoutés",
          [f"événements redoutés graves ou critiques couverts par aucun risque : "
           f"{[c.evenement_redoute_id for c in serious]} — itérer les ateliers 2 à 4"] if serious else [],
          ok_message="Chaque événement redouté grave ou critique est porté par un risque.")
    check("Événements redoutés de moindre gravité non couverts",
          [f"{light}"] if light else [], statut=STATUT_AVERTISSEMENT,
          ok_message="Tous les événements redoutés sont couverts.")

    # 3. Stratégie de traitement — decided, justified, and coherent with the scale (5-2).
    strategy = []
    for risque in risques:
        if risque.option_traitement is None:
            strategy.append(f"{risque.id} sans option de traitement")
            continue
        if not is_meaningful(risque.justification_traitement):
            strategy.append(f"{risque.id} sans justification de traitement")
        if (risque.acceptabilite is Acceptabilite.INACCEPTABLE
                and risque.option_traitement is OptionTraitement.MAINTIEN):
            strategy.append(f"{risque.id} inacceptable et pourtant maintenu en l'état")
    check("Stratégie de traitement", strategy,
          ok_message="Chaque risque porte une option de traitement justifiée.")

    # 4. Plan de traitement — a reduced risk carries measures, every measure acts on something.
    plan = []
    for risque in risques:
        if risque.option_traitement is OptionTraitement.REDUCTION and not risque.mesures_ids:
            plan.append(f"{risque.id} à réduire sans aucune mesure")
    known_modes = {m.id for m in w5_input.modes_operatoires}
    known_gaps = {g.gap_id for g in w5_input.baseline_gaps}
    known_risques = {r.id for r in risques}
    for mesure in mesures:
        if not (set(mesure.risques_ids) & known_risques or set(mesure.modes_ids) & known_modes
                or set(mesure.gap_ids) & known_gaps):
            plan.append(f"{mesure.id} ne traite ni risque, ni mode opératoire, ni écart du socle")
        if mesure.priorite is not priorite_of(mesure, risques):
            plan.append(f"{mesure.id} : priorité incohérente avec le niveau de risque servi")
    check("Plan de traitement", plan,
          ok_message=f"{len(mesures)} mesure(s) rattachées à un risque, un mode ou un écart.")

    # 5. Risques résiduels — evaluated, only downwards, gravité untouched, accepted (5-4).
    residual = []
    for risque in risques:
        if risque.vraisemblance_residuelle is None:
            residual.append(f"{risque.id} sans évaluation résiduelle")
            continue
        if _rank(risque.vraisemblance_residuelle) > _rank(risque.vraisemblance):
            residual.append(f"{risque.id} : vraisemblance résiduelle supérieure à l'initiale")
        if risque.niveau_risque_residuel is not risk_level(risque.gravite, risque.vraisemblance_residuelle):
            residual.append(f"{risque.id} : niveau résiduel incohérent avec {risque.gravite.value}")
        if risque.vraisemblance_residuelle is not risque.vraisemblance and not is_meaningful(risque.motif_residuel):
            residual.append(f"{risque.id} : réduction sans motif")
        if not risque.accepte_par.strip():
            residual.append(f"{risque.id} : risque résiduel non accepté formellement")
    check("Risques résiduels", residual,
          ok_message="Risques résiduels évalués, motivés et acceptés formellement.")

    # 6. Cadre de suivi — the study does not end at the plan (5-5).
    cadre = output.cadre_suivi
    follow = []
    if cadre is None or not cadre.indicateurs:
        follow.append("aucun indicateur de suivi")
    if cadre is None or not cadre.comite.strip():
        follow.append("aucune instance de suivi ni cadence")
    check("Cadre de suivi des risques", follow,
          ok_message=f"{len(cadre.indicateurs) if cadre else 0} indicateur(s) et une instance de suivi.")

    # 7. Écarts du socle — the plan is where atelier 1's gaps get corrected (5-3).
    covered_gaps = {g for m in mesures for g in m.gap_ids}
    idle_gaps = [g.gap_id for g in w5_input.baseline_gaps if g.gap_id not in covered_gaps]
    check("Écarts du socle traités", [f"écarts sans mesure : {idle_gaps}"] if idle_gaps else [],
          statut=STATUT_AVERTISSEMENT,
          ok_message="Chaque écart du socle est porté par une mesure du plan.")

    # 8. Modes alternatifs — treating only the easiest route leaves the others open.
    #    Not in the method: our own check, because atelier 4 now develops every route.
    uncovered_modes = []
    for risque in risques:
        touched = {m for mesure in mesures for m in mesure.modes_ids}
        left = [m for m in risque.modes_alternatifs_ids if m not in touched]
        if left and risque.option_traitement is OptionTraitement.REDUCTION:
            uncovered_modes.append(f"{risque.id} : modes alternatifs non traités {left}")
    check("Modes alternatifs traités", uncovered_modes, statut=STATUT_AVERTISSEMENT,
          ok_message="Les modes alternatifs de chaque risque réduit sont couverts par une mesure.")

    # 9. Répartition du plan — informational, as the plan is read axis by axis.
    per_axe = {axe.value: sum(1 for m in mesures if m.axe is axe) for axe in AxeMesure}
    check("Répartition par axe", [], statut=STATUT_OK,
          ok_message=", ".join(f"{axe} : {count}" for axe, count in per_axe.items()))

    return QualityReport(checks=checks)
