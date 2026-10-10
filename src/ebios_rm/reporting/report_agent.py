"""The model-facing half of the mission report (conception §20.1, §20.2; §3.2, §10.1).

One call per section: the model gets the section's brief and only the part of the
mission state that section needs, and answers with short statements, each citing the
exact fields it rests on. Whether those citations hold is decided in code
(mission_report.check_statement), never by the model.

Agno is imported lazily (agent_runtime), so everything else runs and tests without it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from ebios_rm.agent_runtime import AgnoRunner


@dataclass(frozen=True)
class SectionSpec:
    key: str
    title: str
    ateliers: tuple[int, ...]  # the approved outputs this section is allowed to read
    brief: str


class Statement(BaseModel):
    text: str = ""
    sources: list[str] = Field(default_factory=list)


class SectionDraft(BaseModel):
    statements: list[Statement] = Field(default_factory=list)


class Refusal(BaseModel):
    """A statement the code refused, handed back to the model with the reason (one correction round)."""

    text: str
    sources: list[str]
    reason: str


class ReportRunner(Protocol):
    def write_section(self, spec: SectionSpec, state: dict) -> SectionDraft: ...

    def revise_section(self, spec: SectionSpec, state: dict, refused: list[Refusal]) -> SectionDraft: ...


SYSTEM_INSTRUCTIONS = """\
Tu rédiges une section du rapport de mission d'une analyse de risque EBIOS RM, destiné à la direction de \
l'organisation analysée. Tu reçois les données approuvées de l'étude (JSON) et le brief de la section.

Règles absolues :
1. N'écris que ce que les données établissent. Aucune information extérieure à l'étude, aucune \
recommandation qui ne figure pas dans les données.
2. Chaque affirmation tient en une ou deux phrases courtes, et porte dans `sources` les chemins EXACTS des \
champs qui l'établissent. Un chemin commence toujours par la clé racine (organisation, echelles, w1...w5) et se \
lit clé.clé.indice, le premier élément d'une liste ayant l'indice 0 (exemple : w5.risques.0.niveau_risque). \
Cite le champ précis ; pour compter ou énumérer, cite la liste concernée. Jamais un atelier entier.
3. Cite aussi le champ `id` de chaque objet que tu nommes (risque, mesure, scénario, bien essentiel...) dans \
`sources`, mais dans la phrase nomme-le naturellement (« le risque R1 »), sans écrire « (id : R1) ». \
Ne mentionne aucun identifiant, niveau ou chiffre absent des champs que tu cites.
4. Les échelles (gravité, vraisemblance, niveau de risque) figurent déjà en tête du rapport : ne les répète pas \
dans chaque phrase. Cite simplement le champ qui porte le niveau.
5. Ton professionnel et clair, en français, sans jargon inutile. Une direction doit comprendre sans lire le JSON.
6. Si les données ne permettent pas de couvrir un point du brief, n'écris rien sur ce point : ne comble pas.
"""


def section_prompt(spec: SectionSpec, state: dict) -> str:
    return (
        f"<section>\nTitre : {spec.title}\nBrief : {spec.brief}\n</section>\n\n"
        f"<donnees>\n{json.dumps(state, ensure_ascii=False, indent=1)}\n</donnees>\n\n"
        "Rédige les affirmations de cette section. Pour chacune : `text` et `sources` (chemins exacts dans <donnees>)."
    )


def revision_prompt(spec: SectionSpec, state: dict, refused: list[Refusal]) -> str:
    items = "\n".join(
        f"{i}. « {r.text} » — sources citées : {r.sources} — refusée parce que : {r.reason}"
        for i, r in enumerate(refused, 1)
    )
    return (
        f"<section>\nTitre : {spec.title}\nBrief : {spec.brief}\n</section>\n\n"
        f"<donnees>\n{json.dumps(state, ensure_ascii=False, indent=1)}\n</donnees>\n\n"
        f"<refusees>\n{items}\n</refusees>\n\n"
        "Un contrôle automatique a refusé les affirmations ci-dessus. Renvoie exactement une entrée par "
        "affirmation refusée, dans le même ordre :\n"
        "- si les données l'établissent, réécris-la avec des `sources` corrigées (chemin complet depuis la racine, "
        "et le champ `id` de chaque objet nommé) ;\n"
        "- sinon, renvoie une entrée dont `text` est vide : l'affirmation est abandonnée."
    )


class AgnoReportRunner(AgnoRunner):
    """Concrete ReportRunner backed by Agno + OpenRouter."""

    INSTRUCTIONS = SYSTEM_INSTRUCTIONS

    def write_section(self, spec: SectionSpec, state: dict) -> SectionDraft:
        return self._run_structured(
            SectionDraft, section_prompt(spec, state), what=f"rapport de mission — {spec.title}",
        )

    def revise_section(self, spec: SectionSpec, state: dict, refused: list[Refusal]) -> SectionDraft:
        return self._run_structured(
            SectionDraft, revision_prompt(spec, state, refused),
            what=f"rapport de mission — {spec.title} (correction)",
        )
