"""Prompt template engine with ``{{variable}}`` substitution."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


@dataclass
class PromptTemplate:
    """Template with ``{{variable}}`` substitution for LLM prompts.

    Uses ``{{variable_name}}`` syntax to avoid conflicts with JSON braces
    commonly found in prompt text.

    Attributes:
        template: The template string containing ``{{variable}}`` placeholders.
        variables: Default variable values merged with render-time kwargs.
    """

    template: str
    variables: dict[str, str] = field(default_factory=dict)

    def render(self, **kwargs: str) -> str:
        """Render the template with provided variables.

        Variables provided as keyword arguments override defaults.

        Args:
            **kwargs: Variable values to substitute.

        Returns:
            The rendered string.

        Raises:
            KeyError: If a placeholder has no value in defaults or kwargs.
        """
        merged = {**self.variables, **kwargs}

        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in merged:
                raise KeyError(key)
            return merged[key]

        return _VAR_PATTERN.sub(_replace, self.template)

    def with_defaults(self, **kwargs: str) -> PromptTemplate:
        """Return a new template with additional default variables.

        Existing defaults are preserved; new values override on conflict.

        Args:
            **kwargs: Additional default variable values.

        Returns:
            A new ``PromptTemplate`` with the merged defaults.
        """
        merged = {**self.variables, **kwargs}
        return PromptTemplate(template=self.template, variables=merged)


class TemplateRegistry:
    """Registry of named prompt templates."""

    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}

    def register(self, name: str, template: PromptTemplate) -> None:
        """Register a template under the given name.

        Args:
            name: Unique name for the template.
            template: The prompt template to register.
        """
        self._templates[name] = template

    def get(self, name: str) -> PromptTemplate:
        """Retrieve a registered template by name.

        Args:
            name: The template name.

        Returns:
            The registered ``PromptTemplate``.

        Raises:
            KeyError: If no template is registered under the given name.
        """
        if name not in self._templates:
            raise KeyError(name)
        return self._templates[name]

    def render(self, name: str, /, **kwargs: str) -> str:
        """Look up a template by name and render it.

        Args:
            name: The template name.
            **kwargs: Variable values to substitute.

        Returns:
            The rendered string.

        Raises:
            KeyError: If the template name is unknown or a variable is missing.
        """
        return self.get(name).render(**kwargs)
