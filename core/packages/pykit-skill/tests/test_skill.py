from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pykit_skill import Loader, Safety, effective_envelope, effective_safety
from pykit_skill.manifest import Manifest


class Env:
    def __init__(self, scopes: tuple[str, ...], safety: Safety) -> None:
        self.scopes = scopes
        self.safety = safety


def test_loader_reads_canonical_yaml_and_hashes_scripts(tmp_path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "kit.skill.yaml"
    (tmp_path / "kit.skill.yaml").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "SKILL.md").write_text("# Demo", encoding="utf-8")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "asset.sh").write_text("echo inert", encoding="utf-8")

    pack = Loader().load(tmp_path)

    assert pack.manifest.schema_version == "1"
    assert pack.manifest.references.prompts[0].name == "summarize"
    assert pack.manifest.requires.capabilities == ["filesystem"]
    assert pack.manifest.human_approval[0].step == "publish"
    assert pack.manifest.budgets is not None
    assert pack.manifest.budgets.max_calls == 2
    assert pack.manifest.signature is not None
    assert pack.manifest.signature.key_id == "key-1"
    assert pack.scripts[0].path == "scripts/asset.sh"
    assert len(pack.scripts[0].sha256) == 64


def test_camel_case_manifest_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        Manifest.model_validate(
            {
                "name": "demo",
                "description": "Demo",
                "version": "0.1.0",
                "references": {"tools": []},
                "humanApproval": [],
            }
        )


def test_effective_safety_and_envelope() -> None:
    manifest = Manifest.model_validate(
        {
            "name": "demo",
            "description": "Demo",
            "version": "0.1.0",
            "references": {"tools": ["write"]},
        }
    )
    declared = {"write": Env(("db:write", "db:read"), Safety.MUTATING)}
    assert effective_safety(manifest, declared) is Safety.MUTATING
    effective = effective_envelope("write", manifest, declared["write"], {"db:read"}, {"db:read", "db:write"})
    assert effective.scopes == ("db:read",)
