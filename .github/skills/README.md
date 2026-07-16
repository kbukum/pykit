# pykit development skills

[Agent Skills](https://docs.github.com/copilot/concepts/agents/about-agent-skills) for developing
**pykit itself** — loaded on demand by GitHub Copilot (CLI, coding agent, code review, IDEs) when
a task matches a skill's description. These are **project skills** for contributors; they do not
affect anyone who consumes pykit as a dependency.

Each skill is a folder with a `SKILL.md` (YAML frontmatter + workflow) and optional bundled
reference files loaded only when the skill activates (progressive disclosure). They encode pykit's
permanent engineering baseline (see [`../copilot-instructions.md`](../copilot-instructions.md)) and
drive tasks through the repo's `make`/`uv` gates.

## Skills

| Skill | Use when |
|---|---|
| [`create-branch`](create-branch/SKILL.md) | Cut a `kbukum/`-prefixed branch off an up-to-date main, named by the high-level change (no batch/plan/internal detail). |
| [`create-plan`](create-plan/SKILL.md) | Turn a non-trivial change into a reviewable plan under `tmp/` — README + numbered step files, bound to the baseline. |
| [`apply-plan`](apply-plan/SKILL.md) | Execute a `tmp/` plan from its first unfinished step onward, validating after each; resumable. |
| [`apply-step`](apply-step/SKILL.md) | Apply one plan step in context (README + prior steps), test-first against the baseline, then mark it done. |
| [`commit`](commit/SKILL.md) | Commit staged work with one compact, developer-friendly Conventional-Commit message — no co-author trailer or plan/batch/tool narration. |
| [`create-pr`](create-pr/SKILL.md) | Open a reviewer-friendly PR — high-level summary, honest template sections, bound to the baseline. |
| [`fix-reviews`](fix-reviews/SKILL.md) | Act on PR review comments by pattern — fix every instance across the change set, then commit and resolve the threads. |
| [`validate`](validate/SKILL.md) | Build/test/lint/type-check/format-check/import-layer-check a change through make/uv, scoped to the affected packages. |
| [`review`](review/SKILL.md) | Run the eight-pass engineering-baseline review over a diff, package, or the tree. |
| [`new-package`](new-package/SKILL.md) | Scaffold a new package — core vs contrib placement, workspace/facade wiring, package docstring, import-linter layer. |
| [`new-backend`](new-backend/SKILL.md) | Add a storage/cache/messaging/inference/llm/vectorstore adapter as a typed-registration contrib package. |
| [`parity`](parity/SKILL.md) | Keep pykit at parity with rskit (the reference kit) — mirror by capability, keep the parity matrix accurate. |
| [`release`](release/SKILL.md) | Cut a release — semver bump, CHANGELOG, lock-step version bump, full gates, PyPI Trusted Publishing. |

## Conventions

- Skills are discoverable in Copilot CLI via `/skills`; project skills live under `.github/skills/`
  (also `.claude/skills` / `.agents/skills` are honored), personal skills under `~/.copilot/skills`.
- Run reviews (`review`) in a **fresh, clean-context agent**, never inline in the session that
  wrote the code.
- Validation is `make`/`uv`-first, scoped to the changed package(s) (`make lint P=<pkg>`,
  `make typecheck P=<pkg>`, `make test P=<pkg> T=<pattern>`, `make test-affected`); full-tree gates
  are for audits and releases.
- pykit mirrors **rskit** (the reference kit); keep shared abstractions and naming aligned across
  kits and the parity matrix accurate (`parity` skill).
