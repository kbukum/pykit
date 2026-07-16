# Pass 03 — Security & privacy

A dedicated pass because a vibe-coded path that "just works" usually skips boundary validation,
and pykit is shared infrastructure — a gap here propagates to every consumer. For a deeper
sweep on security-sensitive changes, pair this with a dedicated security review; this pass is
the standing baseline.

> **Run in a separate, clean-context agent** — never inline in the session that wrote the code.
> An independent reviewer re-derives every judgment from the code and the principles instead of
> trusting prior reasoning. A plan/spec may be passed in as a scope checklist only; it never
> excuses a baseline violation.

**Scope note.** *Changes mode:* trace each new input path from its trust boundary to its use.
*Project mode:* audit the toolkit's external-facing surfaces (HTTP, process, storage/database
adapters, auth, crypto) for the invariants below.

## Checks

- **Validate at every trust boundary.** Untrusted input is validated before use; least-privilege
  and secure-by-default. An input that flows into a query, a path, a command, a deserialization, or
  a model/tool-call boundary without validation is a blocker.
- **Injection-safe data access.** Parameterized queries only — never f-string/concatenated SQL.
  Argv-only subprocess execution with `shell=False`; no shell interpolation of untrusted input.
- **Token hygiene.** Tokens/credentials go in headers, never query strings; never logged. Redact
  sensitive fields in errors and logs. Auth is header-only; reject query-string tokens.
- **Current crypto.** No deprecated/weak algorithms (MD5, SHA-1 for security, DES, ECB, static
  IVs, hard-coded keys); use current primitives (AES-GCM, ChaCha20-Poly1305, Argon2id, Ed25519,
  RS256/ES256). Reject `alg: none` in JWT; require `exp`/`iss`/`aud`. Crypto belongs in
  `pykit-encryption` / `pykit-security`, not hand-rolled.
- **Data minimization.** Minimize, redact, and retention-bound sensitive data; do not persist or
  log more than needed. Bound reads of untrusted input and reject oversized payloads before
  buffering them in memory.

## Detection starters

Read each hit to judge intent — these flag candidates, not verdicts.

```bash
# string-built SQL / shelled commands with interpolation
rg -n 'f".*(SELECT|INSERT|UPDATE|DELETE)|\.format\(.*(SELECT|INSERT|UPDATE|DELETE)|shell=True|bash -c|sh -c' . -g '*.py'
# secrets in URLs/logs, or logging a token/password/secret
rg -n '(token|secret|password|api_?key)=' . -g '*.py'
rg -ni '(logger\.|logging\.|structlog).*?(token|secret|password|apikey|api_key)' . -g '*.py'
# weak crypto / alg:none
rg -ni 'md5|sha1|DES|ECB|alg.*none|verify_signature\s*=\s*False' . -g '*.py'
# hard-coded credentials
rg -n '(password|secret|api_key|apikey|token)\s*[:=]\s*["']' . -g '*.py' -g '!**/tests/**'
# untrusted path and file access candidates
rg -n 'Path\(|open\(|read_text\(|write_text\(|read_bytes\(|write_bytes\(' . -g '*.py'
```

Flag any unbounded read of untrusted input (set explicit size limits) and any path/selector from
an untrusted source flowing into filesystem or process execution without validation. Path-shaped
values use `pathlib.Path` safely with containment checks; tests use the pytest `tmp_path` fixture
rather than hardcoded filesystem locations.
