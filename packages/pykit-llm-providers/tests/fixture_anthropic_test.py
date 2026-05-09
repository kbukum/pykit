from __future__ import annotations

import json

import httpx
import pytest

from pykit_ai import ToolUseBlock
from pykit_llm import StreamChunk
from pykit_llm_providers.anthropic.dialect import _iter_sse, _parse_response


def _assemble_tool_calls(chunks: list[StreamChunk]) -> list[ToolUseBlock]:
    states: dict[int, dict[str, str]] = {}
    for chunk in chunks:
        for tool_call in chunk.tool_calls or []:
            state = states.setdefault(tool_call.index, {"id": "", "name": "", "input_json": ""})
            if tool_call.id:
                state["id"] = tool_call.id
            if tool_call.name:
                state["name"] = tool_call.name
            state["input_json"] += tool_call.input_delta

    result: list[ToolUseBlock] = []
    for index in sorted(states):
        state = states[index]
        input_data = json.loads(state["input_json"] or "{}")
        assert isinstance(input_data, dict)
        result.append(ToolUseBlock(id=state["id"], name=state["name"], input=input_data))
    return result


async def _parse_stream_tool_calls(events: list[tuple[str, str]]) -> list[ToolUseBlock]:
    sse = "".join(f"event: {event}\ndata: {payload}\n\n" for event, payload in events)
    response = httpx.Response(200, content=sse.encode())
    chunks = [chunk async for chunk in _iter_sse(response)]
    return _assemble_tool_calls(chunks)


@pytest.mark.parametrize(
    ("raw_response", "expected"),
    [
        pytest.param(
            """
            {
              "id": "msg-single",
              "type": "message",
              "role": "assistant",
              "model": "claude-sonnet-4",
              "content": [{
                "type": "tool_use",
                "id": "toolu_1",
                "name": "get_weather",
                "input": {"city": "NYC"}
              }],
              "stop_reason": "tool_use"
            }
            """,
            [ToolUseBlock(id="toolu_1", name="get_weather", input={"city": "NYC"})],
            id="single-tool-call",
        ),
        pytest.param(
            """
            {
              "id": "msg-multi",
              "type": "message",
              "role": "assistant",
              "model": "claude-sonnet-4",
              "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "search", "input": {"query": "python"}},
                {"type": "tool_use", "id": "toolu_2", "name": "fetch", "input": {"url": "https://example.com"}}
              ],
              "stop_reason": "tool_use"
            }
            """,
            [
                ToolUseBlock(id="toolu_1", name="search", input={"query": "python"}),
                ToolUseBlock(id="toolu_2", name="fetch", input={"url": "https://example.com"}),
            ],
            id="multi-tool-call",
        ),
        pytest.param(
            """
            {
              "id": "msg-empty",
              "type": "message",
              "role": "assistant",
              "model": "claude-sonnet-4",
              "content": [{
                "type": "tool_use",
                "id": "toolu_empty",
                "name": "ping",
                "input": {}
              }],
              "stop_reason": "tool_use"
            }
            """,
            [ToolUseBlock(id="toolu_empty", name="ping", input={})],
            id="empty-input",
        ),
        pytest.param(
            """
            {
              "id": "msg-nested",
              "type": "message",
              "role": "assistant",
              "model": "claude-sonnet-4",
              "content": [{
                "type": "tool_use",
                "id": "toolu_nested",
                "name": "plan_trip",
                "input": {
                  "trip": {"city": "NYC", "days": [1, 2]},
                  "preferences": {"indoor": true}
                }
              }],
              "stop_reason": "tool_use"
            }
            """,
            [
                ToolUseBlock(
                    id="toolu_nested",
                    name="plan_trip",
                    input={"trip": {"city": "NYC", "days": [1, 2]}, "preferences": {"indoor": True}},
                )
            ],
            id="nested-input",
        ),
    ],
)
def test_parse_response_tool_calls(raw_response: str, expected: list[ToolUseBlock]) -> None:
    response = _parse_response(json.loads(raw_response))
    assert response.message.tool_calls == expected


@pytest.mark.parametrize(
    ("events", "expected"),
    [
        pytest.param(
            [
                (
                    "content_block_start",
                    json.dumps(
                        {
                            "type": "content_block_start",
                            "index": 0,
                            "content_block": {
                                "type": "tool_use",
                                "id": "toolu_stream",
                                "name": "plan_trip",
                            },
                        }
                    ),
                ),
                (
                    "content_block_delta",
                    json.dumps(
                        {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {"type": "input_json_delta", "partial_json": '{"trip": {"city": "NY'},
                        }
                    ),
                ),
                (
                    "content_block_delta",
                    json.dumps(
                        {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {
                                "type": "input_json_delta",
                                "partial_json": 'C", "days": [1, 2]}, "preferences": {"indoor": true}}',
                            },
                        }
                    ),
                ),
                (
                    "message_stop",
                    json.dumps({"type": "message_stop"}),
                ),
            ],
            [
                ToolUseBlock(
                    id="toolu_stream",
                    name="plan_trip",
                    input={"trip": {"city": "NYC", "days": [1, 2]}, "preferences": {"indoor": True}},
                )
            ],
            id="streaming-deltas",
        )
    ],
)
async def test_parse_stream_tool_calls(events: list[tuple[str, str]], expected: list[ToolUseBlock]) -> None:
    assert await _parse_stream_tool_calls(events) == expected
