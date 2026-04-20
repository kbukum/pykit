"""Tests for PromptTemplate and TemplateRegistry."""

from __future__ import annotations

import pytest

from pykit_llm.template import PromptTemplate, TemplateRegistry

# ---------------------------------------------------------------------------
# PromptTemplate
# ---------------------------------------------------------------------------


class TestPromptTemplate:
    def test_render_simple(self) -> None:
        t = PromptTemplate(template="Hello {{name}}!")
        assert t.render(name="World") == "Hello World!"

    def test_render_multiple_vars(self) -> None:
        t = PromptTemplate(template="{{greeting}} {{name}}, you are {{role}}.")
        result = t.render(greeting="Hi", name="Alice", role="admin")
        assert result == "Hi Alice, you are admin."

    def test_render_with_defaults(self) -> None:
        t = PromptTemplate(
            template="{{greeting}} {{name}}!",
            variables={"greeting": "Hello"},
        )
        assert t.render(name="Bob") == "Hello Bob!"

    def test_render_kwargs_override_defaults(self) -> None:
        t = PromptTemplate(
            template="{{greeting}} {{name}}!",
            variables={"greeting": "Hello", "name": "default"},
        )
        assert t.render(name="Override") == "Hello Override!"

    def test_render_missing_var_raises_key_error(self) -> None:
        t = PromptTemplate(template="{{name}} is {{status}}")
        with pytest.raises(KeyError, match="status"):
            t.render(name="Alice")

    def test_render_no_vars(self) -> None:
        t = PromptTemplate(template="No variables here.")
        assert t.render() == "No variables here."

    def test_render_preserves_json_braces(self) -> None:
        t = PromptTemplate(template='Output as JSON: {"key": "{{value}}"}')
        assert t.render(value="test") == 'Output as JSON: {"key": "test"}'

    def test_render_repeated_var(self) -> None:
        t = PromptTemplate(template="{{x}} and {{x}} again")
        assert t.render(x="hello") == "hello and hello again"

    def test_with_defaults_returns_new_template(self) -> None:
        t1 = PromptTemplate(template="{{a}} {{b}}", variables={"a": "1"})
        t2 = t1.with_defaults(b="2")
        assert t2.render() == "1 2"
        # Original is unchanged
        assert t1.variables == {"a": "1"}

    def test_with_defaults_overrides_existing(self) -> None:
        t1 = PromptTemplate(template="{{x}}", variables={"x": "old"})
        t2 = t1.with_defaults(x="new")
        assert t2.render() == "new"


# ---------------------------------------------------------------------------
# TemplateRegistry
# ---------------------------------------------------------------------------


class TestTemplateRegistry:
    def test_register_and_get(self) -> None:
        reg = TemplateRegistry()
        t = PromptTemplate(template="Hello {{name}}!")
        reg.register("greet", t)
        assert reg.get("greet") is t

    def test_get_unknown_raises_key_error(self) -> None:
        reg = TemplateRegistry()
        with pytest.raises(KeyError):
            reg.get("nonexistent")

    def test_render(self) -> None:
        reg = TemplateRegistry()
        reg.register("greet", PromptTemplate(template="Hi {{name}}!"))
        assert reg.render("greet", name="Alice") == "Hi Alice!"

    def test_render_unknown_raises_key_error(self) -> None:
        reg = TemplateRegistry()
        with pytest.raises(KeyError):
            reg.render("missing", name="x")

    def test_register_overwrites(self) -> None:
        reg = TemplateRegistry()
        reg.register("t", PromptTemplate(template="v1"))
        reg.register("t", PromptTemplate(template="v2"))
        assert reg.render("t") == "v2"
