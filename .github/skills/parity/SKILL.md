---
name: parity
description: "pykit: Align a capability with sibling kits while preserving idiomatic APIs and tracking deliberate gaps."
user-invocable: true
---

# Cross-kit parity

Match capability and behavior, not symbols or layouts. Follow the [baseline](../../copilot-instructions.md); Python idioms take priority over transliteration.

## Choose the scope

Compare public APIs, invariants, and failures in `../rskit` and `../gokit`. The strongest implementation sets the direction for each capability; never weaken a better implementation for parity.

| Level | Use |
|---|---|
| Full | Shared infrastructure Python can support well: errors, config, providers, resilience, transport, and data |
| Light | Common Python use cases with heavy processing owned elsewhere; media retains detection, metadata, cheap image operations, time/spatial types, and subtitles |
| Kit-only | Language/framework-specific capabilities; heavy media stays rskit-only, Axum maps to Python server behavior, and ConnectRPC has no required Python peer |

## Apply

1. Identify the strongest counterpart and choose full, light, or kit-only alignment.
2. Implement test-first with typed errors, Protocols, generics, async behavior, and enforced value invariants. Preserve bounded resources and failure semantics.
3. Update `docs/parity-matrix.md`, including deliberate renames and gaps. Keep its shared module-presence table consistent with rskit's matrix.
4. Record remaining gaps for the weaker kit; do not introduce cross-kit runtime dependencies or consumer-specific infrastructure.
5. Use `validate` for affected packages and `review` for parity claims.

Use full URLs for cross-repository references. Name branches and publication text after the capability, not plan numbers. Commit, push, and open PRs only with authorization.
