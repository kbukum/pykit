"""Tests for pykit_schema."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from pykit_schema import ValidationResult, from_function, from_type, generate, validate

# --- Test models ---


class SimpleModel(BaseModel):
    name: str
    age: int


class AnnotatedModel(BaseModel):
    """A model with field descriptions."""

    query: Annotated[str, Field(description="Search query")]
    max_results: int = Field(default=10, description="Maximum results", ge=1, le=100)


class NestedModel(BaseModel):
    user: SimpleModel
    tags: list[str] = []


# --- Tests: generate ---


class TestGenerate:
    def test_simple_model(self):
        schema = generate(SimpleModel)
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["age"]["type"] == "integer"

    def test_required_fields(self):
        schema = generate(SimpleModel)
        assert "name" in schema["required"]
        assert "age" in schema["required"]

    def test_annotated_model(self):
        schema = generate(AnnotatedModel)
        props = schema["properties"]
        assert props["query"]["description"] == "Search query"
        assert props["max_results"]["default"] == 10

    def test_title_override(self):
        schema = generate(SimpleModel, title="Person")
        assert schema["title"] == "Person"

    def test_description_override(self):
        schema = generate(SimpleModel, description="A person record")
        assert schema["description"] == "A person record"

    def test_nested_model(self):
        schema = generate(NestedModel)
        assert "user" in schema["properties"]
        assert "tags" in schema["properties"]

    def test_optional_with_default(self):
        schema = generate(AnnotatedModel)
        # max_results has a default, so it should NOT be in required
        required = schema.get("required", [])
        assert "query" in required
        assert "max_results" not in required


# --- Tests: from_type ---


class TestFromType:
    def test_basic_type(self):
        schema = from_type(str)
        assert schema["type"] == "string"

    def test_integer_type(self):
        schema = from_type(int)
        assert schema["type"] == "integer"

    def test_list_type(self):
        schema = from_type(list[str])
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "string"

    def test_basemodel_delegates(self):
        schema = from_type(SimpleModel)
        assert schema["type"] == "object"
        assert "name" in schema["properties"]

    def test_title(self):
        schema = from_type(str, title="Query")
        assert schema["title"] == "Query"

    def test_description(self):
        schema = from_type(int, description="Item count")
        assert schema["description"] == "Item count"


# --- Tests: from_function ---


class TestFromFunction:
    def test_simple_function(self):
        def greet(name: str, excited: bool = False) -> str: ...

        schema = from_function(greet)
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "excited" in schema["properties"]
        assert "name" in schema["required"]
        assert "excited" not in schema.get("required", [])

    def test_skips_self_and_ctx(self):
        def handler(self, ctx, query: str) -> str: ...

        schema = from_function(handler)
        assert "self" not in schema.get("properties", {})
        assert "ctx" not in schema.get("properties", {})
        assert "query" in schema["properties"]

    def test_docstring_as_description(self):
        def search(query: str) -> list[str]:
            """Search for items."""

        schema = from_function(search)
        assert schema["description"] == "Search for items."

    def test_explicit_description_overrides_docstring(self):
        def search(query: str) -> list[str]:
            """Search for items."""

        schema = from_function(search, description="Custom description")
        assert schema["description"] == "Custom description"

    def test_title(self):
        def process(data: str) -> None: ...

        schema = from_function(process, title="DataProcessor")
        assert schema["title"] == "DataProcessor"

    def test_no_params(self):
        def noop() -> None: ...

        schema = from_function(noop)
        assert schema["type"] == "object"
        assert schema.get("properties", {}) == {}

    def test_complex_types(self):
        def handler(items: list[str], meta: dict[str, int]) -> None: ...

        schema = from_function(handler)
        assert "items" in schema["properties"]
        assert "meta" in schema["properties"]


# --- Tests: validate ---


class TestValidate:
    def test_valid_object(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"],
        }
        result = validate(schema, {"name": "Alice", "age": 30})
        assert result.valid
        assert result.errors == []

    def test_invalid_missing_required(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        result = validate(schema, {})
        assert not result.valid
        assert len(result.errors) > 0
        assert any("name" in e.message for e in result.errors)

    def test_invalid_wrong_type(self):
        schema = {"type": "object", "properties": {"age": {"type": "integer"}}}
        result = validate(schema, {"age": "not_a_number"})
        assert not result.valid
        assert any("age" in e.path for e in result.errors)

    def test_valid_with_defaults(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "count": {"type": "integer", "default": 10}},
            "required": ["name"],
        }
        result = validate(schema, {"name": "test"})
        assert result.valid

    def test_valid_empty_schema(self):
        result = validate({}, {"anything": "goes"})
        assert result.valid

    def test_invalid_enum(self):
        schema = {"type": "string", "enum": ["a", "b", "c"]}
        result = validate(schema, "d")
        assert not result.valid

    def test_valid_enum(self):
        schema = {"type": "string", "enum": ["a", "b", "c"]}
        result = validate(schema, "a")
        assert result.valid

    def test_nested_object_validation(self):
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }
            },
            "required": ["user"],
        }
        result = validate(schema, {"user": {"name": "Alice"}})
        assert result.valid

        result = validate(schema, {"user": {}})
        assert not result.valid

    def test_array_validation(self):
        schema = {"type": "array", "items": {"type": "string"}}
        assert validate(schema, ["a", "b"]).valid
        assert not validate(schema, ["a", 1]).valid

    def test_multiple_errors(self):
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        }
        result = validate(schema, {})
        assert not result.valid
        assert len(result.errors) >= 2

    def test_validation_result_type(self):
        result = validate({"type": "string"}, "hello")
        assert isinstance(result, ValidationResult)

    def test_error_path_for_root(self):
        result = validate({"type": "string"}, 42)
        assert not result.valid
        assert result.errors[0].path == "$"

    def test_validate_with_generated_schema(self):
        schema = generate(SimpleModel)
        result = validate(schema, {"name": "Alice", "age": 30})
        assert result.valid

        result = validate(schema, {"name": "Alice"})
        assert not result.valid
