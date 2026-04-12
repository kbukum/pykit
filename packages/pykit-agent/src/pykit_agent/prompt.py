"""Prompt templates and composable prompt building."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class PromptTemplate:
    """Template with ``{{variable}}`` interpolation.

    Variables are delimited by double curly braces.  Missing keys are
    left as-is so callers can layer multiple render passes.
    """

    name: str
    template: str

    _VAR_RE: re.Pattern[str] = field(
        default=re.compile(r"\{\{(\w+)\}\}"),
        init=False,
        repr=False,
        compare=False,
    )

    def render(self, data: dict[str, str]) -> str:
        """Render the template, substituting ``{{key}}`` with *data* values."""

        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            return data.get(key, match.group(0))

        return self._VAR_RE.sub(_replace, self.template)


@dataclass
class _Section:
    name: str
    content: str


@dataclass
class PromptBuilder:
    """Fluent builder for composing prompts from named sections."""

    _sections: list[_Section] = field(default_factory=list, init=False)
    _sep: str = field(default="\n\n", init=False)

    def section(self, name: str, content: str) -> PromptBuilder:
        """Append a named section."""
        self._sections.append(_Section(name=name, content=content))
        return self

    def section_if(self, condition: bool, name: str, content: str) -> PromptBuilder:
        """Append a section only when *condition* is truthy."""
        if condition:
            self._sections.append(_Section(name=name, content=content))
        return self

    def separator(self, sep: str) -> PromptBuilder:
        """Set the separator used between sections (default ``\\n\\n``)."""
        self._sep = sep
        return self

    def build(self) -> str:
        """Join all sections with the configured separator."""
        return self._sep.join(s.content for s in self._sections)
