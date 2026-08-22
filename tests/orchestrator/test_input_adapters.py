"""build_workshop2_input — the narrow, typed handoff from Atelier 1 to Atelier 2
(conception §9, §16). Only biens_essentiels and evenements_redoutes cross the
boundary; everything else in Workshop1Output must be left behind."""

from __future__ import annotations

from ebios_rm.domain.enums import CategorieImpact, Gravite, Origin
from ebios_rm.domain.essential_asset import EssentialAsset, SupportAsset
from ebios_rm.domain.feared_event import FearedEvent
from ebios_rm.orchestrator.input_adapters import Workshop2Input, build_workshop2_input
from ebios_rm.workshops.workshop1_cadrage.models import (
    BaselineGap,
    BaselineScopeDecision,
    ControlReference,
    UnverifiedControl,
    Workshop1Output,
)


def _w1_output() -> Workshop1Output:
    be = EssentialAsset(
        id="BE-1", nom="Dossier patient", description="Données de santé", nature="information",
        origin=Origin.ASSESSMENT, derived_from_fact_fields=["processus_metier_critiques"],
    )
    bs = SupportAsset(
        id="BS-1", nom="SIH", description="Système d'information hospitalier", type_support="application",
        biens_essentiels_supportes=["BE-1"], origin=Origin.ASSESSMENT, derived_from_fact_fields=["systeme_information_resume"],
    )
    er = FearedEvent(
        id="ER-1", description="Fuite de données de santé", bien_essentiel_id="BE-1",
        categorie_impact=CategorieImpact.VIE_PRIVEE_PERSONNES_CONCERNEES, gravite=Gravite.CRITIQUE,
        origin=Origin.ASSESSMENT, derived_from_fact_fields=["donnees_personnelles_traitees"],
    )
    gap = BaselineGap(
        gap_id="BG-abc123", weakness="Pas de MFA sur le VPN",
        controls=[ControlReference(framework="ANSSI_hygiene", control_id="ANSSI-H-21")],
        risk_categories=["initial_access"],
    )
    return Workshop1Output(
        biens_essentiels=[be],
        biens_supports=[bs],
        evenements_redoutes=[er],
        baseline_scope_decisions=[BaselineScopeDecision(category="RGPD", decision="excluded", justification="hors périmètre")],
        baseline_gaps_full=[gap],
        unverified_controls=[UnverifiedControl(control_id="NIST-PR.AC-1", framework="NIST")],
        human_edits=[{"field": "gravite", "old": "Grave", "new": "Critique"}],
    )


def test_build_workshop2_input_carries_only_the_two_needed_fields():
    w1 = _w1_output()
    w2_input = build_workshop2_input(w1)

    assert isinstance(w2_input, Workshop2Input)
    assert w2_input.biens_essentiels == w1.biens_essentiels
    assert w2_input.evenements_redoutes == w1.evenements_redoutes


def test_build_workshop2_input_never_carries_baseline_or_edits():
    """The point of a narrow input: biens_supports, scope decisions, gaps,
    unverified controls and human edits must not be reachable from Workshop2Input
    at all — not just empty, genuinely absent from the model."""
    w2_input = build_workshop2_input(_w1_output())
    fields = set(Workshop2Input.model_fields)
    assert fields == {"biens_essentiels", "evenements_redoutes"}


def test_build_workshop2_input_with_empty_workshop1_output():
    w2_input = build_workshop2_input(Workshop1Output())
    assert w2_input.biens_essentiels == []
    assert w2_input.evenements_redoutes == []
