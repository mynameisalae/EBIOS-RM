"""Consolidate baseline gaps that describe the same weakness (conception §15 step 9).

ISO 27001, NIST, ANSSI and RGPD all demand roughly the same controls, so one real
weakness ("no MFA on remote access") yields one gap per framework. Left alone that
pads the audit report and makes workshop 4 fan out several agents onto the same
problem.

Deciding that "L'authentification multi-facteur n'est pas généralisée" and
"Multi-factor authentication is not enforced for remote access" are the same
weakness is semantic judgement across two languages and two drafting styles — code
cannot do it, so a model proposes the groups. It only ever *proposes*: the auditor
confirms before anything is consolidated (§2, §15 step 9).

The consolidated gap carries every control that demands the fix, so the annex can
still cite all of them and show that one remediation satisfies several
referentials (§20.3).
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from ebios_rm.agent_runtime import StructuredCallFailed, run_structured
from ebios_rm.config import get_model
from ebios_rm.workshops.workshop1_cadrage.models import BaselineGap, ControlReference

# Gaps sent to the model in one call. Weakness strings are short, so a realistic
# assessment fits in a single call; a catastrophic audit (hundreds of gaps) is
# batched rather than truncated.
MAX_GAPS_PER_CALL = 60

_SYSTEM = """\
Tu compares des écarts de sécurité relevés contre plusieurs référentiels
(ISO 27001, NIST CSF, guide d'hygiène ANSSI, RGPD...).

Plusieurs référentiels exigent souvent la même chose. Ta tâche : regrouper les
écarts qui décrivent UNE MÊME faiblesse réelle de l'organisation, même s'ils sont
rédigés dans des langues ou des styles différents.

Règles absolues :
- Ne regroupe que des écarts qui seraient corrigés par la MÊME action. Si deux
  écarts portent sur des périmètres différents (ex. « pas de MFA sur le VPN » et
  « pas de MFA sur l'application métier »), ce sont DEUX faiblesses distinctes :
  ne les regroupe pas.
- Ne regroupe jamais par simple proximité de thème (« sécurité des accès ») : il
  faut la même faiblesse concrète.
- Un groupe contient au moins deux écarts. Les écarts sans équivalent ne figurent
  dans aucun groupe.
- Pour chaque groupe, propose une formulation unique et claire de la faiblesse
  (merged_weakness), en français, et explique en une phrase pourquoi c'est la
  même faiblesse (reason).
- Dans le doute, ne regroupe pas : un écart perdu est plus grave qu'un doublon.

Réponds uniquement au format structuré demandé.
"""


class GapGroupProposal(BaseModel):
    """A set of gap_ids the model believes describe one and the same weakness."""

    gap_ids: list[str] = Field(default_factory=list)
    merged_weakness: str = ""
    reason: str = ""


class GapGroupBatch(BaseModel):
    groups: list[GapGroupProposal] = Field(default_factory=list)


class GapConsolidationRunner(Protocol):
    def propose_groups(self, gaps: list[BaselineGap]) -> list[GapGroupProposal]:
        ...


def _batches(gaps: list[BaselineGap], size: int) -> list[list[BaselineGap]]:
    return [gaps[i:i + size] for i in range(0, len(gaps), size)]


class AgnoGapConsolidationRunner:
    """Concrete GapConsolidationRunner backed by Agno + OpenRouter."""

    def __init__(self, model=None, *, max_attempts: int = 4, base_delay: float = 3.0, progress=print) -> None:
        self._model = model or get_model()
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._progress = progress

    def propose_groups(self, gaps: list[BaselineGap]) -> list[GapGroupProposal]:
        from agno.agent import Agent  # noqa: PLC0415
        import json

        proposals: list[GapGroupProposal] = []
        batches = _batches(gaps, MAX_GAPS_PER_CALL)
        for index, batch in enumerate(batches, 1):
            listing = json.dumps(
                [
                    {
                        "gap_id": g.gap_id,
                        "weakness": g.weakness,
                        "frameworks": g.frameworks,
                    }
                    for g in batch
                ],
                ensure_ascii=False, indent=2,
            )
            prompt = (
                "Voici les écarts relevés. Regroupe ceux qui décrivent la même faiblesse "
                "réelle, ou renvoie une liste vide s'il n'y a aucun doublon.\n\n"
                f"ÉCARTS :\n{listing}"
            )
            what = "consolidation des écarts"
            if len(batches) > 1:
                what += f" (lot {index}/{len(batches)})"
            try:
                batch_result = run_structured(
                    lambda: Agent(model=self._model, instructions=_SYSTEM,
                                  output_schema=GapGroupBatch, markdown=False),
                    prompt, GapGroupBatch, what=what,
                    max_attempts=self._max_attempts, base_delay=self._base_delay,
                    progress=self._progress,
                )
            except StructuredCallFailed as exc:
                # No proposals rather than a guess: gaps simply stay separate.
                self._progress(f"   (consolidation indisponible : {str(exc)[:120]})")
                continue
            proposals.extend(batch_result.groups)
        return proposals


def valid_groups(
    proposals: list[GapGroupProposal], gaps: list[BaselineGap]
) -> list[GapGroupProposal]:
    """Keep only proposals that name at least two real, distinct, not-yet-used gaps.

    Guards against a model inventing gap ids or claiming the same gap in two
    groups, which would silently drop a finding.
    """
    known = {g.gap_id for g in gaps}
    used: set[str] = set()
    kept: list[GapGroupProposal] = []
    for proposal in proposals:
        ids: list[str] = []
        for gap_id in proposal.gap_ids:
            if gap_id in known and gap_id not in used and gap_id not in ids:
                ids.append(gap_id)
        if len(ids) < 2:
            continue
        used.update(ids)
        kept.append(proposal.model_copy(update={"gap_ids": ids}))
    return kept


def consolidate(gaps: list[BaselineGap], groups: list[GapGroupProposal]) -> list[BaselineGap]:
    """Apply auditor-confirmed groups: one gap per weakness, listing every control.

    Gaps in no group pass through untouched, in their original order.
    """
    by_id = {g.gap_id: g for g in gaps}
    replacement: dict[str, BaselineGap] = {}
    absorbed: set[str] = set()

    for group in groups:
        members = [by_id[i] for i in group.gap_ids if i in by_id]
        if len(members) < 2:
            continue
        first = members[0]

        controls: list[ControlReference] = []
        seen: set[tuple[str, str]] = set()
        categories: set[str] = set()
        evidences: list[str] = []
        for member in members:
            for control in member.controls:
                key = (control.framework, control.control_id)
                if key not in seen:
                    seen.add(key)
                    controls.append(control)
            categories.update(member.risk_categories)
            if member.evidence_quote and member.evidence_quote not in evidences:
                evidences.append(member.evidence_quote)

        replacement[first.gap_id] = first.model_copy(update={
            "weakness": (group.merged_weakness or "").strip() or first.weakness,
            "controls": controls,
            "risk_categories": sorted(categories),
            "evidence_quote": " | ".join(evidences),
        })
        absorbed.update(m.gap_id for m in members[1:])

    return [replacement.get(g.gap_id, g) for g in gaps if g.gap_id not in absorbed]
