# pykit-explain

Structured explanation generation from analysis signals using LLMs.

## Installation

```bash
pip install pykit-explain
```

## Quick start

```python
from pykit_explain import ExplanationService, AnalysisSignal

service = ExplanationService()

signals = [
    AnalysisSignal(name="anomaly_score", value=0.92, context="CPU spike"),
    AnalysisSignal(name="error_rate", value=0.15, context="5xx responses"),
]
explanation = await service.explain(signals)
print(explanation.summary)
```

## Features

- Converts raw analysis signals into human-readable explanations via LLMs
- Structured `AnalysisSignal` and `Explanation` data models
- Pluggable LLM backend via `pykit-llm`
- Supports batch explanation with ranking and deduplication
- Async-first design
