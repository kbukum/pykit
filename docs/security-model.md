# Security Model

This document defines the pykit security baseline for `pykit-auth`, `pykit-authz`,
`pykit-security`, and `pykit-encryption`.

## Threat model

- Network attackers must not downgrade token, TLS, or redirect protections.
- Stored credentials must remain unusable if database contents leak.
- Authorization defaults to deny when role or attribute policy data is missing.
- Secrets, tokens, and key material must never be logged or accepted through URLs.

## Authentication

### JWT

- Default signing algorithm: **RS256**.
- Allowed verifier algorithms: **RS256**, **ES256**, **EdDSA**.
- **HS256** is internal-only and requires explicit opt-in plus a 32-byte minimum secret.
- Required claims: `iss`, `aud`, `exp`, `nbf`, `iat`.
- Clock skew tolerance is explicit and capped at **60 seconds**.
- Tokens with `alg: none` or mismatched header algorithms are rejected before verification.

### Passwords

- Default hash: **Argon2id**.
- Minimum parameters:
  - memory: **64 MiB**
  - iterations: **3**
  - parallelism: **4**
- **bcrypt** remains verification-compatible only for migration of existing hashes.
- `PasswordHasher.needs_rehash()` marks bcrypt or outdated Argon2id hashes for replacement.

### API keys

- Keys are generated with random entropy and stored only as **HMAC-SHA-256 digests**.
- Digests are keyed with a required **pepper** (32-byte minimum).
- Validation uses prefix lookup plus **constant-time** digest comparison.
- Scope checks are explicit and rotation supports bounded grace windows.

### OIDC

- Discovery metadata must use **HTTPS** endpoints.
- Public clients require **PKCE (S256)**.
- Redirect URIs are **exact-match** only; no wildcards.
- Callback validation enforces **state** and **nonce** checks.
- JWKS retrieval is cached with bounded refresh for key rotation.
- Refresh-token rotation is on by default: unchanged or missing replacement refresh tokens are rejected.

## Authorization

- Canonical model: **RBAC + ABAC**.
- RBAC supports role inheritance.
- ABAC supports explicit **allow** and **deny** rules.
- Evaluation order:
  1. explicit ABAC deny
  2. ABAC allow
  3. RBAC allow
  4. default deny
- Missing roles, unknown resources, or unmatched rules must all resolve to **deny**.

## Transport and HTTP security

- TLS minimum default: **TLS 1.3**, with **TLS 1.2 floor**.
- `pykit-security` emits secure-by-default headers:
  - `Strict-Transport-Security`
  - `Content-Security-Policy`
  - `X-Content-Type-Options`
  - `X-Frame-Options`
  - `Referrer-Policy`
  - `Permissions-Policy`
- Bearer tokens are **header-only**. Query-string tokens are rejected.
- CORS policies are exact-match and opt-in by origin.

## Token and key lifecycle

- JWT signing keys are configured explicitly; no global registries or auto-registration.
- API keys rotate to new digests and may enter a bounded grace period.
- OIDC JWKS cache refreshes on TTL expiry and once more on key miss.
- Refresh tokens are expected to rotate on each successful exchange.
