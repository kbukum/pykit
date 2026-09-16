# Contributing to pykit
Use this guide to set up the repo, make changes safely, and open a clean pull request.

## Code of Conduct

Be respectful, constructive, and patient. We follow the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

## Quick start

1. [Fork](https://github.com/kbukum/pykit/fork) the repository.
2. Clone your fork and add the upstream remote.
3. Sync both workspaces.
4. Run the fast validation pass before you start editing.

```sh
git clone https://github.com/<your-username>/pykit.git
cd pykit
git remote add upstream https://github.com/kbukum/pykit.git

# Install uv first if needed: https://docs.astral.sh/uv/
make sync
make check-fast
```

## Repository layout

pykit is a uv monorepo with two workspaces:

- `core/` — the main workspace, including the `pykit` facade package and core packages under `core/packages/`
- `contrib/` — optional adapter packages under `contrib/`

Each package has its own `pyproject.toml`, `src/<package_name>/` layout, and `tests/` directory.

## Daily development workflow

Most contributors can work from the repo root with `make`:

| Task | Command |
|---|---|
| Show available commands | `make help` |
| Sync dependencies | `make sync` |
| Fast validation | `make check-fast` |
| Run fast unit tests | `make test-unit` |
| Test changed packages | `make test-affected` |
| Full validation | `make check` |

Useful scoped commands:

```sh
make lint P=pykit-auth
make typecheck P=pykit-auth
make test P=pykit-auth
make test P=pykit-auth T=test_jwt
make check P=pykit-messaging-kafka
```

Workspace selection is controlled with `W=core|contrib|both` and defaults to `both`.

If you prefer direct `uv` commands, run them inside `core/` or `contrib/`. The repo root is not itself a uv workspace.

## Development setup

**Minimum Python version:** 3.13+

pykit uses [uv](https://docs.astral.sh/uv/) for dependency management, virtualenv handling, and workspace operations.

```sh
# Install uv if you do not already have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync both workspaces
make sync

# Sanity check the tree
make check-fast
```

## Code style

| Rule | Setting |
|---|---|
| Formatter / linter | [Ruff](https://docs.astral.sh/ruff/) |
| Line length | 110 |
| Type checker | [mypy](https://mypy-lang.org/) |
| Target version | Python 3.13 |
| Docstrings | Google style |

Key conventions:

- Put `from __future__ import annotations` at the top of every Python module.
- Prefer `typing.Protocol` over ABCs for interface-style contracts.
- Use Pydantic models for configuration and typed payloads where appropriate.
- Use `async` / `await` for I/O-bound code.

## Testing

Every public function and protocol implementation should have at least one test.

```sh
# Full validation
make check

# Coverage for both workspaces
make test-coverage

# Fast local loop
make test-unit
```

Markers used in the repo:

- Unmarked tests are part of the default fast path.
- `@pytest.mark.integration` — requires external services
- `@pytest.mark.e2e` — full-stack and slow
- `@pytest.mark.benchmark` — performance-focused

Coverage floors are enforced in workspace configuration:

- `core/pyproject.toml` — `fail_under = 85`
- `contrib/pyproject.toml` — `fail_under = 70`

Treat those as minimums, not targets.

## Linting and type checking

The usual contributor loop is:

```sh
make fmt-check
make lint
make typecheck
```

To apply auto-fixes:

```sh
make fmt
```

## Import layering

pykit enforces a layered architecture with [import-linter](https://import-linter.readthedocs.io/). Lower layers must not import higher ones.

At a high level, the stack moves from foundations upward:

| Layer group | Packages |
|---|---|
| Foundation | `pykit-errors`, `pykit-config`, `pykit-logging` |
| Core capabilities | `pykit-validation`, `pykit-encryption`, `pykit-util`, `pykit-version`, `pykit-media` |
| Contracts and patterns | `pykit-hook`, `pykit-provider`, `pykit-component`, `pykit-resilience`, `pykit-schema` |
| Composition | `pykit-di`, `pykit-bootstrap`, `pykit-observability`, `pykit-chain` |
| Runtime and flow | `pykit-pipeline`, `pykit-dag`, `pykit-worker`, `pykit-sse`, `pykit-stateful` |
| Security and data | `pykit-auth`, `pykit-authz`, `pykit-security`, `pykit-discovery`, `pykit-database`, `pykit-cache`, `pykit-storage`, `pykit-messaging`, `pykit-httpclient` |
| Transport and AI | `pykit-server`, `pykit-grpc`, `pykit-llm`, `pykit-embedding`, `pykit-vectorstore`, `pykit-mcp`, `pykit-ai`, `pykit-inference`, `pykit-bench`, `pykit-dataset`, `pykit-transcription` |
| Top-level tooling and apps | `pykit-skill`, `pykit-agent`, `pykit-workload`, `pykit-process`, `pykit-git`, `pykit-testutil`, `pykit-integration`, plus contrib adapters |

The main layer contract lives in `core/pyproject.toml`. If your change affects imports, package boundaries, or domain ownership, also run:

```sh
cd core && uv run import-linter
```

If you add or move packages, update `domains.toml` so the `make check-<domain>` gates stay accurate.

## Adding a new package

1. Decide whether the package belongs in `core/packages/` or `contrib/`.
2. Create the package with the usual `src/<package_name>/` and `tests/` layout.
3. Use a nearby package in the same area as the template for `pyproject.toml`.
4. Register the package in the matching workspace file:
   - `core/pyproject.toml` for core packages
   - `contrib/pyproject.toml` for contrib packages
5. Update the matching workspace metadata as needed:
   - dependency groups
   - `tool.uv.sources`
   - coverage `source_pkgs`
   - Ruff first-party settings
   - import-linter config when the package affects layering
6. Update `domains.toml` if the package changes domain membership.
7. Wire the package into the `pykit` facade when it belongs in the public facade.
8. Update the package tables in `README.md` and the relevant docs.
9. If the API shape needs early discussion, open an issue first. The repo includes an [engineering review issue template](.github/ISSUE_TEMPLATE/engineering_review.yml) for architecture-heavy proposals.

## Pull request process

1. Create a feature branch from `main`.

   ```sh
   git checkout -b feat/my-feature
   ```

2. Make the smallest coherent change that solves the problem.
3. Run the relevant checks. For most changes, `make check-fast` during development and `make check` before opening the PR are the right defaults.
4. If the change should be called out in release notes, update `CHANGELOG.md` under `## [Unreleased]`.
5. Push your branch and open a PR against `main`.
6. Fill in the PR description with the problem, the change, and anything reviewers should focus on.
7. Request review from a maintainer.
8. Address review comments in follow-up commits.
9. A maintainer will merge once the PR is approved.

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|---|---|
| `feat:` | New features |
| `fix:` | Bug fixes |
| `docs:` | Documentation only |
| `ci:` | CI/CD changes |
| `refactor:` | Code changes without a feature or fix |
| `test:` | Adding or fixing tests |
| `chore:` | Maintenance |

Examples:

```text
feat(pykit-resilience): add bulkhead limiter
fix(pykit-auth): handle expired JWT edge case
docs: add per-package READMEs
```

## Deprecation policy

pykit is still pre-1.0. While the repo is in `0.x`, maintainers may remove or reshape public APIs in a minor release when that leads to a better long-term design.

Once a package reaches `1.0.0`, use the full deprecation process in [`docs/policy/DEPRECATION.md`](docs/policy/DEPRECATION.md), including PEP 702-style deprecation markers and release-note guidance.

## Release process

Releases are maintainers-only work. For contributors, the main things to know are:

- package versions are currently aligned at `0.1.0`
- releases and versioning rules are documented in [`docs/RELEASING.md`](docs/RELEASING.md) and [`docs/VERSIONING.md`](docs/VERSIONING.md)
- breaking changes and notable user-facing changes should be documented in `CHANGELOG.md`

## Related documents

- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — community expectations
- [SECURITY.md](SECURITY.md) — vulnerability reporting and supply-chain policy
- [GOVERNANCE.md](GOVERNANCE.md) — roles and decision-making
- [MAINTAINERS.md](MAINTAINERS.md) — current maintainers and ownership
- [CHANGELOG.md](CHANGELOG.md) — release history
- [docs/RELEASING.md](docs/RELEASING.md) — release mechanics
- [docs/VERSIONING.md](docs/VERSIONING.md) — versioning guide
- [docs/policy/SEMVER.md](docs/policy/SEMVER.md) — semantic versioning policy
- [docs/policy/DEPRECATION.md](docs/policy/DEPRECATION.md) — deprecation lifecycle
- [docs/adr/](docs/adr/) — architecture decision records

## Sibling-parity reminder

Public abstractions such as `AppError`, `Component`, `Provider`, `Pipeline`, and lifecycle hooks are evaluated across [gokit](https://github.com/kbukum/gokit), [rskit](https://github.com/kbukum/rskit), and pykit. If you change one of those surfaces here, call out the parity impact in your PR.
