---
name: release
description: "pykit: Prepare or publish a release through the repository's version, validation, and supply-chain gates."
user-invocable: true
---

# Release

Follow [releasing](../../../docs/RELEASING.md) and the [baseline](../../copilot-instructions.md). Packages have independent manifests and currently release in lock-step; `core/` and `contrib/` own separate lockfiles.

1. Inspect tags, manifest versions, the release workflow, and the requested scope.
2. Run full acceptance, coverage, architecture, dependency checks, and a project review. Green CI does not replace checks absent from the release workflow.
3. Prepare consistent versions, locks, and concise dated changelog notes. Preserve history and document breaks; verify SemVer/PEP 440 mapping.
4. Review the exact diff and artifact set. Commit, tag, push, and publish only with explicit authorization; otherwise leave preparation for the maintainer.
5. Verify registry installs, workflow commit/tag, hosted assets, SBOM, and provenance. Published versions and tags are immutable; recover forward.

Never discard user work, weaken gates, use floating actions, or retain credentials. Use full URLs for cross-repository references.
