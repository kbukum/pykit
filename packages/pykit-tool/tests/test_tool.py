"""Tests for pykit_tool."""

from __future__ import annotations

import asyncio
import logging

import pytest

from pykit_tool import (
    Annotations,
    Callable,
    Context,
    Definition,
    Registry,
    Result,
    Tool,
    chain,
    error_result,
    json_result,
    text_result,
    tool,
    with_logging,
    with_result_limit,
    with_timeout,
    with_validation,
)

# --- Context ---


class TestContext:
    def test_defaults(self):
        ctx = Context()
        assert ctx.request_id == ""
        assert ctx.tool_use_id == ""
        assert ctx.max_result_size == 0
        assert ctx.metadata == {}
        assert ctx.cancelled is False

    def test_set_get(self):
        ctx = Context()
        ctx.set("user", "alice")
        assert ctx.get("user") == "alice"
        assert ctx.get("missing") is None

    def test_metadata_copy(self):
        ctx = Context()
        ctx.set("key", "value")
        meta = ctx.metadata
        meta["key"] = "changed"
        assert ctx.get("key") == "value"

    def test_cancel(self):
        ctx = Context()
        assert ctx.cancelled is False
        ctx.cancel()
        assert ctx.cancelled is True

    def test_with_fields(self):
        ctx = Context(request_id="req-1", tool_use_id="tu-1", max_result_size=1024)
        assert ctx.request_id == "req-1"
        assert ctx.tool_use_id == "tu-1"
        assert ctx.max_result_size == 1024


# --- Result ---


class TestResult:
    def test_text_result(self):
        r = text_result("hello")
        assert r.content == "hello"
        assert r.is_error is False
        assert r.text() == "hello"

    def test_error_result(self):
        r = error_result("failed")
        assert r.content == "failed"
        assert r.is_error is True

    def test_json_result(self):
        r = json_result({"key": "value"})
        assert r.output == {"key": "value"}
        assert '"key"' in r.text()

    def test_empty_result(self):
        r = Result()
        assert r.text() == ""

    def test_set_meta(self):
        r = Result()
        r.set_meta("duration", 1.5)
        assert r.metadata["duration"] == 1.5

    def test_text_prefers_content(self):
        r = Result(output={"a": 1}, content="custom text")
        assert r.text() == "custom text"

    def test_text_falls_back_to_output(self):
        r = Result(output={"a": 1})
        assert r.text() == '{"a": 1}'


# --- @tool() decorator ---


class TestToolDecorator:
    @pytest.mark.asyncio
    async def test_basic_async_tool(self):
        @tool(description="Add two numbers")
        async def add(a: int, b: int) -> int:
            return a + b

        assert isinstance(add, Tool)
        assert add.definition.name == "add"
        assert add.definition.description == "Add two numbers"
        result = await add.call(Context(), {"a": 1, "b": 2})
        assert isinstance(result, Result)
        assert result.content == "3"

    @pytest.mark.asyncio
    async def test_sync_function_wrapped(self):
        @tool(description="Multiply")
        def multiply(x: int, y: int) -> int:
            return x * y

        result = await multiply.call(Context(), {"x": 3, "y": 4})
        assert result.content == "12"

    @pytest.mark.asyncio
    async def test_custom_name(self):
        @tool(name="custom_add", description="Add numbers")
        async def add(a: int, b: int) -> int:
            return a + b

        assert add.definition.name == "custom_add"

    @pytest.mark.asyncio
    async def test_docstring_as_description(self):
        @tool()
        async def greet(name: str) -> str:
            """Say hello to someone."""
            return f"Hello, {name}!"

        assert greet.definition.description == "Say hello to someone."

    @pytest.mark.asyncio
    async def test_schema_generated(self):
        @tool(description="Search")
        async def search(query: str, max_results: int = 10) -> list[str]:
            return []

        schema = search.definition.input_schema
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "max_results" in schema["properties"]

    @pytest.mark.asyncio
    async def test_with_annotations(self):
        @tool(description="Read data", annotations=Annotations(read_only_hint=True))
        async def reader(key: str) -> str:
            return key

        assert reader.definition.annotations is not None
        assert reader.definition.annotations.read_only_hint is True

    @pytest.mark.asyncio
    async def test_no_params(self):
        @tool(description="Ping")
        async def ping() -> str:
            return "pong"

        result = await ping.call(Context(), {})
        assert result.content == "pong"

    @pytest.mark.asyncio
    async def test_with_ctx(self):
        @tool(description="Use context")
        async def use_ctx(ctx: Context, query: str) -> str:
            return f"req={ctx.request_id} q={query}"

        ctx = Context(request_id="r1")
        result = await use_ctx.call(ctx, {"query": "test"})
        assert result.content == "req=r1 q=test"

    @pytest.mark.asyncio
    async def test_returning_result(self):
        @tool(description="Custom result")
        async def custom(msg: str) -> Result:
            return text_result(f"custom: {msg}")

        result = await custom.call(Context(), {"msg": "hello"})
        assert result.content == "custom: hello"

    @pytest.mark.asyncio
    async def test_returning_dict(self):
        @tool(description="Dict return")
        async def dict_ret(key: str) -> dict:
            return {"key": key, "value": 42}

        result = await dict_ret.call(Context(), {"key": "test"})
        assert result.output == {"key": "test", "value": 42}

    @pytest.mark.asyncio
    async def test_returning_list(self):
        @tool(description="List return")
        async def list_ret() -> list:
            return [1, 2, 3]

        result = await list_ret.call(Context(), {})
        assert result.output == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_definition_new_fields(self):
        @tool(
            description="Write file",
            read_only=False,
            destructive=True,
            timeout=30.0,
            max_result_size=1024,
        )
        async def write_file(path: str, content: str) -> str:
            return "ok"

        assert write_file.definition.read_only is False
        assert write_file.definition.destructive is True
        assert write_file.definition.timeout == 30.0
        assert write_file.definition.max_result_size == 1024


# --- Tool class ---


class TestTool:
    @pytest.mark.asyncio
    async def test_as_callable(self):
        @tool(description="Echo")
        async def echo(message: str) -> str:
            return message

        callable_tool = echo.as_callable()
        assert isinstance(callable_tool, Callable)
        assert callable_tool.definition.name == "echo"
        result = await callable_tool.call(Context(), {"message": "hello"})
        assert isinstance(result, Result)
        assert result.content == "hello"

    @pytest.mark.asyncio
    async def test_with_annotations_returns_copy(self):
        @tool(description="Original")
        async def fn(x: int) -> int:
            return x

        annotated = fn.with_annotations(Annotations(category="math"))
        assert annotated.definition.annotations is not None
        assert annotated.definition.annotations.category == "math"
        # Original unchanged.
        assert fn.definition.annotations is None

    @pytest.mark.asyncio
    async def test_validate_valid_input(self):
        @tool(description="Greet")
        async def greet(name: str) -> str:
            return f"Hello, {name}!"

        vr = greet.validate({"name": "Alice"})
        assert vr.valid

    @pytest.mark.asyncio
    async def test_validate_invalid_input(self):
        @tool(description="Greet")
        async def greet(name: str) -> str:
            return f"Hello, {name}!"

        vr = greet.validate({"name": 42})
        assert not vr.valid
        assert len(vr.errors) > 0


# --- Registry ---


class TestRegistry:
    @pytest.mark.asyncio
    async def test_register_and_call(self):
        @tool(description="Greet")
        async def greet(name: str) -> str:
            return f"Hello, {name}!"

        reg = Registry()
        reg.register(greet.as_callable())
        result = await reg.call("greet", Context(), {"name": "World"})
        assert isinstance(result, Result)
        assert result.content == "Hello, World!"

    def test_duplicate_raises(self):
        @tool(description="A")
        async def fn(x: int) -> int:
            return x

        reg = Registry()
        reg.register(fn.as_callable())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(fn.as_callable())

    def test_get_none_for_missing(self):
        reg = Registry()
        assert reg.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_call_missing_raises(self):
        reg = Registry()
        with pytest.raises(KeyError, match="not found"):
            await reg.call("missing", Context(), {})

    def test_list_definitions(self):
        @tool(description="A")
        async def a(x: int) -> int:
            return x

        @tool(description="B")
        async def b(x: int) -> int:
            return x

        reg = Registry()
        reg.register(a.as_callable())
        reg.register(b.as_callable())
        defs = reg.list()
        assert len(defs) == 2
        names = {d.name for d in defs}
        assert names == {"a", "b"}

    def test_len_and_contains(self):
        @tool(description="X")
        async def x(v: int) -> int:
            return v

        reg = Registry()
        assert len(reg) == 0
        assert "x" not in reg

        reg.register(x.as_callable())
        assert len(reg) == 1
        assert "x" in reg

    def test_names(self):
        @tool(description="A")
        async def alpha() -> str:
            return "a"

        @tool(description="B")
        async def beta() -> str:
            return "b"

        reg = Registry()
        reg.register(alpha.as_callable())
        reg.register(beta.as_callable())
        assert sorted(reg.names()) == ["alpha", "beta"]

    def test_search(self):
        @tool(description="Search the web")
        async def web_search(q: str) -> str:
            return q

        @tool(description="Read a file")
        async def file_read(path: str) -> str:
            return path

        reg = Registry()
        reg.register(web_search.as_callable())
        reg.register(file_read.as_callable())

        results = reg.search("search")
        assert len(results) == 1
        assert results[0].name == "web_search"

        results = reg.search("file")
        assert len(results) == 1
        assert results[0].name == "file_read"

        results = reg.search("xyz")
        assert len(results) == 0

    def test_filter_by_execution_hint_explicit(self):
        @tool(description="UI tool", annotations=Annotations(execution_hint="ui"))
        async def ui_tool(x: int) -> int:
            return x

        @tool(description="Backend tool", annotations=Annotations(execution_hint="backend"))
        async def backend_tool(x: int) -> int:
            return x

        @tool(description="Hybrid tool", annotations=Annotations(execution_hint="hybrid"))
        async def hybrid_tool(x: int) -> int:
            return x

        reg = Registry()
        reg.register(ui_tool.as_callable())
        reg.register(backend_tool.as_callable())
        reg.register(hybrid_tool.as_callable())

        assert [d.name for d in reg.filter_by_execution_hint("ui")] == ["ui_tool"]
        assert [d.name for d in reg.filter_by_execution_hint("backend")] == ["backend_tool"]
        assert [d.name for d in reg.filter_by_execution_hint("hybrid")] == ["hybrid_tool"]

    def test_filter_by_execution_hint_default_is_backend(self):
        """Tools with no annotations or empty execution_hint are treated as backend."""

        @tool(description="No annotations")
        async def plain(x: int) -> int:
            return x

        @tool(description="Empty hint", annotations=Annotations(execution_hint=""))
        async def empty_hint(x: int) -> int:
            return x

        @tool(description="UI tool", annotations=Annotations(execution_hint="ui"))
        async def ui_tool(x: int) -> int:
            return x

        reg = Registry()
        reg.register(plain.as_callable())
        reg.register(empty_hint.as_callable())
        reg.register(ui_tool.as_callable())

        backend = reg.filter_by_execution_hint("backend")
        names = {d.name for d in backend}
        assert names == {"plain", "empty_hint"}

        ui = reg.filter_by_execution_hint("ui")
        assert [d.name for d in ui] == ["ui_tool"]

    @pytest.mark.asyncio
    async def test_call_batch(self):
        @tool(description="Double", read_only=True)
        async def double(n: int) -> int:
            return n * 2

        @tool(description="Write", read_only=False)
        async def write(msg: str) -> str:
            return f"wrote: {msg}"

        reg = Registry()
        reg.register(double.as_callable())
        reg.register(write.as_callable())

        results = await reg.call_batch(
            [
                ("double", {"n": 5}),
                ("write", {"msg": "hello"}),
                ("double", {"n": 10}),
            ],
            Context(),
        )

        assert len(results) == 3
        assert results[0].content == "10"
        assert results[1].content == "wrote: hello"
        assert results[2].content == "20"

    @pytest.mark.asyncio
    async def test_call_batch_missing_tool(self):
        reg = Registry()
        results = await reg.call_batch([("missing", {})], Context())
        assert len(results) == 1
        assert results[0].is_error


# --- Middleware ---


class TestMiddleware:
    @pytest.mark.asyncio
    async def test_with_logging(self):
        @tool(description="Echo")
        async def echo(msg: str) -> str:
            return msg

        logger = logging.getLogger("test_tool")
        wrapped = with_logging(logger)(echo.as_callable())
        result = await wrapped.call(Context(), {"msg": "hi"})
        assert isinstance(result, Result)
        assert result.content == "hi"

    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        @tool(description="Fast")
        async def fast() -> str:
            return "done"

        wrapped = with_timeout(5.0)(fast.as_callable())
        result = await wrapped.call(Context(), {})
        assert result.content == "done"

    @pytest.mark.asyncio
    async def test_with_timeout_exceeded(self):
        @tool(description="Slow")
        async def slow() -> str:
            await asyncio.sleep(10)
            return "done"

        wrapped = with_timeout(0.01)(slow.as_callable())
        with pytest.raises(asyncio.TimeoutError):
            await wrapped.call(Context(), {})

    @pytest.mark.asyncio
    async def test_chain(self):
        @tool(description="Echo")
        async def echo(msg: str) -> str:
            return msg

        logger = logging.getLogger("test_chain")
        combined = chain(with_logging(logger), with_timeout(5.0))
        wrapped = combined(echo.as_callable())

        assert wrapped.definition.name == "echo"
        result = await wrapped.call(Context(), {"msg": "chained"})
        assert result.content == "chained"

    @pytest.mark.asyncio
    async def test_with_validation_valid(self):
        @tool(description="Greet")
        async def greet(name: str) -> str:
            return f"Hello, {name}!"

        wrapped = with_validation()(greet.as_callable())
        result = await wrapped.call(Context(), {"name": "Alice"})
        assert result.content == "Hello, Alice!"
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_with_validation_invalid(self):
        @tool(description="Greet")
        async def greet(name: str) -> str:
            return f"Hello, {name}!"

        wrapped = with_validation()(greet.as_callable())
        result = await wrapped.call(Context(), {"name": 42})
        assert result.is_error is True
        assert "validation failed" in result.content

    @pytest.mark.asyncio
    async def test_with_result_limit(self):
        @tool(description="Long output")
        async def long_output() -> str:
            return "A" * 10000

        wrapped = with_result_limit(100)(long_output.as_callable())
        result = await wrapped.call(Context(), {})
        assert len(result.content) < 10000
        assert "[truncated]" in result.content
        assert result.metadata.get("truncated") is True

    @pytest.mark.asyncio
    async def test_with_result_limit_small_output(self):
        @tool(description="Short output")
        async def short_output() -> str:
            return "hello"

        wrapped = with_result_limit(100)(short_output.as_callable())
        result = await wrapped.call(Context(), {})
        assert result.content == "hello"
        assert "truncated" not in result.metadata


# --- Definition ---


class TestDefinition:
    def test_frozen(self):
        d = Definition(name="test", description="A test tool")
        with pytest.raises(AttributeError):
            d.name = "changed"  # type: ignore[misc]

    def test_defaults(self):
        d = Definition(name="test", description="desc")
        assert d.input_schema == {}
        assert d.output_schema is None
        assert d.annotations is None
        assert d.read_only is False
        assert d.destructive is False
        assert d.timeout == 0.0
        assert d.max_result_size == 0

    def test_new_fields(self):
        d = Definition(
            name="test",
            description="desc",
            read_only=True,
            destructive=True,
            timeout=30.0,
            max_result_size=4096,
        )
        assert d.read_only is True
        assert d.destructive is True
        assert d.timeout == 30.0
        assert d.max_result_size == 4096


class TestAnnotations:
    def test_frozen(self):
        a = Annotations(title="Test")
        with pytest.raises(AttributeError):
            a.title = "changed"  # type: ignore[misc]

    def test_defaults(self):
        a = Annotations()
        assert a.title == ""
        assert a.read_only_hint is None
        assert a.destructive_hint is None
        assert a.category == ""
        assert a.tags == []
        assert a.execution_hint == ""

    def test_execution_hint_values(self):
        for hint in ("ui", "backend", "hybrid"):
            a = Annotations(execution_hint=hint)
            assert a.execution_hint == hint

    def test_execution_hint_in_dataclass_fields(self):
        """execution_hint should round-trip through dataclasses.asdict."""
        import dataclasses

        a = Annotations(title="X", execution_hint="hybrid", category="nav")
        d = dataclasses.asdict(a)
        assert d["execution_hint"] == "hybrid"
        assert d["title"] == "X"
