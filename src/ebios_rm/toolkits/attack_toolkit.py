"""Read-only ATT&CK query functions exposed as real Agno tools (conception §10.1, §19).

The first genuine tool call of the project. Ateliers 1 to 4 deliberately avoid
it (free models do not call tools reliably — same reasoning documented in
those ateliers' own agent.py). Atelier 5 is the one place the conception
requires it: get_mitigations_for_technique, called live by the agent for
whichever technique it is currently proposing a measure for.

The tool never touches the database directly. It wraps a MitigationCatalogue
already built for exactly the techniques this mission's scenarios cite
(repositories/attack_repository.py) — so what the tool call returns and what
assessment.py checks afterwards are guaranteed to be the same data, and a
technique outside this mission's scope simply returns an empty list rather
than opening a wider, unaudited query.
"""

from __future__ import annotations

import json
from typing import Callable, List

from agno.tools import Toolkit

from ebios_rm.repositories.attack_repository import MitigationCatalogue


class AttackToolkit(Toolkit):
    """Wraps one pre-built MitigationCatalogue as an Agno tool."""

    def __init__(self, catalogue: MitigationCatalogue, **kwargs) -> None:
        self._catalogue = catalogue
        tools: List[Callable] = [self.get_mitigations_for_technique]
        super().__init__(name="attack_toolkit", tools=tools, **kwargs)

    def get_mitigations_for_technique(self, technique_id: str) -> str:
        """Renvoie les mesures de mitigation ATT&CK réelles et actives pour une technique.

        Appelle cet outil pour CHAQUE identifiant de technique (ex. T1078, T1486)
        cité dans les scénarios avant de proposer une mesure qui s'appuie dessus.
        Un identifiant de mitigation que tu n'as pas obtenu par cet outil ne doit
        jamais apparaître dans mitigation_ids_attck — il serait rejeté.

        Args:
            technique_id (str): L'identifiant de la technique (ex. "T1078", "T1078.002").

        Returns:
            str: JSON — {"technique_id": ..., "mitigations": [{"id": "M1032",
                "name": "Multi-factor Authentication"}, ...]}. Une liste vide
                signifie qu'aucune mitigation active n'existe pour cette
                technique dans ce référentiel — ne pas en inventer.
        """
        mitigations = self._catalogue.by_technique.get(technique_id, ())
        return json.dumps({
            "technique_id": technique_id,
            "mitigations": [{"id": m.mitigation_id, "name": m.name} for m in mitigations],
        }, ensure_ascii=False)
