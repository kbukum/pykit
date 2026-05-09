"""Explicit skill registry and provider contracts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_skill.loader import SkillPack


@runtime_checkable
class Provider(Protocol):
    """Source of skill packs; registered explicitly at composition time."""

    def list(self) -> list[SkillPack]: ...


@runtime_checkable
class Registry(Protocol):
    """Skill registry protocol."""

    def register(self, provider: Provider) -> None: ...

    def add(self, pack: SkillPack) -> None: ...

    def get(self, name: str) -> SkillPack | None: ...

    def list(self) -> list[SkillPack]: ...


class InMemoryRegistry:
    """Default explicit in-memory skill registry."""

    def __init__(self) -> None:
        self._packs: dict[str, SkillPack] = {}

    def register(self, provider: Provider) -> None:
        for pack in provider.list():
            self.add(pack)

    def add(self, pack: SkillPack) -> None:
        name = pack.manifest.name
        if name in self._packs:
            raise ValueError(f"skill already registered: {name!r}")
        self._packs[name] = pack

    def get(self, name: str) -> SkillPack | None:
        return self._packs.get(name)

    def list(self) -> list[SkillPack]:
        return list(self._packs.values())
