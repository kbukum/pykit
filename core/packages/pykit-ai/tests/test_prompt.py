from __future__ import annotations

import pytest

from pykit_ai.prompt import (
    Builder,
    PromptTemplate,
    Registry,
    RenderError,
    Template,
    VariableDecl,
    render,
    validate,
)


def test_template_render_mustache() -> None:
    template = Template(
        name="greet",
        version="1.0.0",
        template="Hello {{ name }}",
        variables=[VariableDecl(name="name")],
    )
    assert template.render({"name": "Ada"}) == "Hello Ada"


def test_template_missing_variable() -> None:
    template = Template(
        name="greet",
        version="1.0.0",
        template="Hello {{name}}",
        variables=[VariableDecl(name="name")],
    )
    with pytest.raises(RenderError):
        template.render({})


def test_render_rejects_undeclared_values() -> None:
    with pytest.raises(RenderError, match="undeclared"):
        render("Hello {{name}}", {"name": "Ada", "extra": "no"})


def test_registry_register_lookup_versions() -> None:
    registry = Registry()
    registry.register("greet", "1.0.0", "Hello {{name}}")
    registry.register("greet", "1.2.0", "Hi {{name}}")

    assert registry.lookup("greet", "1.0.0").render({"name": "Ada"}) == "Hello Ada"
    assert registry.lookup_latest("greet").version == "1.2.0"
    assert registry.versions("greet") == ["1.0.0", "1.2.0"]
    assert [(item.name, item.version) for item in registry.list()] == [
        ("greet", "1.0.0"),
        ("greet", "1.2.0"),
    ]


def test_validation_finds_undeclared_unused_and_duplicate() -> None:
    findings = validate(
        PromptTemplate(
            name="bad",
            version="1.0.0",
            template="Hello {{name}} {{missing}}",
            variables=[VariableDecl(name="name"), VariableDecl(name="name"), VariableDecl(name="unused")],
        )
    )
    assert {finding.code for finding in findings} == {"undeclared", "unused", "duplicate"}


def test_builder_render() -> None:
    expected = "## Role\nBe helpful\n\n## Task\nAnswer"
    assert Builder().add("Role", "Be helpful").add("Task", "Answer").render() == expected
