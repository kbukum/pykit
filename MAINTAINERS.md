# Maintainers
This file lists the people responsible for pykit and explains how maintainership works.

## Core maintainers

| Name | GitHub | Areas |
|---|---|---|
| K. Bukum | @kbukum | All packages |

## Bus factor: 1

pykit currently has a **single core maintainer**. That is a real sustainability risk for a project of this size. We are actively looking for contributors who want to grow into co-maintainer roles, especially in these areas:

- **Foundation** — `pykit-errors`, `pykit-config`, `pykit-logging`, `pykit-validation`
- **Patterns** — `pykit-provider`, `pykit-component`, `pykit-resilience`, `pykit-di`, `pykit-bootstrap`, `pykit-observability`
- **Data and flow** — `pykit-pipeline`, `pykit-dag`, `pykit-worker`
- **Infrastructure** — `pykit-database`, `pykit-cache`, `pykit-messaging`, `pykit-storage`, `pykit-httpclient`
- **Servers** — `pykit-server`, `pykit-grpc`
- **AI/ML** — `pykit-llm`, `pykit-llm-providers`, `pykit-bench`, `pykit-dataset`
- **Security** — `pykit-auth`, `pykit-authz`, `pykit-security`, `pykit-encryption`

If you are interested, open an issue with the [engineering review template](.github/ISSUE_TEMPLATE/engineering_review.yml) describing your area of interest and recent contributions, or start by picking up issues labelled `good-first-issue` or `help-wanted`.

## How maintainers are added

New maintainers are added by the existing core maintainers through a pull request that updates this file. Candidates are usually long-term contributors who have shown:

- a track record of high-quality contributions across multiple areas of the codebase
- familiarity with project conventions, the uv workspace layout, the import-layer rules, and the release process
- a commitment to responsive code review

## Responsibilities

Maintainers are expected to:

- review pull requests within a reasonable timeframe
- triage issues and security reports (see [SECURITY.md](SECURITY.md))
- cut releases following [docs/RELEASING.md](docs/RELEASING.md)
- uphold the [Code of Conduct](CODE_OF_CONDUCT.md)
- maintain sibling parity with [`gokit`](https://github.com/kbukum/gokit) and [`rskit`](https://github.com/kbukum/rskit)

## Inactivity and stepping down

A maintainer who has been inactive for 6 months may be moved to an emeritus section by the remaining maintainers. Maintainers are encouraged to step down explicitly by opening a pull request that updates this file.

## Emeritus maintainers

_No emeritus maintainers yet._

## Contact

For routine project communication, use GitHub issues or discussions. For security issues, see [SECURITY.md](SECURITY.md).
