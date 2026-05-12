# pykit-ai

Canonical AI vocabulary for pykit AI/ML packages: content parts, messages, model identity, usage, budgets, stream events, prompts, vector helpers, typed exceptions, and OpenTelemetry semantic-convention keys.

This package contains shared types and utilities only: no providers, registries, I/O, or runtime logic.

## Architecture

```mermaid
flowchart TD
  AI[pykit-ai]
  C[content + core + stream]
  M[message + chat]
  P[prompt]
  V[vector]
  E[errors + semconv]
  S[imports pykit-schema]
  LLM[pykit-llm]
  EMB[pykit-embedding]
  AGENT[pykit-agent]
  MCP[pykit-mcp]

  AI --> C
  AI --> M
  AI --> P
  AI --> V
  AI --> E
  AI --> S
  LLM --> AI
  EMB --> AI
  AGENT --> AI
  MCP --> AI
```
