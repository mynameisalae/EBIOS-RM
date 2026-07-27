"""One gap per real weakness, listing every framework requiring it (conception §15 step 9)."""

from ebios_rm.workshops.workshop1_cadrage.gap_dedup import (
    GapGroupProposal,
    consolidate,
    valid_groups,
)
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap, ControlReference


def _gap(gap_id, framework, control_id, weakness, categories=("credential_access",), evidence=""):
    return BaselineGap(
        gap_id=gap_id, weakness=weakness,
        controls=[ControlReference(framework=framework, control_id=control_id)],
        risk_categories=list(categories), evidence_quote=evidence,
    )


def _mfa_gaps():
    return [
        _gap("BG-iso", "ISO27001", "A.5.15", "L'authentification multi-facteur n'est pas généralisée.",
             ("credential_access", "initial_access"), "acces_distant_moyens = VPN"),
        _gap("BG-nist", "NIST", "PR.AA-05", "Multi-factor authentication is not enforced for remote access.",
             ("credential_access",), "pas de MFA mentionné"),
        _gap("BG-anssi", "ANSSI_hygiene", "ANSSI-H-21", "Pas de MFA sur l'accès distant.",
             ("initial_access",)),
        _gap("BG-backup", "ISO27001", "A.8.13", "Pas de copie de sauvegarde hors ligne.", ("impact",)),
    ]


# --- consolidation ---

def test_group_becomes_one_gap_listing_every_framework():
    gaps = _mfa_gaps()
    group = GapGroupProposal(gap_ids=["BG-iso", "BG-nist", "BG-anssi"],
                             merged_weakness="Pas de MFA sur les accès distants",
                             reason="même faiblesse, trois référentiels")

    out = consolidate(gaps, [group])

    assert len(out) == 2                                   # 4 gaps -> MFA + backup
    mfa = next(g for g in out if g.gap_id == "BG-iso")
    assert mfa.weakness == "Pas de MFA sur les accès distants"
    assert mfa.frameworks == ["ISO27001", "NIST", "ANSSI_hygiene"]
    assert mfa.control_ids == ["A.5.15", "PR.AA-05", "ANSSI-H-21"]


def test_consolidation_unions_risk_categories_and_keeps_evidence():
    out = consolidate(_mfa_gaps(), [GapGroupProposal(gap_ids=["BG-iso", "BG-nist"])])
    mfa = next(g for g in out if g.gap_id == "BG-iso")
    assert mfa.risk_categories == ["credential_access", "initial_access"]
    assert "acces_distant_moyens = VPN" in mfa.evidence_quote
    assert "pas de MFA mentionné" in mfa.evidence_quote


def test_ungrouped_gaps_pass_through_untouched():
    gaps = _mfa_gaps()
    out = consolidate(gaps, [GapGroupProposal(gap_ids=["BG-iso", "BG-nist"])])
    backup = next(g for g in out if g.gap_id == "BG-backup")
    assert backup == gaps[-1]


def test_no_groups_changes_nothing():
    gaps = _mfa_gaps()
    assert consolidate(gaps, []) == gaps


# --- guards against a model dropping a finding ---

def test_invented_gap_ids_are_ignored():
    gaps = _mfa_gaps()
    kept = valid_groups([GapGroupProposal(gap_ids=["BG-iso", "BG-does-not-exist"])], gaps)
    assert kept == []                                      # only one real id left -> not a group


def test_a_gap_cannot_be_claimed_by_two_groups():
    gaps = _mfa_gaps()
    kept = valid_groups([
        GapGroupProposal(gap_ids=["BG-iso", "BG-nist"]),
        GapGroupProposal(gap_ids=["BG-nist", "BG-anssi"]),   # BG-nist already used
    ], gaps)
    assert len(kept) == 1
    assert kept[0].gap_ids == ["BG-iso", "BG-nist"]


def test_single_member_group_is_rejected():
    assert valid_groups([GapGroupProposal(gap_ids=["BG-iso"])], _mfa_gaps()) == []


def test_duplicate_ids_within_a_group_are_collapsed():
    kept = valid_groups([GapGroupProposal(gap_ids=["BG-iso", "BG-iso", "BG-nist"])], _mfa_gaps())
    assert kept[0].gap_ids == ["BG-iso", "BG-nist"]


def test_nothing_is_lost_when_a_group_is_refused():
    # Refusing a proposal must leave every gap standing.
    gaps = _mfa_gaps()
    out = consolidate(gaps, [])
    assert {g.gap_id for g in out} == {g.gap_id for g in gaps}


# --- workshop 4 handoff benefits automatically ---

def test_workshop4_handoff_has_one_entry_per_weakness():
    from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output

    consolidated = consolidate(_mfa_gaps(), [GapGroupProposal(gap_ids=["BG-iso", "BG-nist", "BG-anssi"])])
    output = Workshop1Output(baseline_gaps_full=consolidated)
    handoff = output.baseline_gaps_for_w4()

    assert len(handoff) == 2                                # not 4 agents for 2 weaknesses
    for entry in handoff:                                   # still stripped of referential identity (§12.3)
        assert set(entry.model_dump().keys()) == {"gap_id", "weakness", "risk_categories"}
