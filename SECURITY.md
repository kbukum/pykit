# Security Policy
This document explains which versions are supported and how to report security issues privately.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | :white_check_mark: |

## Reporting a vulnerability

Please report vulnerabilities **privately** through [GitHub Security Advisories](https://github.com/kbukum/pykit/security/advisories/new). That opens a private disclosure thread visible only to maintainers.

Do **not** open a public GitHub issue for a security report.

## What to include

Include as much of the following as you can:

- a clear description of the issue and its impact
- steps to reproduce, ideally with a minimal proof of concept
- the affected version or versions
- the Python version you tested with
- any suggested mitigations or fixes

## What to expect

- **Acknowledgment** within 48 hours
- **Status update** within 5 business days with an assessment
- **Fix timeline** once the issue is confirmed
- **CVE assignment** for confirmed vulnerabilities affecting released versions, requested through GitHub Security Advisories
- **Credit** in the advisory and release notes unless you prefer to stay anonymous

## Disclosure policy

- We follow [coordinated disclosure](https://en.wikipedia.org/wiki/Coordinated_vulnerability_disclosure).
- Please allow a reasonable embargo period, typically 90 days, before public disclosure.
- The embargo may be extended by mutual agreement when a fix requires coordination across downstream consumers.
- Once a fix is released, the advisory is published and CVE details become public.

## Security best practices for users

When using pykit in production:

- Keep dependencies up to date.

  ```sh
  cd core && uv lock --upgrade && uv sync
  cd ../contrib && uv lock --upgrade && uv sync
  ```

- Use `pykit-encryption` for sensitive data at rest.
- Configure TLS through the relevant transport or security package. Do not disable certificate verification in production.
- Never commit secrets. Use environment variables or a secret manager instead.
- Review `pip-audit` and `bandit` findings regularly. This repo runs both in CI.
- For HTTP authentication, prefer the secure-by-default middleware in `pykit-auth`. Avoid query-string token fallbacks unless there is no better option.
- Avoid `pickle` for untrusted input. Prefer schema-validated structured deserialization.

## Supply chain and CI security

The repo currently enforces the following security checks and release safeguards:

- GitHub Actions workflows are pinned to commit SHAs in `.github/workflows/`.
- CI runs `uv lock --check` in both `core/` and `contrib/`.
- The dedicated security workflow runs **CodeQL**, **pip-audit**, and **bandit**.
- Dependency updates are managed through `.github/dependabot.yml`.
- Python compatibility is pinned in `.python-version` and in the workspace `requires-python` settings.
- Releases publish to PyPI with **Trusted Publishing (OIDC)**.
- The release workflow generates **build provenance attestations** and attaches a **CycloneDX SBOM** to the GitHub release.
