## Description

<!-- Provide a clear and concise description of your changes -->

## Motivation

<!-- Why is this change needed? What problem does it solve? -->
<!-- Link to related issues: Fixes #123 or Closes #456 -->

## Type of Change

<!-- Mark the relevant option with an 'x' -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Test coverage improvement

## Package(s) Affected

<!-- List the packages this PR changes (e.g., pykit-server, pykit-database, pykit-logging) -->

-

## Changes Made

<!-- List key changes in bullet points -->

-
-
-

## Testing

<!-- Describe how you tested your changes -->

- [ ] Added new tests for my changes
- [ ] All existing tests pass (`uv run pytest`)
- [ ] Linter passes (`uv run ruff check packages/`)
- [ ] Type-check passes (`uv run mypy packages/`)
- [ ] Import layering passes (`uv run lint-imports`)
- [ ] Manual testing performed (describe below if applicable)

### Test Evidence

<!-- Optional: show test output, screenshots, or logs demonstrating your changes work -->

```
$ uv run pytest packages/pykit-<name>/
...
```

## Breaking Changes

<!-- If this is a breaking change, describe the impact and migration path -->

## Sibling Parity

<!-- pykit mirrors gokit and rskit. If this change touches a public abstraction
(error codes, Component lifecycle, Provider, Pipeline, etc.), confirm parity
or link the corresponding sibling issue. -->

- [ ] Sibling-parity not required (internal change)
- [ ] Sibling-parity tracked: gokit#___, rskit#___

## Checklist

- [ ] My code follows the [coding standards](../CONTRIBUTING.md#code-style) in CONTRIBUTING.md
- [ ] I have run `uv lock` and committed `uv.lock` if dependencies changed
- [ ] I have added Google-style docstrings for new public functions/classes
- [ ] I have updated relevant documentation (README.md, package README, etc.)
- [ ] I have added tests that prove my fix/feature works
- [ ] I have considered backward compatibility
- [ ] New dependencies (if any) are justified and minimal
- [ ] CHANGELOG entry added under `[Unreleased]`

## Additional Notes

<!-- Any extra context, screenshots, or information for reviewers -->
