"""Reading back what the auditor wrote in the audit annex (conception §20.2).

The annex is generated once, with a blank « Appréciation de l'auditeur » cell for every
abnormal event. The auditor fills some of them in Word; this module — plain code, no
model — detects which cells are no longer empty and hands them on. Only those reach the
model, and only with the part of the mission they concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docx import Document

EVENTS_FIRST_HEADER = "Origine"
APPRAISAL_HEADER = "Appréciation de l'auditeur"
MISSION_ROW_LABEL = "Mission"


class AnnexReadError(ValueError):
    """The file is not an audit annex this code produced, or it cannot be tied to a mission."""


@dataclass(frozen=True)
class Appraisal:
    origin: str
    code: str
    message: str
    text: str


@dataclass(frozen=True)
class AnnexReading:
    mission_id: str
    appraisals: tuple[Appraisal, ...]


def read_appraisals(path: str | Path) -> AnnexReading:
    document = Document(str(path))

    mission_id = ""
    events = None
    for table in document.tables:
        header = [cell.text for cell in table.rows[0].cells]
        if header[:1] == ["Rubrique"]:
            for row in table.rows[1:]:
                if row.cells[0].text == MISSION_ROW_LABEL:
                    mission_id = row.cells[1].text.strip()
        elif header[:1] == [EVENTS_FIRST_HEADER] and header[-1:] == [APPRAISAL_HEADER]:
            events = table

    if not mission_id:
        raise AnnexReadError("Annexe illisible : l'identifiant de la mission est introuvable.")
    if events is None:
        return AnnexReading(mission_id, ())  # an annex without abnormal events has nothing to appraise

    appraisals = []
    for row in events.rows[1:]:
        cells = [cell.text for cell in row.cells]
        if cells[-1].strip():
            appraisals.append(Appraisal(cells[0], cells[1], cells[2], cells[-1].strip()))
    return AnnexReading(mission_id, tuple(appraisals))
