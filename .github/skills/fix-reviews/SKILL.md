---
name: fix-reviews
description: "pykit: Evaluate PR review comments and fix valid patterns across the affected change; only when asked."
user-invocable: true
---

# Fix review patterns

Act only when asked. Apply the [baseline](../../copilot-instructions.md), not suggestions that conflict with it.

1. Identify the PR and retrieve reviews, inline comments, and paginated GraphQL review threads with resolution state and node IDs. `gh pr view` covers summary bodies; `gh api .../pulls/<n>/comments --paginate` covers inline comments.
2. Evaluate each comment against current source. Reject invalid suggestions with a reason; do not reply under the maintainer's name.
3. Identify the underlying pattern and search the changed files plus close callers/callees. Fix every valid instance there, including pre-existing defects; explain wider scope and leave unrelated code alone.
4. Make cohesive root-cause fixes. Behavioral changes require failing tests first, including failure paths. Preserve edits and staging.
5. Use `validate` for the smallest affected gates. Prose-only fixes require documentation checks, not application builds.
6. Commit and push only when explicitly authorized, using `commit`. Resolve addressed threads with `resolveReviewThread` only after the remote contains the validated fixes. Leave rejected or decision-dependent threads unresolved.

Report unresolved comments and real blockers concisely. A request to fix reviews does not authorize publication.
