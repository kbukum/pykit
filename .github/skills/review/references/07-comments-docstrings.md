# Pass 07 — Comments & docstring semantics

The final pass, and a subtle one: comments and docstrings are trusted by future readers and by
published Python docs, so a **wrong** comment is worse than no comment. Vibe-coded comments tend
to narrate the obvious, restate the code, or describe what the code *used to* do. This pass keeps
prose truthful and useful.

> **Run in a separate, clean-context agent** — never inline in the session that wrote the code.
> An independent reviewer re-derives every judgment from the code and the principles instead of
> trusting prior reasoning. A plan/spec may be passed in as a scope checklist only; it never
> excuses a baseline violation.

**Scope note.** *Changes mode:* read every comment and docstring line in the diff against the code
beside it. *Project mode:* sample docstrings across packages, prioritizing public API docstrings
that generated docs render.

## Checks

- **Docstrings are accurate.** Each Google-style docstring matches what the function/class/module
  actually does now — arguments, return values, exceptions, side effects, async/concurrency
  ownership, and security-sensitive constraints. A docstring that describes old behavior after a
  change is a should-fix (it will mislead every future reader and ship in published docs).
- **Docstring convention.** Public modules, classes, functions, methods, and attributes that form
  the package API are documented with Google-style sections (`Args:`, `Returns:`, `Raises:`) when
  applicable. Package overview lives in the package `__init__.py` docstring. Public API docs tie to
  pass `06`; here the focus is *correctness* of the prose.
- **Comments earn their place.** Explain **why** — the non-obvious constraint, invariant, or
  trade-off — not **what** the code plainly says. Delete comments that merely restate the line
  below them.
- **No historical narration.** Comments describe the code as it is now, not the bug that was fixed
  or how it used to work. "Previously we… now we…" belongs in the commit message / git history,
  not the source. Flag every instance.
- **No stale references.** Comments don't name removed types, old parameter names, dead flags, or
  moved files. TODO/FIXME/HACK carry a tracked issue link or they don't belong (ties to pass `04`).
- **Accurate, minimal.** When in doubt, fewer comments — but the ones present must be correct. A
  misleading comment is a should-fix even if the code is right.

## Detection starters

Comment semantics are read-and-judge work; these only surface candidates.

```bash
# historical narration in comments/docstrings
rg -n '(previously|used to|old |before we|now we|changed to|no longer)' core/packages contrib -g '*.py'
# comments that may restate code rather than explain why
rg -n '^\s*#\s*(set|get|create|delete|update|return|call|loop|check)' core/packages contrib -g '*.py'
# stale-marker comments
rg -n 'TODO|FIXME|HACK|XXX' core/packages contrib -g '*.py'
# public API candidates whose docstrings need a semantic read
rg -n '^(def|async def|class) [A-Za-z][A-Za-z0-9_]*' core/packages contrib -g '*.py' -g '!**/tests/**'
```

Then read the docstring on each changed public identifier next to its implementation and confirm
the prose is true. Accurate docstrings that explain behavior, contracts, and non-obvious
constraints pass; anything describing old behavior, restating the obvious, or narrating the fix
does not.
