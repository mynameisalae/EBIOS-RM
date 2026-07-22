"""Discovers every framework plugin under plugins/frameworks/ (contract in base.py).

Used by:
- the intake form, to pre-fill applicable_frameworks suggestions (conception §12.4);
- db/loader.py, to populate baseline_controls at reference-db-loader startup (§13.3).

Adding a law or standard means dropping a folder here — this module never names
a framework (§12.5).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

FRAMEWORKS_DIR = Path(__file__).parent / "frameworks"


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
