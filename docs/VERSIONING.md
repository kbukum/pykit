# Versioning

Packages declare versions independently in their own `pyproject.toml`; releases currently use a lock-step train. Consumers should pin each package they install.

Before 1.0, breaking changes require a minor bump. Patches may include fixes, internal improvements, and non-breaking additions. Stable packages follow normal SemVer and the [deprecation policy](policy/DEPRECATION.md).

Tags use `pykit-<name>/vX.Y.Z` for a package or `vX.Y.Z` for the workspace train. Manifests use Python-compatible versions; verify prerelease normalization before tagging.

See [SemVer policy](policy/SEMVER.md) for the compatibility contract and [releasing](RELEASING.md) for preparation, publication, and verification.
