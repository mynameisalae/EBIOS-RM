"""Deterministic atelier 5 methodology (conception §19).

Pure functions, no LLM and no I/O. Everything that decides rather than
proposes is here: validating the atelier 4 output holds up, checking each
proposed measure's mitigation ids against the real ATT&CK relation, its
scenario references, its priority against the fixed vocabulary, and the
quality checker.

Priority is the one field this module does *not* recompute from a formula —
unlike atelier 4's risk_level (gravité × vraisemblance, a fixed matrix), the
fiche de test only pins priorite's vocabulary, not a deterministic value to
check it against. The auditor arbitrates the actual judgment; code enforces
that the judgment is expressed in the fixed vocabulary and grounded in real
mitigations, nothing more.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from ebios_rm.domain.enums import PrioriteMesure
from ebios_rm.domain.mesure import Mesure
from ebios_rm.domain.operational_scenario import Anomaly, OperationalScenario
from ebios_rm.repositories.attack_repository import MitigationCatalogue
from ebios_rm.workshops.common import AtelierAlert
from ebios_rm.workshops.workshop1_cadrage.human_interface import is_meaningful
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap
from ebios_rm.workshops.workshop2_sources_risque.models import (
    STATUT_ERREUR,
    STATUT_OK,
    QualityCheck,
    QualityReport,
)
from ebios_rm.workshops.workshop5_traitement_risque.models import (
    REASON_MITIGATION_INCONNUE,
    REASON_PROPOSITION_VIDE,
    REASON_SCENARIO_INCONNU,
    ElementEcarte,
    MesureProposal,
    Workshop5Input,
)

# --- Étape 0: the finalized atelier 4 output must hold up -------------------


def validate_atelier4(scenarios: list[OperationalScenario], baseline_gaps: list[BaselineGap]) -> list[AtelierAlert]:
    """Check the finalized scenarios reference gaps that were actually transmitted (§2).

    Produces alerts, never repairs: a scenario citing a gap id atelier 1 never
    produced is fixed upstream, not silently dropped here.
    """
    alerts: list[AtelierAlert] = []
    if not scenarios:
        alerts.append(AtelierAlert(
            reference="atelier4",
            probleme="Aucun scénario opérationnel : l'atelier 5 n'a rien à traiter."))

    known_gaps = {g.gap_id for g in baseline_gaps}
    seen: set[str] = set()
    for scenario in scenarios:
        if scenario.id in seen:
            alerts.append(AtelierAlert(reference=scenario.id, probleme="Identifiant de scénario en double."))
        seen.add(scenario.id)
        cited = {g.gap_id for g in scenario.baseline_gaps_considered}
        unknown = cited - known_gaps
        if unknown:
            alerts.append(AtelierAlert(
                reference=scenario.id,
                probleme=f"Écart(s) du socle cité(s) mais non transmis à l'atelier 5 : {sorted(unknown)}.",
                bloquant=False,
            ))
    return alerts


# --- Value readers: lenient on form, strict on meaning ----------------------

def _fold(text: str) -> str:
    """Accents stripped, letters only, lowercased — the one normalisation used
    on both sides of the comparison below, so « Élevée » folds the same way
    whether it comes from the fixed vocabulary or from the model's own text."""
    plain = unicodedata.normalize("NFKD", text)
    return re.sub(r"[^a-z]", "", "".join(c for c in plain if not unicodedata.combining(c)).lower())


_PRIORITE_BY_FOLD = {_fold(p.value): p for p in PrioriteMesure}


def read_priorite(raw: str | None) -> PrioriteMesure | None:
    """« Élevée » and « elevee (priorité haute) » both read as ÉLEVÉE; anything
    that does not fold onto exactly one of the three fixed values does not."""
    text = _fold(raw or "")
    for key, value in _PRIORITE_BY_FOLD.items():
        if key and key in text:
            return value
    return None


# --- One proposed measure -> a checked Mesure, or set aside -----------------


def build_mesure(
    n: int,
    proposal: MesureProposal,
    w5_input: Workshop5Input,
    mitigations: MitigationCatalogue,
) -> tuple[Mesure | None, list[ElementEcarte]]:
    """Check one proposed measure (§19). Returns the validated Mesure, kept with
    whatever anomalies were found so the auditor sees them (same discipline as
    atelier 4's build_analysis: a problem is flagged on the kept object, not
    silently repaired) — or None only when the proposal is genuinely empty,
    with the whole thing recorded in ``ecartes`` instead of a hollow entry
    nobody could act on.
    """
    anomalies: list[Anomaly] = []
    ecartes: list[ElementEcarte] = []

    def flag(code: str, message: str, *, bloquante: bool = True) -> None:
        anomalies.append(Anomaly(code=code, message=message, bloquante=bloquante))

    known_scenarios = {s.id for s in w5_input.scenarios}
    scenarios_associes = []
    for sid in proposal.scenarios_associes:
        if sid in known_scenarios:
            scenarios_associes.append(sid)
        else:
            ecartes.append(ElementEcarte(
                type="reference_scenario", reference=sid, libelle=proposal.description[:80],
                raison=REASON_SCENARIO_INCONNU))
            flag("scenario_inconnu", f"« {sid} » n'est pas un scénario opérationnel transmis — retiré.",
                 bloquante=False)

    mitigation_ids = []
    for mid in proposal.mitigation_ids_attck:
        if mid in mitigations.all_ids:
            mitigation_ids.append(mid)
        else:
            ecartes.append(ElementEcarte(
                type="mitigation", reference=mid, libelle=proposal.description[:80],
                raison=REASON_MITIGATION_INCONNUE))
            flag("mitigation_inconnue",
                 f"« {mid} » n'est pas une mitigation active retournée par l'outil ATT&CK — retirée.")

    description = proposal.description.strip()
    has_description = is_meaningful(description)

    if not has_description and not scenarios_associes and not mitigation_ids:
        # Nothing at all survives: no real content, no real anchor. Keeping
        # this as a Mesure would give the auditor an empty row to act on.
        ecartes.append(ElementEcarte(
            type="mesure", reference=f"proposition {n}", libelle=proposal.description[:80],
            raison=REASON_PROPOSITION_VIDE))
        return None, ecartes

    priorite = read_priorite(proposal.priorite)
    if priorite is None:
        flag("priorite_invalide",
             f"« {proposal.priorite} » n'est pas une valeur de l'échelle Faible / Moyenne / Élevée.")

    missing = [label for label, value in
               (("coût", proposal.cout), ("efficacité", proposal.efficacite), ("délai", proposal.delai))
               if not is_meaningful(value)]
    if missing:
        flag("critere_manquant", f"Critère(s) manquant(s) : {', '.join(missing)}.")

    if not has_description:
        flag("description_absente", "Aucune description de la mesure.")

    if not scenarios_associes and not mitigation_ids:
        flag("mesure_sans_ancrage",
             "Ni scénario ni mitigation associés : impossible de savoir ce que la mesure traite.",
             bloquante=False)

    mesure = Mesure(
        id=f"MT-{n:02d}",
        description=description,
        scenarios_associes=scenarios_associes,
        mitigation_ids_attck=mitigation_ids,
        cout=proposal.cout.strip(),
        efficacite=proposal.efficacite.strip(),
        delai=proposal.delai.strip(),
        priorite=priorite,
        anomalies=anomalies,
    )
    return mesure, ecartes


# --- Étape finale: the quality checker ---------------------------------------


def run_quality_checks(
    w5_input: Workshop5Input, mesures: list[Mesure], mitigations: MitigationCatalogue
) -> QualityReport:
    """Re-check the assembled result on its content (§19), independently of
    what build_mesure already filtered — including anything edited by hand since."""
    checks: list[QualityCheck] = []

    def check(controle: str, problems: list[str], *, ok_message: str = "") -> None:
        checks.append(QualityCheck(
            controle=controle, statut=STATUT_ERREUR if problems else STATUT_OK,
            message="; ".join(problems) if problems else ok_message))

    # 1. Couverture — every scenario the input carried has at least one measure.
    covered = {sid for m in mesures for sid in m.scenarios_associes}
    uncovered = [s.id for s in w5_input.scenarios if s.id not in covered]
    check("Couverture", [f"scénario(s) sans mesure associée : {uncovered}"] if uncovered else [],
          ok_message=f"{len(mesures)} mesure(s), chaque scénario couvert par au moins une.")

    # 2. Mitigations — every id in the output is one the base's own relation returned.
    invalid = [f"{m.id} : {mid}" for m in mesures for mid in m.mitigation_ids_attck
               if mid not in mitigations.all_ids]
    check("Mitigations ATT&CK", invalid, ok_message="Tous les identifiants existent dans le catalogue de mitigations.")

    # 3. Références — every scenario cited exists among what was transmitted.
    known_scenarios = {s.id for s in w5_input.scenarios}
    dangling = [f"{m.id} : {sid}" for m in mesures for sid in m.scenarios_associes if sid not in known_scenarios]
    check("Références aux scénarios", dangling, ok_message="Toutes les références pointent vers un scénario transmis.")

    # 4. Critères — nothing left blank, and a priority the auditor can read.
    incomplete = [m.id for m in mesures if not (m.cout.strip() and m.efficacite.strip() and m.delai.strip())]
    check("Critères d'arbitrage", [f"mesure(s) incomplète(s) : {incomplete}"] if incomplete else [],
          ok_message="Coût, efficacité et délai renseignés pour chaque mesure.")

    unrated = [m.id for m in mesures if m.priorite is None]
    check("Priorité", [f"mesure(s) sans priorité lisible : {unrated}"] if unrated else [],
          ok_message="Chaque mesure porte une priorité de l'échelle Faible / Moyenne / Élevée.")

    # 5. Écarts du socle — every gap a scenario actually considered (§18's own
    #    baseline_gaps_considered) is addressed by at least one measure on that
    #    scenario. Mesure has no gap_id field of its own (out of the fixed
    #    w5_output schema, conception §19) — coverage is read through the
    #    scenario it is attached to, not traced to an individual gap id. A
    #    measure with no scenario at all (a pure socle-wide fix, e.g. "publier
    #    une politique de mots de passe") is real but outside what this check
    #    can verify; it is not flagged as a problem for that reason alone.
    gaps_considered = {s.id for s in w5_input.scenarios if s.baseline_gaps_considered}
    unaddressed = [sid for sid in gaps_considered if sid not in covered]
    check("Écarts du socle rattachés à un scénario",
          [f"scénario(s) avec écart(s) considéré(s) mais sans mesure : {unaddressed}"] if unaddressed else [],
          ok_message="Chaque scénario dont l'atelier 4 a examiné un écart du socle a au moins une mesure.")

    return QualityReport(checks=checks)
