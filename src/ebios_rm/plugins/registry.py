"""Discovers the data-only plugins shipped under plugins/ — nothing here names a
referential or a methodology by hand.

Two families, deliberately kept apart:

- ``frameworks/`` — compliance referentials (contract in base.py). Used by the
  intake form to pre-fill applicable_frameworks (conception §12.4) and by
  db/loader.py to populate baseline_controls (§13.3).
- ``ebios_bases/`` — the approved EBIOS RM SR/OV base of atelier 2 (white-box §3):
  the catalogue of risk-source categories and objective finalités the agent may
  select from. It is methodological knowledge, not organisational data and not a
  compliance referential, so it is never loaded into baseline_controls: doing so
  would make it show up as a declarable framework in the intake form.

Adding a law, a standard, or a new EBIOS RM version means dropping a folder in —
no code change (§12.5).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

FRAMEWORKS_DIR = Path(__file__).parent / "frameworks"
EBIOS_BASES_DIR = Path(__file__).parent / "ebios_bases"


@dataclass(frozen=True)
class FrameworkPlugin:
    """One discovered framework plugin (manifest + its control rows)."""

    id: str
    name: str
    framework_version: str
    legal_nature: str
    has_legal_impact_provisions: bool
    default_suggested: bool
    controls: list[dict]
    path: Path


def _load_one(folder: Path) -> FrameworkPlugin:
    manifest = yaml.safe_load((folder / "manifest.yaml").read_text(encoding="utf-8")) or {}
    controls_path = folder / "controls.json"
    controls = json.loads(controls_path.read_text(encoding="utf-8")) if controls_path.exists() else []
    return FrameworkPlugin(
        id=str(manifest["id"]),
        name=str(manifest.get("name", manifest["id"])),
        framework_version=str(manifest.get("framework_version", "")),
        legal_nature=str(manifest.get("legal_nature", "")).strip(),
        has_legal_impact_provisions=bool(manifest.get("has_legal_impact_provisions", False)),
        default_suggested=bool(manifest.get("default_suggested", False)),
        controls=controls,
        path=folder,
    )


def discover_frameworks(frameworks_dir: Path | None = None) -> list[FrameworkPlugin]:
    """Every plugin folder with a manifest.yaml, excluding the _template scaffold."""
    base = frameworks_dir or FRAMEWORKS_DIR
    plugins: list[FrameworkPlugin] = []
    for folder in sorted(base.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        if not (folder / "manifest.yaml").exists():
            continue
        plugins.append(_load_one(folder))
    return plugins


def default_suggested_frameworks(frameworks_dir: Path | None = None) -> list[str]:
    """Framework ids pre-filled (editable) in org_context_form.applicable_frameworks (conception §12.4)."""
    return [p.id for p in discover_frameworks(frameworks_dir) if p.default_suggested]


# --- EBIOS RM SR/OV base (white-box atelier 2 §3, §6) ---

@dataclass(frozen=True)
class SourceRisqueCategory:
    """One risk-source category of the approved base — a motivated actor category (§8, §17)."""

    id: str
    libelle: str
    definition: str
    finalites_typiques: list[str]   # objective finalité ids this actor usually pursues
    indices_pertinence: list[str]   # what makes this actor plausible for an organisation


@dataclass(frozen=True)
class ObjectifViseFinalite:
    """One objective finalité of the approved base — an end, never a technique (§9)."""

    id: str
    libelle: str
    definition: str
    exemples: list[str]


@dataclass(frozen=True)
class EbiosBase:
    """The approved SR/OV base handed to atelier 2 (white-box §3).

    ``verified_against_official_guide`` travels with the data on purpose: until a
    human has checked the wording against the adopted official EBIOS RM guide
    (§22), the quality report says so rather than letting the claim disappear.
    """

    id: str
    name: str
    ebios_version: str
    verified_against_official_guide: bool
    sources_risque: list[SourceRisqueCategory]
    objectifs_vises: list[ObjectifViseFinalite]

    def source_categories(self) -> dict[str, SourceRisqueCategory]:
        return {c.id: c for c in self.sources_risque}

    def objectif_finalites(self) -> dict[str, ObjectifViseFinalite]:
        return {f.id: f for f in self.objectifs_vises}


def _load_json_list(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _load_base(folder: Path) -> EbiosBase:
    manifest = yaml.safe_load((folder / "manifest.yaml").read_text(encoding="utf-8")) or {}
    return EbiosBase(
        id=str(manifest["id"]),
        name=str(manifest.get("name", manifest["id"])),
        ebios_version=str(manifest.get("ebios_version", "")),
        verified_against_official_guide=bool(manifest.get("verified_against_official_guide", False)),
        sources_risque=[
            SourceRisqueCategory(
                id=str(c["id"]),
                libelle=str(c.get("libelle", c["id"])),
                definition=str(c.get("definition", "")),
                finalites_typiques=list(c.get("finalites_typiques", [])),
                indices_pertinence=list(c.get("indices_pertinence", [])),
            )
            for c in _load_json_list(folder / "sources_risque.json")
        ],
        objectifs_vises=[
            ObjectifViseFinalite(
                id=str(f["id"]),
                libelle=str(f.get("libelle", f["id"])),
                definition=str(f.get("definition", "")),
                exemples=list(f.get("exemples", [])),
            )
            for f in _load_json_list(folder / "objectifs_vises.json")
        ],
    )


def discover_ebios_bases(bases_dir: Path | None = None) -> list[EbiosBase]:
    """Every SR/OV base folder with a manifest.yaml, excluding the _template scaffold."""
    base = bases_dir or EBIOS_BASES_DIR
    if not base.exists():
        return []
    return [
        _load_base(folder)
        for folder in sorted(base.iterdir())
        if folder.is_dir() and not folder.name.startswith("_") and (folder / "manifest.yaml").exists()
    ]


def load_ebios_base(base_id: str | None = None, bases_dir: Path | None = None) -> EbiosBase:
    """The SR/OV base atelier 2 runs against.

    Raises rather than returning an empty base: an atelier 2 with no approved
    catalogue would let the model invent its own categories, which is exactly what
    white-box §6 forbids.
    """
    bases = discover_ebios_bases(bases_dir)
    if not bases:
        raise ValueError(f"Aucune base EBIOS RM SR/OV trouvée dans {bases_dir or EBIOS_BASES_DIR}.")
    if base_id is None:
        return bases[0]
    for base in bases:
        if base.id == base_id:
            return base
    raise ValueError(f"Base EBIOS RM SR/OV inconnue : '{base_id}'. Disponibles : {[b.id for b in bases]}.")
