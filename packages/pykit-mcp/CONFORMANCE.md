# pykit-mcp MCP 2025-06-18 conformance

This document tracks `pykit-mcp`'s conformance to the
[Model Context Protocol](https://modelcontextprotocol.io/) revision
**2025-06-18**. The spec itself lives upstream; this file records what is
implemented here, what is partial, and explicit deviations.


| Capability | Status | Notes |
|---|---|---|
| tools/list + tools/call | Present | Backed by `pykit_tool.Registry`; per-call authz seam available. |
| prompts/list + prompts/get | Present | Static prompt entries; `pykit_ai.prompt` owns shared prompt templates. |
| resources/list + resources/read | Present | Static resources and template matching. |
| resource templates | Present | Basic URI-template matching. |
| cancellation | Partial | SDK/session cancellation propagates; explicit compliance vectors still limited by upstream SDK surface. |
| progress/logging/pagination/completion | Partial | Native SDK request handlers can be added; no bespoke protocol fork. |
| structured tool output | Present | Output schema validation before MCP result conversion. |
| tool annotations | Present | Converted to MCP annotations; remote annotations derive local tool envelopes. |
| roots/sampling/elicitation | Partial | Client-side/server-side seams depend on upstream SDK capability exposure. |
| stdio transport | Present | Canonical name `stdio`. |
| streamable_http transport | Present | Canonical name `streamable_http`; SSE is not a separate transport. |
| Origin validation | Present | `create_streamable_http_security_settings`. |
| localhost bind | Present | `create_mcp_http_security_config` defaults to `127.0.0.1`. |
| payload limits | Present | Server `max_input_bytes`/`max_result_bytes`; HTTP helper `max_payload_bytes`. |
| OAuth 2.1 + PKCE | Partial | Helper config and default requirement seam; full authorization server integration is composition-owned. |
