"""Tests for prompt templates and builder."""

from __future__ import annotations

from pykit_agent.prompt import PromptBuilder, PromptTemplate


class TestPromptTemplate:
    """PromptTemplate rendering."""

    def test_simple_substitution(self) -> None:
        t = PromptTemplate(name="greet", template="Hello, {{name}}!")
        assert t.render({"name": "Alice"}) == "Hello, Alice!"

    def test_multiple_variables(self) -> None:
        t = PromptTemplate(
            name="intro",
            template="You are {{role}}. Your task is {{task}}.",
        )
        result = t.render({"role": "a helpful assistant", "task": "answering questions"})
        assert result == "You are a helpful assistant. Your task is answering questions."

    def test_missing_key_left_as_is(self) -> None:
        t = PromptTemplate(name="partial", template="Hi {{name}}, your id is {{id}}")
        assert t.render({"name": "Bob"}) == "Hi Bob, your id is {{id}}"

    def test_empty_data(self) -> None:
        t = PromptTemplate(name="empty", template="No vars here")
        assert t.render({}) == "No vars here"

    def test_repeated_variable(self) -> None:
        t = PromptTemplate(name="rep", template="{{x}} and {{x}}")
        assert t.render({"x": "A"}) == "A and A"

    def test_empty_template(self) -> None:
        t = PromptTemplate(name="blank", template="")
        assert t.render({"any": "value"}) == ""


class TestPromptBuilder:
    """PromptBuilder composable sections."""

    def test_single_section(self) -> None:
        result = PromptBuilder().section("intro", "You are an AI.").build()
        assert result == "You are an AI."

    def test_multiple_sections(self) -> None:
        result = (
            PromptBuilder()
            .section("role", "You are a coder.")
            .section("rules", "Be concise.")
            .build()
        )
        assert result == "You are a coder.\n\nBe concise."

    def test_custom_separator(self) -> None:
        result = (
            PromptBuilder()
            .separator("\n---\n")
            .section("a", "Section A")
            .section("b", "Section B")
            .build()
        )
        assert result == "Section A\n---\nSection B"

    def test_section_if_true(self) -> None:
        result = (
            PromptBuilder()
            .section("base", "Base")
            .section_if(True, "extra", "Extra")
            .build()
        )
        assert result == "Base\n\nExtra"

    def test_section_if_false(self) -> None:
        result = (
            PromptBuilder()
            .section("base", "Base")
            .section_if(False, "extra", "Extra")
            .build()
        )
        assert result == "Base"

    def test_empty_builder(self) -> None:
        assert PromptBuilder().build() == ""

    def test_fluent_chaining(self) -> None:
        builder = PromptBuilder()
        ret = builder.section("a", "A").section("b", "B").separator("\n")
        assert ret is builder
