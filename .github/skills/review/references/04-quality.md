# Pass 04 — Quality, readability & maintainability

This is the pass the user cares about most: **is the code readable, maintainable, and well
organized — or is it piled into one file?** Correctness passes (`02`, `03`) can be green while
the code is still a maintenance liability. Vibe-coded output tends to grow one giant file with a
few 300-line functions; this pass rejects that.

> **Run in a separate, clean-context agent** — never inline in the session that wrote the code.
> An independent reviewer re-derives every judgment from the code and the principles instead of
> trusting prior reasoning. A plan/spec may be passed in as a scope checklist only; it never
> excuses a baseline violation.

**Scope note.** *Changes mode:* judge the readability of the touched files and functions.
*Project mode:* sweep for oversized files, god-packages, and duplicated logic across the tree.

## File & package organization (primary focus)

- **No piling into one file.** A package's functionality is split into focused modules by concern
  — e.g. `client.py`, `options.py`, `errors.py`, `types.py`, `registry.py` — not one 800-line
  `__init__.py` or `<name>.py` holding everything. A single file that mixes types, construction,
  transport, and helpers is a **should-fix**; refactor into cohesive modules.
- **One clear responsibility per file.** A reader should predict a file's contents from its name.
  Group related types + their methods together; keep unrelated concerns in separate files.
- **Cohesive packages.** A package is one concept. A grab-bag `utils`/`helpers` module accreting
  unrelated functions is a smell — place each helper with the concern it serves, or in the
  canonical owner (pass `01`).
- **Right-sized functions.** A function that does not fit on a screen or mixes several abstraction
  levels should be decomposed. Deeply nested conditionals → early returns / guard clauses. Prefer
  small, named helpers over inline complexity.

## Readability

- **Names reveal intent.** No cryptic abbreviations, no `data2`/`tmp3`, no misleading names.
  Public identifiers read well at the call site and use Python naming conventions.
- **Straight-line where possible.** Minimize state and mutation; prefer clear sequential logic over
  clever one-liners. Complexity that must exist is isolated and named.
- **Errors add context.** Translate exceptions with `raise ... from e` and a message/code that says
  what failed, not a bare catch that loses the call site.

## Maintainability

- **DRY within reason.** Copy-pasted blocks with small tweaks → one parameterized helper. (But do
  not over-abstract a single use.)
- **No dead or speculative code.** No commented-out blocks (git history exists), no unused public
  exports, no "might need it later" scaffolding. Remove it.
- **Consistent with neighbors.** Matches the patterns of the surrounding package (Protocol shape,
  pydantic model style, constructor/config pattern, error style) rather than introducing a one-off
  style.

## Detection starters

Read each hit — size and nesting are signals, not automatic verdicts.

```bash
# largest Python files (piling-into-one-file candidates)
find core/packages contrib -name '*.py' -not -path '*/tests/*' -print0 | xargs -0 wc -l | sort -rn | head -30
# packages that are a single big runtime module (no concern split)
for d in $(find core/packages contrib -path '*/src/*' -type d | sort); do   n=$(find "$d" -maxdepth 1 -name '*.py' ! -name '__init__.py' | wc -l); echo "$n $d"; done | sort -n | head
# grab-bag modules/packages
find core/packages contrib -type d \( -name utils -o -name helpers -o -name common -o -name misc \)
find core/packages contrib -name 'utils.py' -o -name 'helpers.py' -o -name 'common.py'
# commented-out code / stale markers
rg -n '^\s*#\s*(def|class|if|for|while|return|await|async|from|import)' core/packages contrib -g '*.py'
rg -n 'TODO|FIXME|HACK|XXX' core/packages contrib -g '*.py'
```

Then run `make fmt-check` and `make lint` — a clean ruff format/lint run is necessary but not
sufficient; the organization judgments above are the point of this pass.

## Output for this pass

For each finding, name the concrete refactor: which file to split, into which files, and along
which concern boundary — so it is directly actionable, not just "this file is too big".
