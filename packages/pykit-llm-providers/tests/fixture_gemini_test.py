from __future__ import annotations

import json

import httpx
import pytest

from pykit_ai import ToolUseBlock
from pykit_llm import StreamChunk
from pykit_llm_providers.gemini.dialect import _iter_sse, _parse_response


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
    sse = "".join(f"data: {event}\n\n" for event in events)
    response = httpx.Response(200, content=sse.encode())
    chunks = [chunk async for chunk in _iter_sse(response)]
    return _assemble_tool_calls(chunks)


@pytest.mark.parametrize(
    ("raw_response", "expected"),
    [
        pytest.param(
            """
            {
              "candidates": [{
                "content": {
                  "parts": [{"functionCall": {"name": "get_weather", "args": {"city": "NYC"}}}],
                  "role": "model"
                },
                "finishReason": "TOOL_USE"
              }],
              "modelVersion": "gemini-2.0-flash"
            }
            """,
            [ToolUseBlock(id="get_weather", name="get_weather", input={"city": "NYC"})],
            id="single-tool-call",
        ),
        pytest.param(
            """
            {
              "candidates": [{
                "content": {
                  "parts": [
                    {"functionCall": {"name": "search", "args": {"query": "python"}}},
                    {"functionCall": {"name": "fetch", "args": {"url": "https://example.com"}}}
                  ],
                  "role": "model"
                },
                "finishReason": "TOOL_USE"
              }],
              "modelVersion": "gemini-2.0-flash"
            }
            """,
            [
                ToolUseBlock(id="search", name="search", input={"query": "python"}),
                ToolUseBlock(id="fetch", name="fetch", input={"url": "https://example.com"}),
            ],
            id="multi-tool-call",
        ),
        pytest.param(
            """
            {
              "candidates": [{
                "content": {
                  "parts": [{"functionCall": {"name": "ping", "args": {}}}],
                  "role": "model"
                },
                "finishReason": "TOOL_USE"
              }],
              "modelVersion": "gemini-2.0-flash"
            }
            """,
            [ToolUseBlock(id="ping", name="ping", input={})],
            id="empty-input",
        ),
        pytest.param(
            """
            {
              "candidates": [{
                "content": {
                  "parts": [{
                    "functionCall": {
                      "name": "plan_trip",
                      "args": {
                        "trip": {"city": "NYC", "days": [1, 2]},
                        "preferences": {"indoor": true}
                      }
                    }
                  }],
                  "role": "model"
                },
                "finishReason": "TOOL_USE"
              }],
              "modelVersion": "gemini-2.0-flash"
            }
            """,
            [
                ToolUseBlock(
                    id="plan_trip",
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
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "functionCall": {
                                                "name": "plan_trip",
                                                "args": {
                                                    "trip": {"city": "NYC", "days": [1, 2]},
                                                    "preferences": {"indoor": True},
                                                },
                                            }
                                        }
                                    ],
                                    "role": "model",
                                }
                            }
                        ]
                    }
                ),
                json.dumps(
                    {
                        "candidates": [
                            {
                                "content": {"parts": [], "role": "model"},
                                "finishReason": "TOOL_USE",
                            }
                        ]
                    }
                ),
            ],
            [
                ToolUseBlock(
                    id="plan_trip",
                    name="plan_trip",
                    input={"trip": {"city": "NYC", "days": [1, 2]}, "preferences": {"indoor": True}},
                )
            ],
            id="streaming-events",
        )
    ],
)
async def test_parse_stream_tool_calls(events: list[str], expected: list[ToolUseBlock]) -> None:
    assert await _parse_stream_tool_calls(events) == expected
