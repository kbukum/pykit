# pykit Usage Examples

A tour of common pykit patterns. For per-package details, see each package's own `README.md`.

## Config + Logging

```python
from pykit_config import ServiceConfig, load_config
from pykit_logging import setup_logging, get_logger

config = load_config(ServiceConfig, config_file="config.yml")
setup_logging(config)
log = get_logger("my-service")
log.info("service configured", env=config.environment)
```

## Resilience Patterns

```python
from pykit_resilience import retry, CircuitBreaker

cb = CircuitBreaker(max_failures=5, timeout=30.0)

@retry(max_attempts=3, backoff=0.1)
async def call_external():
    async with cb:
        return await httpx.get("https://api.example.com/data")
```

## Agent Loop

```python
from pykit_agent import Agent, AgentConfig
from pykit_tool import Registry

registry = Registry()
registry.register(weather_tool)

agent = Agent(llm_provider, registry, config=AgentConfig(max_turns=10))
result = await agent.run("What's the weather in Berlin?")
print(result.events)
```

## LLM Chat Completion

```python
from pykit_llm import LLMProvider, Request, Message

provider = LLMProvider(dialect="openai", model="gpt-4", api_key=os.getenv("OPENAI_API_KEY"))
resp = await provider.chat_completion(Request(
    messages=[Message(role="user", content="Explain circuit breakers")],
))
print(resp.content)
```

## Messaging

```python
from pykit_messaging import Producer, Consumer

producer = Producer(config)
await producer.publish("events", key="user-123", value=payload)

consumer = Consumer(config, group="my-group")
consumer.subscribe("events", handler=process_event)
await consumer.start()
```

## Object Storage

```python
from pykit_storage import Storage

store = Storage(config)
await store.put("uploads/report.pdf", data)
content = await store.get("uploads/report.pdf")
```
