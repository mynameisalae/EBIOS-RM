"""Workshop 2 execution (white-box §2) — the deterministic conductor.

Runs the ten steps of the white-box architecture in order: validate the atelier 1
output, build the working context, generate and filter the sources de risque,
generate and filter the objectifs visés, build the SR/OV couples, trace them back
to atelier 1, characterise and prioritise them, and run the quality checker.

The agent only proposes; every acceptance, rejection, score and scale is enforced
in assessment.py, which has no LLM (white-box §16).

What is *not* here, on purpose (conception §10.2): the approval loop, versioning,
pause/resume, the decision log and token accounting. Workshop 2 exposes the same
seams as workshop 1 — a runner Protocol, ``revision_notes``, ``blocks`` +
``previous``, and a pure function over typed input — and the orchestrator supplies
the machinery. One loop driving five identically-shaped workshops is what keeps
the rollback cap in one file instead of five.
"""

from __future__ import annotations

from ebios_rm.mission_context.mission_context import MissionContext
from ebios_rm.plugins.registry import EbiosBase
from ebios_rm.workshops.common import AtelierDataError
from ebios_rm.workshops.workshop1_cadrage.models import Workshop1Output
from ebios_rm.workshops.workshop2_sources_risque.agent_runner import Workshop2AgentRunner
from ebios_rm.workshops.workshop2_sources_risque.assessment import (
    build_couples,
    filter_objectifs,
    filter_sources,
    run_quality_checks,
    validate_atelier1,
)
from ebios_rm.workshops.workshop2_sources_risque.models import (
    CONTEXT_FIELDS,
    ElementEcarte,
    Workshop2Input,
    Workshop2Output,
)

# The three independently-generated blocks of w2_output. A rejection can target any
# subset; the rest is reused verbatim (partial redo, conception §12.6).
BLOCK_SOURCES = "sources"        # les sources de risque retenues
BLOCK_OBJECTIFS = "objectifs"    # les objectifs visés retenus
BLOCK_COUPLES = "couples"        # les couples SR/OV, leur trace et leur priorisation
ALL_BLOCKS = {BLOCK_SOURCES, BLOCK_OBJECTIFS, BLOCK_COUPLES}


# --- Mission Context + w1_output -> the narrow atelier 2 input (white-box §3) ---

def build_workshop2_input(
    mission_context: MissionContext, w1_output: Workshop1Output
) -> Workshop2Input:
    """Assemble the only input atelier 2 is allowed to see (white-box §3).

    This function is the input contract. It reads exactly ``CONTEXT_FIELDS`` from
    the Mission Context and exactly three lists from atelier 1 — which is also how
    ``baseline_gaps_full``, ``unverified_controls`` and ``human_edits`` are kept
    out: they are never read, rather than read and then filtered.
    """
    facts = [f for f in mission_context.facts if f.field_name in CONTEXT_FIELDS]
    return Workshop2Input(
        organisation_nom=mission_context.organisation_nom,
        secteur_activite=mission_context.secteur_activite,
        contexte={f.field_name: f.value for f in facts if f.value not in (None, "")},
        biens_essentiels=[a.model_copy(deep=True) for a in w1_output.biens_essentiels],
        biens_supports=[s.model_copy(deep=True) for s in w1_output.biens_supports],
        evenements_redoutes=[e.model_copy(deep=True) for e in w1_output.evenements_redoutes],
        faits_contexte=[f.model_copy(deep=True) for f in facts],
        alertes_atelier1=validate_atelier1(w1_output),
    )


# --- Workshop2Input -> w2_output ---

def _kept(previous: Workshop2Output | None, type_: str) -> list[ElementEcarte]:
    """The discarded elements of one family, carried over when its block is not redone."""
    return [e for e in (previous.elements_ecartes if previous else []) if e.type == type_]


def run_workshop2(
    w2_input: Workshop2Input,
    runner: Workshop2AgentRunner,
    base: EbiosBase,
    revision_notes: list[str] | None = None,
    blocks: set[str] | None = None,
    previous: Workshop2Output | None = None,
) -> Workshop2Output:
    """Run atelier 2 over a validated input and emit w2_output (white-box §2, §19).

    ``revision_notes`` are the auditor's rejection reasons, passed to the
    regenerated blocks so the redo addresses them.

    ``blocks`` selects what to regenerate (default: everything); untouched blocks
    are copied verbatim from ``previous``, so rejecting a wrong priority never
    reshuffles couples the auditor already accepted — and never pays for LLM calls
    nobody asked for.
    """
    todo = set(blocks) if blocks else set(ALL_BLOCKS)
    if todo != ALL_BLOCKS and previous is None:
        raise ValueError("Un rejeu partiel a besoin du résultat précédent pour réutiliser les blocs conservés.")

    # Étape 0 — validate atelier 1 before reasoning (white-box §4). Raised, never
    # worked around: « erreur de donnée n'est pas erreur de raisonnement ».
    if w2_input.alertes_bloquantes:
        raise AtelierDataError(1, w2_input.alertes_bloquantes)

    # Regenerating either end of a couple regenerates the couples: SR/OV ids are
    # assigned by the filters, so keeping old couples across a new source set would
    # leave them pointing at ids that no longer mean the same thing.
    if todo & {BLOCK_SOURCES, BLOCK_OBJECTIFS}:
        todo.add(BLOCK_COUPLES)

    ecartes: list[ElementEcarte] = []

    # Étapes 2-4 — candidate sources de risque, then filter and justify.
    if BLOCK_SOURCES in todo:
        proposals = runner.propose_sources(w2_input, base, revision_notes)
        sources, discarded = filter_sources(proposals, base)
        ecartes.extend(discarded)
    else:
        sources = [s.model_copy(deep=True) for s in previous.sources_risque]
        ecartes.extend(_kept(previous, "source_risque"))

    # Étapes 5-6 — candidate objectifs visés, then filter and justify.
    if BLOCK_OBJECTIFS in todo:
        proposals = runner.propose_objectifs(w2_input, base, sources, revision_notes)
        objectifs, discarded = filter_objectifs(proposals, base, w2_input)
        ecartes.extend(discarded)
    else:
        objectifs = [o.model_copy(deep=True) for o in previous.objectifs_vises]
        ecartes.extend(_kept(previous, "objectif_vise"))

    # Étapes 7-9 — couples, traceability back to atelier 1, characterisation.
    if BLOCK_COUPLES in todo:
        proposals = runner.propose_couples(w2_input, sources, objectifs, revision_notes)
        couples, couples_secondaires, discarded = build_couples(
            proposals, sources, objectifs, w2_input
        )
        ecartes.extend(discarded)
    else:
        couples = [c.model_copy(deep=True) for c in previous.couples]
        couples_secondaires = [c.model_copy(deep=True) for c in previous.couples_secondaires]
        ecartes.extend(_kept(previous, "couple"))

    # Étape 10 — the quality checker, always run over the assembled result.
    return Workshop2Output(
        sources_risque=sources,
        objectifs_vises=objectifs,
        couples=couples,
        couples_secondaires=couples_secondaires,
        elements_ecartes=ecartes,
        quality_report=run_quality_checks(
            w2_input, base, sources, objectifs, couples, couples_secondaires
        ),
        alertes_atelier1=list(w2_input.alertes_atelier1),
        human_edits=list(previous.human_edits) if previous is not None else [],
    )
