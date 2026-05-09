"""Filesystem skill loader."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from pykit_skill.manifest import Manifest, ScriptAsset

MANIFEST_FILE = "kit.skill.yaml"
SKILL_FILE = "SKILL.md"


@dataclass(frozen=True, slots=True)
class SkillPack:
    """Loaded skill pack with progressive-disclosure body and inert assets."""

    root: Path
    manifest: Manifest
    body: str
    scripts: tuple[ScriptAsset, ...] = ()


class Loader:
    """Load skill metadata and bodies from explicit filesystem paths."""

    def load_manifest(self, path: str | Path) -> Manifest:
        skill_path = Path(path)
        manifest_path = skill_path / MANIFEST_FILE
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError("skill manifest must be a YAML mapping")
        return Manifest.model_validate(raw)

    def load(self, path: str | Path) -> SkillPack:
        skill_path = Path(path)
        manifest = self.load_manifest(skill_path)
        body = (skill_path / SKILL_FILE).read_text(encoding="utf-8")
        scripts = tuple(_script_assets(skill_path / "scripts", skill_path))
        return SkillPack(root=skill_path, manifest=manifest, body=body, scripts=scripts)


def _script_assets(scripts_dir: Path, root: Path) -> list[ScriptAsset]:
    if not scripts_dir.exists():
        return []
    assets: list[ScriptAsset] = []
    for item in sorted(path for path in scripts_dir.rglob("*") if path.is_file()):
        digest = hashlib.sha256(item.read_bytes()).hexdigest()
        assets.append(ScriptAsset(path=str(item.relative_to(root)), sha256=digest))
    return assets
