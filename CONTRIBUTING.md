# Contributing to pykit

Thank you for your interest in contributing! This document explains how to get
started, what we expect from contributors, and how the review process works.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Linting](#linting)
- [Import Layering](#import-layering)
- [Adding a New Package](#adding-a-new-package)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

---

## Code of Conduct

Be respectful, constructive, and patient. We follow the
[Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

---

## Getting Started

1. [Fork](https://github.com/kbukum/pykit/fork) the repository.
2. Clone your fork:

   ```sh
   git clone https://github.com/<your-username>/pykit.git
   cd pykit
   ```

3. Set the upstream remote:

   ```sh
   git remote add upstream https://github.com/kbukum/pykit.git
   ```

---

## Development Setup

**Minimum Python version:** 3.13+ (enforced by `.python-version`).

pykit uses [uv](https://docs.astral.sh/uv/) as its package manager and
workspace tool.

```sh
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync the entire workspace (installs all packages + dev dependencies)
uv sync

# Verify everything works
uv run pytest
```

The workspace is structured as a **uv workspace monorepo** with 44 independent
packages under `packages/`. Each package has its own `pyproject.toml`,
`src/<package_name>/` layout, and `tests/` directory.

---

## Code Style

| Rule | Setting |
|---|---|
| Formatter / Linter | [Ruff](https://docs.astral.sh/ruff/) |
| Line length | 110 |
| Type checker | [mypy](https://mypy-lang.org/) (strict mode) |
| Docstrings | Google style |
| Future annotations | `from __future__ import annotations` in every module |
| Target version | Python 3.13 |

Key conventions:

- **`from __future__ import annotations`** — required at the top of every
  Python file for consistent type-annotation behavior.
- **Google-style docstrings** — use `Args:`, `Returns:`, `Raises:` sections.
- **Protocol over ABC** — prefer `typing.Protocol` for interface definitions.
- **Pydantic models** for configuration and data transfer objects.
- **async/await** for all I/O-bound operations.

---

## Testing

Every public function and protocol implementation should have at least one test.

```sh
# Run the full test suite
uv run pytest

# Run tests for a specific package
uv run pytest packages/pykit-errors/

# Run with coverage
uv run pytest --cov
```

Coverage expectations:

- Minimum coverage threshold: **60%** (enforced by `pyproject.toml`).
- Aim for higher coverage on core packages (`errors`, `config`, `provider`,
  `resilience`, `pipeline`).
- Time-dependent tests should use `asyncio` time mocking — never
  `time.sleep()` in tests.
- Tests requiring live services (databases, Redis, Kafka) should be marked
  with `@pytest.mark.integration` and documented.

---

## Linting

All checks must pass before submitting a PR:

```sh
# Lint check
uv run ruff check packages/

# Format check
uv run ruff format packages/ --check

# Type check
uv run mypy packages/
```

To auto-fix lint and formatting issues:

```sh
uv run ruff check packages/ --fix
uv run ruff format packages/
```

---

## Import Layering

pykit enforces a **strict layer architecture** using
[import-linter](https://import-linter.readthedocs.io/). Lower layers cannot
import from higher layers. This prevents circular dependencies and keeps the
dependency graph clean.

The layers (from lowest to highest) are defined in the root `pyproject.toml`
under `[tool.importlinter]`:

```
Layer 0 (Foundation):  errors, config, logging
Layer 1 (Utilities):   validation, encryption, util, version, media
Layer 2 (Patterns):    provider, component, resilience
Layer 3 (Frameworks):  di, bootstrap, observability
Layer 4 (Data/Flow):   pipeline, dag, worker, sse, stateful
Layer 5 (Security):    auth, authz, security
Layer 6 (Infra):       database, redis, storage, messaging, httpclient
Layer 7 (Servers):     server, grpc
Layer 8 (AI/ML):       llm, triton, bench, dataset
Layer 9 (Platform):    discovery, workload, process, testutil, metrics
```

To verify layering:

```sh
uv run lint-imports
```

When adding new imports, check the layer definitions to ensure you are not
importing from a higher layer.

---

## Adding a New Package

1. Create the package directory:

   ```sh
   mkdir -p packages/pykit-<name>/src/pykit_<name>
   mkdir -p packages/pykit-<name>/tests
   ```

2. Create `packages/pykit-<name>/pyproject.toml`:

   ```toml
   [project]
   name = "pykit-<name>"
   description = "Brief description of the package"
   version = "0.1.0"
   requires-python = ">=3.13"
   dependencies = []

   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

   [tool.hatch.build.targets.wheel]
   packages = ["src/pykit_<name>"]
   ```

3. Create `packages/pykit-<name>/src/pykit_<name>/__init__.py`:

   ```python
   from __future__ import annotations
   ```

4. Add the package to the root `pyproject.toml`:
   - Add to `[dependency-groups] dev`
   - Add to `[tool.uv.sources]`
   - Add to `[tool.coverage.run] source_pkgs`
   - Add to `[tool.ruff.lint.isort] known-first-party`
   - Add to the appropriate layer in `[tool.importlinter]`

5. Wire the package into the `pykit` facade if appropriate.

6. Add an entry to the package table in `README.md`.

7. Open a tracking issue describing the API surface before implementing, so
   the design can be discussed early.

---

## Pull Request Process

1. Create a feature branch from `main`:

   ```sh
   git checkout -b feat/my-feature
   ```

2. Make the smallest change that achieves the goal. Avoid unrelated clean-up
   in the same PR — file a separate issue/PR for it.

3. Ensure all checks pass:

   ```sh
   uv run ruff check packages/
   uv run ruff format packages/ --check
   uv run mypy packages/
   uv run pytest
   uv run lint-imports
   ```

4. Update `CHANGELOG.md` under `## [Unreleased]` with a brief description of
   what you added, changed, or fixed.

5. Push your branch and open a PR against `main`.

6. Fill in the PR description completely — explain **what** and **why**.

7. Request a review from a maintainer.

8. Address review comments in follow-up commits (do not force-push after
   review has started unless asked).

9. A maintainer will squash-merge once approved.

---

## Release Process

- All packages currently share the same version: **0.1.0**.
- Version bumps are coordinated across the workspace.
- We follow [Keep a Changelog](https://keepachangelog.com/) format.
- Releases are tagged as `v<version>` (e.g., `v0.1.0`).
- Breaking changes must be documented in the changelog with a
  `### Breaking Changes` section.

---

## Related Documents

- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Contributor Covenant v2.1
- [SECURITY.md](SECURITY.md) — vulnerability disclosure & supply-chain
- [GOVERNANCE.md](GOVERNANCE.md) — roles, decision making, sibling-parity contract
- [MAINTAINERS.md](MAINTAINERS.md) — current maintainers & areas
- [CHANGELOG.md](CHANGELOG.md) — release history
- [docs/RELEASING.md](docs/RELEASING.md) — release process
- [docs/VERSIONING.md](docs/VERSIONING.md) — versioning rules
- [docs/policy/SEMVER.md](docs/policy/SEMVER.md) · [docs/policy/DEPRECATION.md](docs/policy/DEPRECATION.md)
- [docs/adr/](docs/adr/) — Architecture Decision Records

### Sibling-parity reminder

Public abstractions (`AppError`, `Component`, `Provider`, `Pipeline`, lifecycle
hooks) are mirrored across [gokit](https://github.com/kbukum/gokit),
[rskit](https://github.com/kbukum/rskit), and
[pykit](https://github.com/kbukum/pykit). When you change one of these
surfaces here, please open tracking issues in the sibling repos so the change
can be evaluated for parity.
