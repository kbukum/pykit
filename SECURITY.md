# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in pykit, please report it
**privately** using one of the following channels:

1. **Preferred**: [GitHub Security Advisories](https://github.com/kbukum/pykit/security/advisories/new)
   — opens a private disclosure thread visible only to maintainers.
2. **Alternative**: Email the maintainers (see [MAINTAINERS.md](MAINTAINERS.md))
   with subject prefix `[SECURITY]`.

Do **not** open a public GitHub issue for security reports.

### What to Include

- A clear description of the issue and its potential impact.
- Steps to reproduce, including a minimal proof-of-concept if possible.
- The affected version(s) and Python version.
- Any suggested mitigations or fixes.

### What to Expect

- **Acknowledgment** within 48 hours of your report.
- **Status update** within 5 business days with an assessment.
- **Fix timeline** communicated once the issue is confirmed.
- **CVE assignment** for confirmed vulnerabilities affecting released
  versions, requested via GitHub Security Advisories.
- **Credit** in the release notes and the advisory (unless you prefer to
  remain anonymous).

### Disclosure Policy

- We follow [coordinated disclosure](https://en.wikipedia.org/wiki/Coordinated_vulnerability_disclosure).
- Please allow a reasonable embargo period (typically 90 days) before any
  public disclosure, extendable by mutual agreement when a fix requires
  coordination across downstream consumers.
- Once a fix is released, the advisory is published and CVE details are
  made public.

## Security Best Practices for Users

When using pykit in production:

- Keep dependencies up to date (`uv lock --upgrade && uv sync`).
- Use the `pykit-encryption` package for sensitive data at rest.
- Configure TLS via the `pykit-security` package for all network
  communication — never disable certificate verification in production.
- Never commit secrets — use environment variables or secret managers
  (`pykit-config` integrates with Pydantic Settings for env-based config).
- Review `pip-audit` and `bandit` findings regularly. CI runs `pip-audit`
  on every push.
- For HTTP authentication, prefer the secure-by-default middleware in
  `pykit-auth`. Avoid query-string token fallbacks unless absolutely
  necessary.
- Avoid `pickle` for untrusted input — use `pykit-schema` (Pydantic) for
  structured deserialization.

## Supply Chain

- All GitHub Actions used in CI are pinned to commit SHAs (see
  `.github/workflows/`).
- Dependency updates are automated via Dependabot
  (`.github/dependabot.yml`).
- The Python toolchain is pinned via `.python-version` and
  `requires-python` in `pyproject.toml`; CI enforces this invariant.
- Releases are signed with [Sigstore](https://www.sigstore.dev/) via
  `pypa/gh-action-pypi-publish` (Trusted Publishing). SBOMs (CycloneDX)
  are attached to each release.
- The lockfile (`uv.lock`) is committed and checked in CI via
  `uv lock --check`.
