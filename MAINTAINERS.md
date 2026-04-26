# Maintainers

This file lists the people responsible for the pykit project. Maintainers are
responsible for code review, releases, and project direction.

## Core Maintainers

| Name      | GitHub      | Areas             |
|-----------|-------------|-------------------|
| K. Bukum  | @kbukum     | All packages      |

## Bus Factor: 1 — Co-Maintainers Wanted

pykit currently has a **single core maintainer**. This is a known
sustainability risk for a project of this size (50+ packages). We are
actively looking for contributors interested in becoming co-maintainers,
particularly in the following areas:

- **Foundation**: `pykit-errors`, `pykit-config`, `pykit-logging`,
  `pykit-validation`
- **Patterns**: `pykit-provider`, `pykit-component`, `pykit-resilience`,
  `pykit-di`, `pykit-bootstrap`, `pykit-observability`
- **Data & Flow**: `pykit-pipeline`, `pykit-dag`, `pykit-worker`
- **Infrastructure**: `pykit-database`, `pykit-redis`, `pykit-messaging`,
  `pykit-storage`, `pykit-httpclient`
- **Servers**: `pykit-server`, `pykit-grpc`
- **AI/ML**: `pykit-llm`, `pykit-llm-providers`, `pykit-bench`,
  `pykit-dataset`
- **Security**: `pykit-auth`, `pykit-auth-oidc`, `pykit-auth-apikey`,
  `pykit-authz`, `pykit-encryption`

If you are interested, please open an issue using the
[engineering review template](.github/ISSUE_TEMPLATE/) describing your area
of interest and recent contributions, or start by picking up issues labelled
`good-first-issue` / `help-wanted`.

## How Maintainers Are Added

New maintainers are added by the existing core maintainers via a pull request
that updates this file. Candidates are typically long-term contributors who
have demonstrated:

- A track record of high-quality contributions across multiple areas of the
  codebase.
- Familiarity with project conventions, the uv workspace layout, the import
  layering rules (`import-linter`), and the release process.
- A commitment to responsive code review.

## Responsibilities

Maintainers are expected to:

- Review pull requests within a reasonable timeframe.
- Triage issues and security reports (see [SECURITY.md](SECURITY.md)).
- Cut releases following the process documented in
  [docs/RELEASING.md](docs/RELEASING.md).
- Uphold the [Code of Conduct](CODE_OF_CONDUCT.md).
- Maintain sibling parity with [`gokit`](https://github.com/kbukum/gokit)
  and [`rskit`](https://github.com/kbukum/rskit).

## Becoming Inactive / Stepping Down

A maintainer who has been inactive for 6 months may be moved to an "Emeritus"
section by the remaining maintainers. Maintainers are encouraged to step down
explicitly by opening a PR to update this file.

## Emeritus Maintainers

_No emeritus maintainers yet._

## Contact

For routine project communication, use GitHub issues or discussions.
For security issues, see [SECURITY.md](SECURITY.md).
