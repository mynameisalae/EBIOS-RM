"""Free-text referential mentions must reach the plugin that can be loaded (conception §12.5)."""

from ebios_rm.mission_context.mission_context import _canonical_frameworks

KNOWN = ("ISO27001", "ANSSI_hygiene", "NIST", "RGPD")


def test_prose_mentions_map_onto_plugin_ids():
    # The answer that broke the live run: three of the four entries could never match.
    parts = ["RGPD", "Certification HDS (hébergeur) pour le volet infogéreur",
             "Norme ISO 27001", "et le Code de la Santé Publique français."]
    assert _canonical_frameworks(parts, KNOWN) == [
        "RGPD",
        "Certification HDS (hébergeur) pour le volet infogéreur",  # no plugin: kept, gate decides
        "ISO27001",
        "et le Code de la Santé Publique français.",
    ]


def test_word_order_punctuation_and_accents_do_not_matter():
    assert _canonical_frameworks(["ISO/IEC 27001:2022"], KNOWN) == ["ISO27001"]
    assert _canonical_frameworks(["règles d'hygiène ANSSI"], KNOWN) == ["ANSSI_hygiene"]
    assert _canonical_frameworks(["nist csf 2.0"], KNOWN) == ["NIST"]


def test_a_neighbouring_standard_is_not_matched():
    assert _canonical_frameworks(["Norme ISO 27005"], KNOWN) == ["Norme ISO 27005"]


def test_the_most_specific_plugin_wins():
    # "NIST 800-53" carries every token of NIST too; declaring both would turn one
    # named referential into two.
    assert _canonical_frameworks(["NIST 800-53"], KNOWN + ("NIST_800_53",)) == ["NIST_800_53"]
    assert _canonical_frameworks(["NIST CSF 2.0"], KNOWN + ("NIST_800_53",)) == ["NIST"]


def test_duplicates_collapse_to_one_declaration():
    assert _canonical_frameworks(["ISO 27001", "ISO/IEC 27001"], KNOWN) == ["ISO27001"]
