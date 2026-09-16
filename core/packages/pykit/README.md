# pykit

Install one facade package to get every core pykit dependency and a lazy import surface over the toolkit.

## Installation

```bash
pip install pykit
# or
uv add pykit
```

## Quick start

```python
import pykit

errors = pykit.errors
util = pykit.util
version = pykit.version

slug = util.slug("Hello World!")
print(slug)
print(version.get_short_version("my-service"))

# Direct package imports still work when you want them.
from pykit_util import deep_merge
```

## How the facade works

- `import pykit` stays lightweight. Sub-packages are imported on first attribute access through lazy `__getattr__` loading.
- The facade installs **45 package dependencies** and exposes **44 lazy import targets**.
- Most attributes map one-to-one to a package, such as `pykit.errors -> pykit_errors` and `pykit.storage -> pykit_storage`.
- A few names are aliases: `pykit.kafka -> pykit_messaging` and `pykit.prompt -> pykit_ai.prompt`.

## Included package groups

| Group | Examples |
| --- | --- |
| Foundation | `errors`, `config`, `logging`, `validation`, `encryption`, `util`, `version`, `media` |
| Composition | `provider`, `component`, `resilience`, `di`, `bootstrap`, `observability`, `security` |
| Service infrastructure | `database`, `cache`, `storage`, `httpclient`, `server`, `grpc`, `auth`, `authz` |
| Runtime orchestration | `pipeline`, `dag`, `worker`, `sse`, `stateful`, `process`, `workload` |
| AI and tooling | `llm`, `ai`, `inference`, `dataset`, `embedding`, `tool`, `agent`, `mcp`, `skill`, `schema`, `hook`, `bench`, `testutil`, `discovery` |

## See also

- [Main pykit README](../../../README.md)
