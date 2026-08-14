"""Deterministic atelier 2 methodology (white-box §4, §7, §10, §11, §12, §13, §14, §16).

Pure functions, no LLM and no I/O. Everything the white-box spec puts on the
"code / règles" side of §16 lives here: validating the atelier 1 data, enforcing
that a candidate comes from the approved base and carries a justification and a
context anchor, refusing techniques dressed up as sources or objectives, building
the couples and their traceability, applying the pertinence/vraisemblance scales,
and running the independent quality checker.

The model can propose and argue; it cannot talk its way past this module.
"""

from __future__ import annotations

import re
import unicodedata

from ebios_rm.domain.enums import Origin, Pertinence, StatutSelection, VraisemblanceInitiale
from ebios_rm.domain.risk_source import CoupleSROV, ObjectifVise, RiskSource
from ebios_rm.plugins.registry import EbiosBase
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.models import (
    REASON_BIEN_ESSENTIEL_INCONNU,
    REASON_DOUBLON,
    REASON_ECARTE_PAR_AGENT,
    REASON_EXTREMITE_NON_RETENUE,
    REASON_HORS_CATALOGUE,
    REASON_PAS_UN_ACTEUR,
    REASON_REFERENCE_INVALIDE,
    REASON_SANS_ANCRAGE_CONTEXTE,
    REASON_SANS_JUSTIFICATION,
    REASON_SCORES_INVALIDES,
    REASON_TECHNIQUE_PAS_OBJECTIF,
    STATUT_AVERTISSEMENT,
    STATUT_ERREUR,
    STATUT_OK,
    Atelier1Alert,
    CoupleProposal,
    ElementEcarte,
    ObjectifViseProposal,
    QualityCheck,
    QualityReport,
    RiskSourceProposal,
    Workshop2Input,
)

_STATUTS = {s.value for s in StatutSelection}
_SCORE_RANGE = range(1, 5)  # motivation / ressources / activité are rated 1..4


# --- text helpers -----------------------------------------------------------

def normalise(text: str) -> str:
    """Lowercase, accent-free, single-spaced — for comparisons only, never for display."""
    stripped = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(c for c in stripped if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", ascii_text.casefold()).strip()


# Attack techniques and modalities. An objectif visé phrased as one of these is a
# forbidden confusion (white-box §9, §17): « injection SQL », « PowerShell » and
# « phishing » describe *how*, and atelier 2 is about *what for*. The same list
# guards sources de risque, where a vulnerability is likewise not an actor (§17).
#
# ponytail: keyword blocklist. It catches the failure the weak dev model actually
# produces (a technique handed back as an objective). Upgrade to a classifier call
# only if real runs show false positives — a legitimate objective mentioning one of
# these words in passing.
_TECHNIQUE_TERMS = (
    "phishing", "hameconnage", "spear", "injection sql", "sql", "xss", "csrf",
    "powershell", "ransomware", "rancongiciel", "malware", "logiciel malveillant",
    "ddos", "deni de service", "force brute", "brute force", "exploit",
    "vulnerabilite", "faille", "cve-", "0-day", "zero day", "backdoor",
    "porte derobee", "keylogger", "rootkit", "credential stuffing",
    "vol d identifiants", "vol didentifiants", "escalade de privileges",
    "mouvement lateral", "scan de ports", "ingenierie sociale",
)

# Things that are assets, not actors (white-box §17: « transformer un serveur, une
# base ou une vulnérabilité en SR »).
_ASSET_TERMS = (
    "serveur", "base de donnees", "annuaire", "application", "poste de travail",
    "pare-feu", "firewall", "vpn", "site web", "messagerie", "sauvegarde",
    "systeme d information", "reseau",
)


def _mentions(text: str, terms: tuple[str, ...]) -> str | None:
    """The first term of ``terms`` occurring as a word in ``text``, if any."""
    haystack = normalise(text)
    for term in terms:
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack):
            return term
    return None


def looks_like_technique(text: str) -> str | None:
    """The attack technique this text names, if it names one (white-box §9, §17)."""
    return _mentions(text, _TECHNIQUE_TERMS)


def looks_like_asset_or_vuln(text: str) -> str | None:
    """The asset or vulnerability this text names, if it names one (white-box §17)."""
    return _mentions(text, _ASSET_TERMS) or looks_like_technique(text)


# --- Étape 0: validate the atelier 1 output before reasoning (white-box §4) ---

def validate_atelier1(w1: Workshop1Output) -> list[Atelier1Alert]:
    """Check ids, relations and mandatory fields of the atelier 1 output (white-box §4).

    Produces alerts; never repairs. « Erreur de donnée n'est pas erreur de
    raisonnement » — a broken reference is the auditor's to fix in atelier 1, and
    silently patching it here would hide a defect in the study.
    """
    alerts: list[Atelier1Alert] = []
    be_ids: set[str] = set()

    for asset in w1.biens_essentiels:
        if not asset.id or not asset.nom.strip():
            alerts.append(Atelier1Alert(
                reference=asset.id or "(bien essentiel sans id)",
                probleme="Bien essentiel sans identifiant ou sans nom.",
            ))
        if asset.id in be_ids:
            alerts.append(Atelier1Alert(
                reference=asset.id, probleme="Identifiant de bien essentiel en double.",
            ))
        be_ids.add(asset.id)

    bs_ids: set[str] = set()
    for support in w1.biens_supports:
        if support.id in bs_ids:
            alerts.append(Atelier1Alert(
                reference=support.id, probleme="Identifiant de bien support en double.",
            ))
        bs_ids.add(support.id)
        for be_id in support.biens_essentiels_supportes:
            if be_id not in be_ids:
                alerts.append(Atelier1Alert(
                    reference=support.id,
                    probleme=f"Le bien support référence un bien essentiel inconnu : '{be_id}'.",
                ))

    er_ids: set[str] = set()
    for event in w1.evenements_redoutes:
        if event.id in er_ids:
            alerts.append(Atelier1Alert(
                reference=event.id, probleme="Identifiant d'événement redouté en double.",
            ))
        er_ids.add(event.id)
        if event.bien_essentiel_id not in be_ids:
            alerts.append(Atelier1Alert(
                reference=event.id,
                probleme=(
                    f"L'événement redouté référence un bien essentiel inconnu : "
                    f"'{event.bien_essentiel_id}'."
                ),
            ))

    if not w1.biens_essentiels:
        alerts.append(Atelier1Alert(
            reference="atelier1",
            probleme="Aucun bien essentiel : l'atelier 2 n'a rien sur quoi raisonner.",
        ))
    # Non-blocking: the objectives are built from the essential assets, so the study
    # can proceed, but the auditor should know the atelier 1 output is thin.
    if not w1.evenements_redoutes:
        alerts.append(Atelier1Alert(
            reference="atelier1",
            probleme="Aucun événement redouté : les enjeux de sécurité ne sont pas explicités.",
            bloquant=False,
        ))
    return alerts


# --- Étape 3: filter and justify the sources de risque (white-box §7) --------

def _statut_of(raw: str) -> StatutSelection | None:
    value = (raw or "").strip().casefold()
    return StatutSelection(value) if value in _STATUTS else None


def _cited_fields(fields: list[str]) -> list[str]:
    return [f.strip() for f in fields if f and f.strip()]


def filter_sources(
    proposals: list[RiskSourceProposal],
    base: EbiosBase,
) -> tuple[list[RiskSource], list[ElementEcarte]]:
    """Turn candidate sources into retained/secondary ones, or into justified rejects.

    Four rules, all code-enforced (white-box §6, §7, §17):
      * the category must come from the approved base — never invented at runtime;
      * a candidate is not retained merely because the catalogue lists it: it needs
        a justification tied to this organisation;
      * that justification must cite at least one context element;
      * an actor is an actor — a server, a database or a vulnerability is not.
    """
    categories = base.source_categories()
    retained: list[RiskSource] = []
    discarded: list[ElementEcarte] = []
    seen: dict[str, str] = {}  # normalised name -> assigned id

    def reject(proposal: RiskSourceProposal, raison: str, detail: str = "") -> None:
        discarded.append(ElementEcarte(
            type="source_risque",
            reference=proposal.categorie_id or "(sans catégorie)",
            libelle=proposal.nom,
            raison=raison,
            detail=detail or proposal.justification.strip(),
        ))

    for proposal in proposals:
        category = categories.get(proposal.categorie_id.strip())
        if category is None:
            reject(proposal, REASON_HORS_CATALOGUE,
                   f"Catégorie proposée : '{proposal.categorie_id}'.")
            continue

        statut = _statut_of(proposal.statut)
        if statut is None or statut is StatutSelection.ECARTE:
            reject(proposal, REASON_ECARTE_PAR_AGENT)
            continue
        if not proposal.justification.strip():
            reject(proposal, REASON_SANS_JUSTIFICATION)
            continue
        cited = _cited_fields(proposal.derived_from_fact_fields)
        if not cited:
            reject(proposal, REASON_SANS_ANCRAGE_CONTEXTE)
            continue
        named = looks_like_asset_or_vuln(f"{proposal.nom} {proposal.description}")
        if named:
            reject(proposal, REASON_PAS_UN_ACTEUR, f"Terme relevé : « {named} ».")
            continue

        key = normalise(proposal.nom) or proposal.categorie_id
        if key in seen:
            reject(proposal, REASON_DOUBLON, f"Déjà retenue sous {seen[key]}.")
            continue

        source_id = f"SR-{len(retained) + 1:02d}"
        seen[key] = source_id
        retained.append(RiskSource(
            id=source_id,
            categorie_id=category.id,
            categorie_libelle=category.libelle,
            nom=proposal.nom.strip(),
            description=proposal.description.strip(),
            motivation=proposal.motivation.strip(),
            statut=statut,
            justification=proposal.justification.strip(),
            derived_from_fact_fields=cited,
            origin=Origin.ASSESSMENT,
        ))
    return retained, discarded


# --- Étape 6: filter and justify the objectifs visés (white-box §10) ---------

def filter_objectifs(
    proposals: list[ObjectifViseProposal],
    base: EbiosBase,
    w2_input: Workshop2Input,
) -> tuple[list[ObjectifVise], list[ElementEcarte]]:
    """Turn candidate objectives into retained ones, or into justified rejects.

    Is it really an objective (not a technique)? Is it tied to a real stake — an
    atelier 1 essential asset? Is the finalité one the approved base defines? Is it
    distinct from another objective?
    """
    finalites = base.objectif_finalites()
    known_be = {a.id for a in w2_input.biens_essentiels}
    retained: list[ObjectifVise] = []
    discarded: list[ElementEcarte] = []
    seen: dict[str, str] = {}

    def reject(proposal: ObjectifViseProposal, raison: str, detail: str = "") -> None:
        discarded.append(ElementEcarte(
            type="objectif_vise",
            reference=proposal.finalite_id or "(sans finalité)",
            libelle=proposal.description,
            raison=raison,
            detail=detail or proposal.justification.strip(),
        ))

    for proposal in proposals:
        finalite = finalites.get(proposal.finalite_id.strip())
        if finalite is None:
            reject(proposal, REASON_HORS_CATALOGUE,
                   f"Finalité proposée : '{proposal.finalite_id}'.")
            continue

        statut = _statut_of(proposal.statut)
        if statut is None or statut is StatutSelection.ECARTE:
            reject(proposal, REASON_ECARTE_PAR_AGENT)
            continue
        if not proposal.justification.strip():
            reject(proposal, REASON_SANS_JUSTIFICATION)
            continue
        technique = looks_like_technique(proposal.description)
        if technique:
            reject(proposal, REASON_TECHNIQUE_PAS_OBJECTIF, f"Terme relevé : « {technique} ».")
            continue

        # An objective with no reachable stake cannot be traced back to atelier 1 (§12).
        targets = [be for be in proposal.biens_essentiels_vises if be in known_be]
        if not targets:
            reject(proposal, REASON_BIEN_ESSENTIEL_INCONNU,
                   f"Biens essentiels proposés : {proposal.biens_essentiels_vises}.")
            continue

        key = normalise(proposal.description)
        if key in seen:
            reject(proposal, REASON_DOUBLON, f"Déjà retenu sous {seen[key]}.")
            continue

        objectif_id = f"OV-{len(retained) + 1:02d}"
        seen[key] = objectif_id
        retained.append(ObjectifVise(
            id=objectif_id,
            finalite_id=finalite.id,
            finalite_libelle=finalite.libelle,
            description=proposal.description.strip(),
            enjeu=proposal.enjeu.strip(),
            biens_essentiels_vises=targets,
            statut=statut,
            justification=proposal.justification.strip(),
            derived_from_fact_fields=_cited_fields(proposal.derived_from_fact_fields),
            origin=Origin.ASSESSMENT,
        ))
    return retained, discarded


# --- Étape 9: characterisation and prioritisation (white-box §13) ------------

def pertinence_of(motivation: int, ressources: int) -> Pertinence:
    """Pertinence of a couple, from the source's motivation and its means.

    The scale is code, not prompt: letting the LLM invent a formula is a forbidden
    design error (§17). Both factors must be present — a highly motivated actor
    with no means, and a well-resourced one with no interest, are both weak.

    ponytail: product of the two 1..4 ratings, banded. Replace the bands here (one
    function, one test) if the project adopts a different official scale — §22 asks
    for exactly that check against the adopted EBIOS RM version.
    """
    score = motivation * ressources
    if score <= 3:
        return Pertinence.FAIBLE
    if score <= 8:
        return Pertinence.MOYEN
    return Pertinence.ELEVE


def vraisemblance_of(pertinence: Pertinence, activite: int) -> VraisemblanceInitiale:
    """Initial likelihood V1..V4 — "does this source target this organisation".

    Never technical success: whether an attack would work is atelier 4's question,
    answered there against the security-baseline gaps. Here, a pertinent source
    that is also observed to be active against this sector is likelier to come.
    """
    base = {Pertinence.FAIBLE: 1, Pertinence.MOYEN: 2, Pertinence.ELEVE: 3}[pertinence]
    level = min(4, base + (1 if activite >= 3 else 0))
    return VraisemblanceInitiale(f"V{level}")


# --- Étapes 7 & 8: build the couples and trace them back to atelier 1 --------

def build_couples(
    proposals: list[CoupleProposal],
    sources: list[RiskSource],
    objectifs: list[ObjectifVise],
    w2_input: Workshop2Input,
) -> tuple[list[CoupleSROV], list[CoupleSROV], list[ElementEcarte]]:
    """Associate compatible SR and OV — never every combination (white-box §11, §12).

    Returns (retained, secondary, discarded). Each retained couple carries its full
    trace: SR -> OV -> bien(s) essentiel(s) -> valeur(s) métier, with the associated
    support assets as dependency information. That trace is a lookup over the
    atelier 1 output and is computed here, not asked of the model.
    """
    sources_by_id = {s.id: s for s in sources}
    objectifs_by_id = {o.id: o for o in objectifs}
    assets_by_id = {a.id: a for a in w2_input.biens_essentiels}

    retained: list[CoupleSROV] = []
    secondary: list[CoupleSROV] = []
    discarded: list[ElementEcarte] = []
    seen: set[tuple[str, str]] = set()

    def reject(proposal: CoupleProposal, raison: str, detail: str = "") -> None:
        discarded.append(ElementEcarte(
            type="couple",
            reference=f"{proposal.source_risque_id}/{proposal.objectif_vise_id}",
            libelle=proposal.justification.strip(),
            raison=raison,
            detail=detail,
        ))

    for proposal in proposals:
        source = sources_by_id.get(proposal.source_risque_id.strip())
        objectif = objectifs_by_id.get(proposal.objectif_vise_id.strip())
        if source is None or objectif is None:
            reject(proposal, REASON_REFERENCE_INVALIDE)
            continue
        if StatutSelection.ECARTE in (source.statut, objectif.statut):
            reject(proposal, REASON_EXTREMITE_NON_RETENUE)
            continue

        statut = _statut_of(proposal.statut)
        if statut is None or statut is StatutSelection.ECARTE:
            reject(proposal, REASON_ECARTE_PAR_AGENT, proposal.justification.strip())
            continue
        if not proposal.justification.strip():
            reject(proposal, REASON_SANS_JUSTIFICATION)
            continue

        key = (source.id, objectif.id)
        if key in seen:
            reject(proposal, REASON_DOUBLON)
            continue
        scores = (proposal.motivation, proposal.ressources, proposal.activite)
        if any(s not in _SCORE_RANGE for s in scores):
            # Not clamped and not guessed: an uncotated couple cannot be prioritised,
            # and inventing its rating is exactly what §17 forbids.
            reject(proposal, REASON_SCORES_INVALIDES,
                   f"motivation={proposal.motivation}, ressources={proposal.ressources}, "
                   f"activite={proposal.activite}")
            continue

        seen.add(key)
        # A secondary source drags its couples to secondary too: the couple cannot be
        # more firmly retained than the source it rests on.
        if StatutSelection.SECONDAIRE in (source.statut, objectif.statut):
            statut = StatutSelection.SECONDAIRE

        be_ids = list(objectif.biens_essentiels_vises)
        valeurs: list[str] = []
        for be_id in be_ids:
            asset = assets_by_id.get(be_id)
            if asset is None:
                continue
            for processus in asset.processus_metier_associes or [asset.nom]:
                if processus not in valeurs:
                    valeurs.append(processus)
        supports = [
            s.id for s in w2_input.biens_supports
            if any(be_id in s.biens_essentiels_supportes for be_id in be_ids)
        ]

        pertinence = pertinence_of(proposal.motivation, proposal.ressources)
        couple = CoupleSROV(
            id=f"CPL-{len(retained) + len(secondary) + 1:02d}",
            source_risque_id=source.id,
            objectif_vise_id=objectif.id,
            biens_essentiels_ids=be_ids,
            valeurs_metier=valeurs,
            biens_supports_associes=supports,
            motivation=proposal.motivation,
            ressources=proposal.ressources,
            activite=proposal.activite,
            pertinence=pertinence,
            vraisemblance_initiale=vraisemblance_of(pertinence, proposal.activite),
            statut=statut,
            justification=proposal.justification.strip(),
        )
        (secondary if statut is StatutSelection.SECONDAIRE else retained).append(couple)

    # Highest pertinence first, then likelihood — the priorisation the auditor reads (§13).
    order = {Pertinence.ELEVE: 0, Pertinence.MOYEN: 1, Pertinence.FAIBLE: 2}
    sort_key = lambda c: (order[c.pertinence], -int(c.vraisemblance_initiale.value[1]))  # noqa: E731
    retained.sort(key=sort_key)
    secondary.sort(key=sort_key)
    return retained, secondary, discarded


# --- Étape 10: the independent quality checker (white-box §14) ---------------

def run_quality_checks(
    w2_input: Workshop2Input,
    base: EbiosBase,
    sources: list[RiskSource],
    objectifs: list[ObjectifVise],
    couples: list[CoupleSROV],
    couples_secondaires: list[CoupleSROV],
) -> QualityReport:
    """The ten controls of white-box §14, run over the assembled result.

    Independent of the generation: it re-checks the output it is given rather than
    trusting that the filters ran, so a future change that loosens one of them
    still surfaces here instead of shipping silently.
    """
    checks: list[QualityCheck] = []
    all_couples = [*couples, *couples_secondaires]
    sources_by_id = {s.id: s for s in sources}
    objectifs_by_id = {o.id: o for o in objectifs}
    categories = base.source_categories()
    finalites = base.objectif_finalites()
    known_be = {a.id for a in w2_input.biens_essentiels}
    support_names = {normalise(s.nom) for s in w2_input.biens_supports}

    def check(controle: str, problems: list[str], *, statut: str = STATUT_ERREUR,
              ok_message: str = "") -> None:
        checks.append(QualityCheck(
            controle=controle,
            statut=statut if problems else STATUT_OK,
            message="; ".join(problems) if problems else ok_message,
        ))

    # 1. Terminologie — SR, OV, BE and BS kept distinct.
    terminology = [
        f"{s.id} « {s.nom} » désigne un bien support, pas un acteur"
        for s in sources if normalise(s.nom) in support_names
    ]
    check("Terminologie", terminology, ok_message="SR, OV, BE et BS sont distincts.")

    # 2. Périmètre — every couple concerns an essential asset of the study.
    scope = [
        f"{c.id} vise des biens essentiels hors atelier 1 : "
        f"{[b for b in c.biens_essentiels_ids if b not in known_be]}"
        for c in all_couples if any(b not in known_be for b in c.biens_essentiels_ids)
    ]
    check("Périmètre", scope, ok_message="Tous les couples restent dans le périmètre étudié.")

    # 3. Traçabilité — every couple resolves back to atelier 1.
    trace = [f"{c.id} n'est relié à aucun bien essentiel" for c in all_couples
             if not c.biens_essentiels_ids]
    check("Traçabilité", trace, ok_message="Chaque couple remonte à l'atelier 1.")

    # 4. SR — plausible and justified, with a context anchor.
    sr_problems = [
        f"{s.id} sans justification" if not s.justification.strip()
        else f"{s.id} sans élément de contexte cité"
        for s in sources
        if not s.justification.strip() or not s.derived_from_fact_fields
    ]
    check("Sources de risque", sr_problems,
          ok_message="Chaque source retenue est justifiée et ancrée dans le contexte.")

    # 5. OV — an objective, not a technique.
    ov_problems = [
        f"{o.id} formule une technique (« {looks_like_technique(o.description)} »)"
        for o in objectifs if looks_like_technique(o.description)
    ]
    check("Objectifs visés", ov_problems,
          ok_message="Chaque objectif est un objectif, pas une modalité technique.")

    # 6. SR/OV — the couple forms a coherent intent. A finalité outside the ones the
    #    base lists as typical for that actor is a warning, not an error: the model
    #    may have a real reason, and the auditor is the one who rules on it.
    incoherent = []
    for couple in all_couples:
        source, objectif = sources_by_id.get(couple.source_risque_id), objectifs_by_id.get(couple.objectif_vise_id)
        if source is None or objectif is None:
            continue
        category = categories.get(source.categorie_id)
        if category and objectif.finalite_id not in category.finalites_typiques:
            incoherent.append(
                f"{couple.id} : « {objectif.finalite_libelle} » n'est pas une finalité "
                f"typique de « {source.categorie_libelle} » — à confirmer par l'auditeur"
            )
    check("Cohérence SR/OV", incoherent, statut=STATUT_AVERTISSEMENT,
          ok_message="Chaque couple forme une intention cohérente.")

    # 7. Doublons.
    pairs = [(c.source_risque_id, c.objectif_vise_id) for c in all_couples]
    duplicates = sorted({f"{sr}/{ov}" for (sr, ov) in pairs if pairs.count((sr, ov)) > 1})
    check("Doublons", [f"couple en double : {d}" for d in duplicates],
          ok_message="Aucun couple équivalent.")

    # 8. Données — identifiers and relations valid.
    data = [
        f"{c.id} référence {c.source_risque_id}/{c.objectif_vise_id}, inconnu"
        for c in all_couples
        if c.source_risque_id not in sources_by_id or c.objectif_vise_id not in objectifs_by_id
    ]
    check("Données", data, ok_message="Identifiants et relations valides.")

    # 9. Méthode — everything comes from the approved base.
    method = [
        f"{s.id} : catégorie '{s.categorie_id}' absente de la base" for s in sources
        if s.categorie_id not in categories
    ] + [
        f"{o.id} : finalité '{o.finalite_id}' absente de la base" for o in objectifs
        if o.finalite_id not in finalites
    ]
    check("Méthode", method,
          ok_message=f"Base méthodologique approuvée : {base.name} ({base.ebios_version}).")
    if not base.verified_against_official_guide:
        checks.append(QualityCheck(
            controle="Méthode — relecture du référentiel",
            statut=STATUT_AVERTISSEMENT,
            message=(
                f"La base « {base.name} » n'est pas encore marquée comme relue contre le "
                "guide officiel EBIOS RM adopté (white-box §22)."
            ),
        ))

    # 10. Incertitude — assumptions distinguishable from supplied facts.
    known_fields = {f.field_name for f in w2_input.faits_contexte}
    unknown = sorted({
        field
        for item in [*sources, *objectifs]
        for field in item.derived_from_fact_fields
        if field not in known_fields
    })
    check("Incertitude", [f"champ cité absent du contexte : {u}" for u in unknown],
          statut=STATUT_AVERTISSEMENT,
          ok_message="Faits et hypothèses restent distinguables.")

    return QualityReport(checks=checks)
