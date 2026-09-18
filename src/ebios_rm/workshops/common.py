"""What every atelier needs in the same shape, defined once (conception §2, §9, §19).

Three things repeat from atelier to atelier, and repeated them the copies drifted:

* ``ElementEcarteBase`` — something the atelier set aside, with the reason. Nothing
  is ever dropped silently (§16 « supprimer un élément écarté sans enregistrer la
  raison » is a forbidden design error); the codes belong to each atelier, the
  shape and the reason lookup belong here.
* ``AtelierAlert`` — a defect found in the *previous* atelier's output. Raised for
  the auditor, never repaired: « erreur de donnée n'est pas erreur de
  raisonnement » (white-box §4).
* ``AtelierDataError`` — what stops an atelier when one of those alerts is
  blocking, rather than reasoning on a result that does not hold.

The JSON written to the mission database is unchanged: the field names are the
ones the ateliers already stored.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel


class ElementEcarteBase(BaseModel):
    """A candidate that did not make it, and why (§16, §17, §19).

    Subclass it per atelier with that atelier's ``LABELS`` — the reason codes are
    the atelier's vocabulary, so « doublon » does not read the same in atelier 2
    (a source de risque already retained) as in atelier 3 (a second scenario on
    one couple).
    """

    LABELS: ClassVar[dict[str, str]] = {}

    type: str          # what kind of element: 'source_risque', 'scenario', 'analyse'...
    reference: str     # its id when it had one, otherwise the proposed label
    libelle: str = ""
    raison: str        # a code of the atelier's own list
    detail: str = ""

    @property
    def raison_label(self) -> str:
        """The reason as a sentence for the auditor — never a bare code."""
        return self.LABELS.get(self.raison, self.raison)


class AtelierAlert(BaseModel):
    """A defect in the output of the atelier upstream (white-box §4, conception §2).

    Produced while building the next atelier's input, never repaired there: a
    reference that points at nothing is fixed where it was written, or the defect
    travels on wearing a new atelier's id.
    """

    reference: str     # the id or the field the problem concerns
    probleme: str
    bloquant: bool = True


class AtelierDataError(RuntimeError):
    """The upstream atelier's output cannot be reasoned on — the run stops (§2).

    ``atelier`` is the number of the atelier at fault, so the message tells the
    auditor where to go and fix it.
    """

    def __init__(self, atelier: int, alerts) -> None:
        super().__init__(
            f"L'atelier {atelier} comporte des anomalies bloquantes :\n"
            + "\n".join(f"  - [{a.reference}] {a.probleme}" for a in alerts)
        )
        self.atelier = atelier
        self.alerts = list(alerts)
