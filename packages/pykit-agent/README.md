# pykit-agent

AI agent loop with tool execution, hooks, and context management for building autonomous agents.

## Installation

```bash
pip install pykit-agent
```

## Quick start

```python
from pykit_agent import Agent, AgentConfig

config = AgentConfig(max_iterations=10)
agent = Agent(config=config)

result = await agent.run("Summarize the latest news about Python")
print(result.output)
```

## Features

- Iterative agent loop with configurable max iterations and stop conditions
- Tool registry integration — auto-wires tools via `pykit-tool`
- Hook system for pre/post step callbacks (`pykit-hook`)
- LLM abstraction via `pykit-llm` — swap providers without changing agent logic
- Async-first design with structured context propagation
