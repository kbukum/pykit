# Governance
This document explains how the pykit project makes decisions and assigns responsibility.

## Project status

pykit is **pre-stable** (`v0.x`). Backward compatibility is **not** guaranteed between `v0.x` releases. Breaking changes are acceptable when they lead to a cleaner long-term design. See [CHANGELOG.md](CHANGELOG.md) for the release history.

## Sibling-parity contract

pykit is part of a sibling trio that intentionally mirrors module structure, naming, and patterns:

- [`kbukum/gokit`](https://github.com/kbukum/gokit) — Go
- [`kbukum/rskit`](https://github.com/kbukum/rskit) — Rust
- [`kbukum/pykit`](https://github.com/kbukum/pykit) — Python

When a public abstraction such as `AppError`, `Component`, `Provider`, `Pipeline`, lifecycle hooks, error codes, or configuration semantics changes in one sibling, the same change should be evaluated for the other two. Drift is treated as a finding and tracked in cross-sibling issues.

## Roles

### Contributors

Anyone who opens an issue or pull request is a contributor. Contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md) and the [Contribution Guide](CONTRIBUTING.md).

### Reviewers

Reviewers are contributors who have shown sustained engagement and are trusted to approve pull requests in specific areas of the codebase. Reviewer ownership is recorded in [.github/CODEOWNERS](.github/CODEOWNERS).

### Maintainers

Maintainers have merge rights and are responsible for the long-term direction of the project. The current list is in [MAINTAINERS.md](MAINTAINERS.md).

## Decision-making

For routine changes such as bug fixes and small features, a single maintainer approval is sufficient.

For changes that affect multiple packages or alter a public API, contributors are encouraged to open a discussion or RFC-style issue first.

For significant architectural changes, at least two maintainers must approve. This includes changes such as:

- introducing a new sub-package
- removing a public package
- changing the import-layer rules
- changing the release process

If maintainers disagree, the proposal is deferred until consensus is reached or a clear path forward is documented in an [ADR](docs/adr/).

## Release process

Releases are cut by maintainers following [docs/RELEASING.md](docs/RELEASING.md). Each release must include a `CHANGELOG.md` entry in [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. CI enforces the single `[Unreleased]` heading invariant.

## Security issues

Security issues follow the dedicated process in [SECURITY.md](SECURITY.md). They are not handled through the normal public issue tracker.

## Amendments

This document may be amended by pull request. Amendments require approval from a majority of current maintainers.
