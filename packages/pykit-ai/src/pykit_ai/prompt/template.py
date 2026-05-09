"""Prompt template primitives."""

from __future__ import annotations

import builtins
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from pykit_ai.message import SystemMessage

from packaging.version import Version
from pydantic import BaseModel, ConfigDict, Field

from pykit_schema import ValidationResult
from pykit_schema import validate as validate_schema

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class RenderError(ValueError):
    """Raised when a prompt cannot be rendered or validated."""


class VariableDecl(BaseModel):
    """Typed prompt variable declaration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    type: str = "string"
    required: bool = True
    default: object | None = None


class ValidationFinding(BaseModel):
    """Prompt template validation finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Literal["undeclared", "unused", "duplicate"]
    message: str
    variable: str


class PromptTemplate(BaseModel):
    """A versioned prompt template with typed variables and optional output schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    template: str
    variables: list[VariableDecl] = Field(default_factory=list)
    output_schema: dict[str, Any] | None = None
    description: str = ""

    def render(self, values: dict[str, object]) -> str:
        """Render with mustache-style variables and strict declaration checks."""
        findings = validate(self)
        if findings:
            raise RenderError("; ".join(f.message for f in findings))
        declarations = {decl.name: decl for decl in self.variables}
        extra = sorted(set(values) - set(declarations))
        if extra:
            raise RenderError(f"undeclared prompt variables: {', '.join(extra)}")
        rendered_values: dict[str, object] = {}
        missing: list[str] = []
        for name, decl in declarations.items():
            if name in values:
                rendered_values[name] = values[name]
            elif decl.default is not None:
                rendered_values[name] = decl.default
            elif decl.required:
                missing.append(name)
        if missing:
            raise RenderError(f"missing prompt variables: {', '.join(missing)}")
        return render(self.template, rendered_values)

    def validate_output(self, value: object) -> ValidationResult:
        """Validate structured output against the optional output schema."""
        if self.output_schema is None:
            return ValidationResult(valid=True)
        return validate_schema(self.output_schema, value)

    def render_to_message(self, data: object) -> SystemMessage:
        from pykit_ai.message import SystemMessage

        if not isinstance(data, dict):
            raise RenderError("prompt template render_to_message requires a mapping")
        return SystemMessage(content=self.render(data))


Template = PromptTemplate


def placeholders(template: str) -> list[str]:
    """Return placeholder names in occurrence order."""
    return [match.group(1) for match in _PLACEHOLDER_RE.finditer(template)]


def render(template: str, variables: dict[str, object]) -> str:
    """Render ``{{var}}`` placeholders from the provided variable dictionary."""
    used = set(placeholders(template))
    missing = sorted(used - set(variables))
    if missing:
        raise RenderError(f"missing prompt variables: {', '.join(missing)}")
    extra = sorted(set(variables) - used)
    if extra:
        raise RenderError(f"undeclared prompt variables: {', '.join(extra)}")

    def replace(match: re.Match[str]) -> str:
        return str(variables[match.group(1)])

    return _PLACEHOLDER_RE.sub(replace, template)


def validate(template: PromptTemplate | str) -> list[ValidationFinding]:
    """Validate placeholder declarations for a prompt template."""
    if isinstance(template, str):
        return []
    found = placeholders(template.template)
    declared = [variable.name for variable in template.variables]
    findings: list[ValidationFinding] = []
    for name in sorted(set(found) - set(declared)):
        findings.append(
            ValidationFinding(
                code="undeclared", variable=name, message=f"placeholder {name!r} is not declared"
            )
        )
    for name in sorted(set(declared) - set(found)):
        findings.append(
            ValidationFinding(code="unused", variable=name, message=f"variable {name!r} is not used")
        )
    duplicates = sorted({name for name in declared if declared.count(name) > 1})
    for name in duplicates:
        findings.append(
            ValidationFinding(code="duplicate", variable=name, message=f"variable {name!r} is duplicated")
        )
    return findings


@dataclass(frozen=True, slots=True)
class PromptIdentity:
    """Registered prompt identity."""

    name: str
    version: str


@dataclass(slots=True)
class Registry:
    """Explicit in-memory registry for versioned prompt templates."""

    _templates: dict[tuple[str, str], PromptTemplate] = field(default_factory=dict)

    def register(
        self,
        name: str,
        version: str,
        template: str,
        output_schema: dict[str, Any] | None = None,
    ) -> PromptTemplate:
        """Register a prompt template by name and semver version."""
        parsed_version = str(Version(version))
        key = (name, parsed_version)
        if key in self._templates:
            raise ValueError(f"prompt template already registered: {name!r} {parsed_version!r}")
        prompt = PromptTemplate(
            name=name,
            version=parsed_version,
            template=template,
            variables=[VariableDecl(name=name) for name in dict.fromkeys(placeholders(template))],
            output_schema=output_schema,
        )
        self._templates[key] = prompt
        return prompt

    def lookup(self, name: str, version: str) -> PromptTemplate:
        """Lookup an exact prompt template version."""
        key = (name, str(Version(version)))
        try:
            return self._templates[key]
        except KeyError as exc:
            raise KeyError(f"unknown prompt template: {name!r} {version!r}") from exc

    def lookup_latest(self, name: str) -> PromptTemplate:
        """Lookup the highest semver version registered for a prompt name."""
        versions = self.versions(name)
        if not versions:
            raise KeyError(f"unknown prompt template: {name!r}")
        return self.lookup(name, versions[-1])

    def list(self) -> builtins.list[PromptIdentity]:
        """List registered prompt identities in stable order."""
        return [PromptIdentity(name, version) for name, version in sorted(self._templates)]

    def versions(self, name: str) -> builtins.list[str]:
        """List semver-sorted versions for a prompt name."""
        versions: builtins.list[str] = [
            version for prompt_name, version in self._templates if prompt_name == name
        ]
        return [str(version) for version in sorted(Version(version) for version in versions)]


TemplateRegistry = Registry
