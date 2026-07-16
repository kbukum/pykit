---
name: new-backend
description: >-
    Add a pluggable backend/adapter (storage, cache, messaging, inference, llm, vectorstore) to
    pykit the canonical way — a contrib package under contrib/pykit-<domain>-<name> implementing
    the core Protocol, selected via config through an explicit typed registration, no import-time
    side effects, with the in-memory/local default kept in core. Use when integrating a provider
    like S3, Kafka, Redis, Qdrant, or an LLM/inference provider.
user-invocable: true
---

# Adding a backend adapter to pykit

pykit's data/ai/infra domains use a Protocol + registration pattern so a core package ships an
in-memory or local default and heavy provider backends live in opt-in **contrib packages** installed
as optional extras. Follow the existing owners exactly — do not invent a new registration mechanism.

## The binding rules

1. **Contrib package.** The adapter lives at `contrib/pykit-<domain>-<name>/` (`pykit-storage-s3`,
   `pykit-messaging-kafka`, `pykit-cache-redis`, `pykit-vectorstore-qdrant`, …), added to the
   `contrib/pyproject.toml` workspace members + dev group. It carries the heavy SDK dependency so
   core stays light.
2. **Implements the core Protocol.** The adapter implements the canonical Protocol its core package
   owns (e.g. the storage/cache/messaging provider Protocol) — it does not redefine the abstraction.
   It depends on the core package (`pykit-<domain>`) plus the SDK.
3. **Explicit typed registration, config-driven selection.** Registration is explicit and
   caller-driven with typed config captured in the factory; **no import-time side effects, no
   module-level mutable global registry**. Selection is config-driven (a module-level dict populated
   at import, or registration in `__init__`, is a blocker).
4. **Core keeps the default.** The in-memory / local backend stays in the core package and remains
   the zero-config default; contrib backends are selected via config and installed as an optional
   extra (`pip install pykit-<domain>[<name>]` or the dedicated `pykit-<domain>-<name>` package).

Study an existing adapter under `contrib/` (e.g. `pykit-cache-redis`, `pykit-storage-s3`) for the
exact shape before writing a new one.

## Steps

1. **Create the contrib package** (see the `new-package` skill for workspace wiring):

   ```
   contrib/pykit-<domain>-<name>/
   ├── pyproject.toml        # deps: pykit-<domain>, pykit-errors, <sdk>
   ├── src/pykit_<domain>_<name>/
   └── tests/
   ```

   Add it to `contrib/pyproject.toml` members + dev group and run `uv lock`.

2. **Define a typed `Config`** for the backend (endpoint, credentials source, timeouts,
   bucket/topic names) as a frozen dataclass or pydantic model. No `Any`/stringly-typed escape
   hatch. Validate it at construction — this is a trust boundary.

3. **Implement the adapter** against the core Protocol. Timeout every remote `await`
   (`asyncio.timeout`); bounded jittered retries for idempotent ops only; degrade/circuit-break
   rather than success-shaped fallbacks. Tokens go in headers, not query strings. No bare
   `except`/swallowed errors on runtime paths; typed `AppError` preserving cause via
   `raise ... from e`. Split code by concern into focused modules (config, client, adapter,
   mapping).

4. **Expose explicit registration** — a function that closes over the config and installs the typed
   factory into the passed registry. No global registry, no import-time side effects.

5. **Package docstring** on `__init__.py` describing the backend, its config, and its failure modes.

6. **Tests** — behavioral, deterministic, async via `pytest-asyncio`/`anyio`, injected clock (never
   wall-clock `sleep`), cover failure paths; fixtures over embedded config; parallel-safe under
   `pytest -n auto`. Integration tests that need a live broker/store are marked (`integration`) and
   skipped without it.

## Validate

```bash
make fmt
make build     P=pykit-<domain>-<name>
make lint      P=pykit-<domain>-<name>
make typecheck P=pykit-<domain>-<name>
make test      P=pykit-<domain>-<name>
uv run import-linter
```

## Checklist

- [ ] Contrib package under `contrib/pykit-<domain>-<name>/`, added to `contrib/pyproject.toml`
- [ ] Optional-extra install wired; core in-memory/local default untouched and still zero-config
- [ ] Typed `Config`, validated at construction; no `Any`/stringly-typed factory
- [ ] Explicit registration; no import-time side effects, no mutable global registry
- [ ] Timeouts, bounded retries (idempotent only), no success-shaped fallbacks, typed errors
- [ ] Package docstring + behavioral async tests, deterministic and parallel-safe

Per repo workflow, **create the branch and make edits only** — the maintainer commits and pushes.
