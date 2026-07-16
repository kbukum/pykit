---
name: parity
description: >-
    Mirror capabilities from rskit (the Rust reference kit) into pykit by capability, not blindly,
    and keep docs/parity-matrix.md accurate. Use when porting or aligning a package with its rskit
    counterpart, deciding whether something should be fully mirrored or stay rskit-only, or when
    touching anything that has a cross-kit parity row.
user-invocable: true
---

# Keeping pykit at rskit parity

pykit is a sibling kit to rskit (Rust) and gokit (Go): same module structure and naming, same
engineering baseline, idiomatic per language. **rskit received a full quality pass and is the
current reference shape/quality** for cross-kit parity; the active goal is bringing pykit to
rskit-level and release readiness. rskit lives in the sibling repo `../rskit`.

## Mirror by capability, not blindly

Parity is judged **by capability**, weighing where each language is strongest — not by copying
every rskit symbol. Decide per capability:

- **Fully mirror** when Python is equally capable and the concept is shared infrastructure (errors,
  config, di, provider shapes, resilience, transport, data adapters).
- **Light version** when Python can cover the common case but the heavy work belongs in Rust.
  **Media is the canonical example:** pykit `media` is a light standalone package — detection,
  metadata, cheap image ops, time/spatial types, subtitles (SRT/VTT). Heavy audio/video/matrix
  transcoding and codec/filter/pipeline vocabulary stay **rskit-only** by design.
- **Intentionally kit-only** when a concept is framework-specific (e.g. rskit `http` is Axum
  -specific and folds into pykit `server`; gokit `connect` is ConnectRPC-specific with no rskit or
  pykit peer). Record these as deliberate `➖` rows with a note, not gaps to close.

When in doubt about a heavy capability, prefer the light-pykit / strong-rskit split.

## Workflow

1. **Read the rskit owner.** Find the counterpart crate in `../rskit` and study its public API,
   invariants, and error model — not just its surface.
2. **Decide the mirroring level** (full / light / kit-only) using the rules above.
3. **Implement idiomatically in Python** — PEP 695 generics, Protocols (not ABCs), typed errors
   (`AppError`), pydantic v2 for data, async-first, no `Any` in public APIs. Do not transliterate
   Rust; match behavior and invariants, express them the Python way. Enforce documented value
   invariants in code (saturate/clamp, NaN guards, half-open ranges) as pykit `media` does.
4. **Update `docs/parity-matrix.md`.** Adjust the module-presence row (✅ / ➖ / ⏳) and the
   pykit-specific capability tables. The module-presence table is a shared cross-kit source
   (kept identical in `rskit/docs/parity-matrix.md`) — keep both sides consistent and note any
   intentional divergence.
5. **Flag rskit improvements upward.** If aligning pykit exposes a gap, weakness, or redesign
   opportunity in rskit, note it — rskit is foundational and multi-purpose (not pykit-specific),
   and is still in development, so improving it generically is wanted. Never make rskit
   pykit-specific.

## Naming and cross-references

- Module/package names align across kits (pykit `logging` matches rskit `logging`, etc.). Preserve
  the shared naming; call out any deliberate rename in the parity matrix.
- In PR/issue text, reference items in rskit (or any other repo) with **full URLs**, never bare
  `#123` — a bare number resolves to the current repo.
- Do not name branches/commits/PRs after internal plan or batch numbers; name by the actual
  capability change. Each PR must read standalone.

## Validate

Run the affected pykit packages through the `validate` skill and, for a real audit of the parity
claim, the `review` skill:

```bash
make test P=<pkg>
make typecheck P=<pkg>
```

Per repo workflow, **create the branch and make edits only** — the maintainer commits and pushes.
