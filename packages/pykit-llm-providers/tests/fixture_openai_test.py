from __future__ import annotations

import json

import httpx
import pytest

from pykit_ai import ToolUseBlock
from pykit_llm import StreamChunk
from pykit_llm_providers.openai.dialect import _iter_sse, _parse_response


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


async def _parse_stream_tool_calls(events: list[str]) -> list[ToolUseBlock]:
    sse = "".join(f"data: {event}\n\n" for event in events) + "data: [DONE]\n\n"
    response = httpx.Response(200, content=sse.encode())
    chunks = [chunk async for chunk in _iter_sse(response)]
    return _assemble_tool_calls(chunks)


@pytest.mark.parametrize(
    ("raw_response", "expected"),
    [
        pytest.param(
            """
            {
              "id": "chatcmpl-single",
              "object": "chat.completion",
              "model": "gpt-4o",
              "choices": [{
                "index": 0,
                "message": {
                  "role": "assistant",
                  "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                      "name": "get_weather",
                      "arguments": "{\\"city\\":\\"NYC\\"}"
                    }
                  }]
                },
                "finish_reason": "tool_calls"
              }]
            }
            """,
            [ToolUseBlock(id="call_1", name="get_weather", input={"city": "NYC"})],
            id="single-tool-call",
        ),
        pytest.param(
            """
            {
              "id": "chatcmpl-multi",
              "object": "chat.completion",
              "model": "gpt-4o",
              "choices": [{
                "index": 0,
                "message": {
                  "role": "assistant",
                  "tool_calls": [
                    {
                      "id": "call_1",
                      "type": "function",
                      "function": {
                        "name": "search",
                        "arguments": "{\\"query\\":\\"python\\"}"
                      }
                    },
                    {
                      "id": "call_2",
                      "type": "function",
                      "function": {
                        "name": "fetch",
                        "arguments": "{\\"url\\":\\"https://example.com\\"}"
                      }
                    }
                  ]
                },
                "finish_reason": "tool_calls"
              }]
            }
            """,
            [
                ToolUseBlock(id="call_1", name="search", input={"query": "python"}),
                ToolUseBlock(id="call_2", name="fetch", input={"url": "https://example.com"}),
            ],
            id="multi-tool-call",
        ),
        pytest.param(
            """
            {
              "id": "chatcmpl-empty",
              "object": "chat.completion",
              "model": "gpt-4o",
              "choices": [{
                "index": 0,
                "message": {
                  "role": "assistant",
                  "tool_calls": [{
                    "id": "call_empty",
                    "type": "function",
                    "function": {
                      "name": "ping",
                      "arguments": "{}"
                    }
                  }]
                },
                "finish_reason": "tool_calls"
              }]
            }
            """,
            [ToolUseBlock(id="call_empty", name="ping", input={})],
            id="empty-args",
        ),
        pytest.param(
            """
            {
              "id": "chatcmpl-nested",
              "object": "chat.completion",
              "model": "gpt-4o",
              "choices": [{
                "index": 0,
                "message": {
                  "role": "assistant",
                  "tool_calls": [{
                    "id": "call_nested",
                    "type": "function",
                    "function": {
                      "name": "plan_trip",
                      "arguments": "{\\"trip\\":{\\"city\\":\\"NYC\\",\\"days\\":[1,2]},\\"preferences\\":{\\"indoor\\":true}}"
                    }
                  }]
                },
                "finish_reason": "tool_calls"
              }]
            }
            """,
            [
                ToolUseBlock(
                    id="call_nested",
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
                json.dumps(
                    {
                        "id": "chatcmpl-stream-1",
                        "object": "chat.completion.chunk",
                        "model": "gpt-4o",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call_stream",
                                            "function": {
                                                "name": "plan_trip",
                                                "arguments": '{"trip": {"city": "NY',
                                            },
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ],
                    }
                ),
                json.dumps(
                    {
                        "id": "chatcmpl-stream-2",
                        "object": "chat.completion.chunk",
                        "model": "gpt-4o",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "",
                                            "function": {
                                                "name": "",
                                                "arguments": 'C", "days": [1, 2]}, "preferences": {"indoor": true}}',
                                            },
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ],
                    }
                ),
            ],
            [
                ToolUseBlock(
                    id="call_stream",
                    name="plan_trip",
                    input={"trip": {"city": "NYC", "days": [1, 2]}, "preferences": {"indoor": True}},
                )
            ],
            id="streaming-deltas",
        )
    ],
)
async def test_parse_stream_tool_calls(events: list[str], expected: list[ToolUseBlock]) -> None:
    assert await _parse_stream_tool_calls(events) == expected
