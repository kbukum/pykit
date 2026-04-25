# pykit — OSS Engineering Review (v1.0 readiness)

> **Scope.** Aggregates four dimension audits (`pykit-dim1` … `pykit-dim4`) of the pykit Python workspace (55 packages, Python 3.13, uv 0.9.26, hatch backend) into a single OSS-engineering review patterned after the gokit gold-standard review. Every finding from the four dim files is preserved with a stable `PY-*` ID and a verbatim `path:Lstart-Lend` evidence pointer. Source dim files remain the authoritative location for Med/Low/Nit narrative; this document collects Critical/High inline.

---

## § 1 Executive Summary

1. **NOT READY for v1.0.** 55 packages, all pinned at `version = "0.1.0"`, none ever published to PyPI. Workspace fails its own static gates (mypy crashes, import-linter contract is broken), 10 unit tests in `pykit-discovery` are red, 5 transitive CVEs ride on the lockfile-that-isn't-tracked. See § 9 verdict.
2. **Static type contract is theatre.** `mypy --strict` is configured to type-check **5 of 55** packages (`pykit-discovery/pyproject.toml:259-272`) and even that fails on a duplicate `test_edge_cases` module name (`tooling-pykit.log.mypy:1-9`). 50 packages have no static type gate. Public APIs leak `Any` in 271 sites across 46 files.
3. **Architecture contract is broken at HEAD.** `[tool.importlinter]` declares `pykit_grpc` strictly above `pykit_discovery`, but `packages/pykit-grpc/src/pykit_grpc/discovery_channel.py:12-13` imports `pykit_discovery.{types,protocols}` — a textbook layer violation. Only **39 of 55** packages are even named in the contract.
4. **Tests are red and the suite is single-process.** `pytest -q` produces 10 failures in `pykit-discovery` (`DiscoveryComponent` ctor drift: tests pass `provider=`, code requires `config=`); the workflow runs `pytest -n auto` but `pytest-xdist` is not installed, so `-n auto` is silently ignored and the suite is serial. OTLP integration tests block on `localhost:4318`.
5. **Five live CVEs in the resolved environment** (`tooling-pykit.log.audit3`): `cryptography 46.0.6` → 46.0.7 (CVE-2026-39892), `pip 26.0.1` → 26.0.2 (CVE-2026-3219), `pygments 2.19.2` → 2.20.0 (CVE-2026-4539), `pytest 9.0.2` → 9.0.3 (CVE-2025-71176), `python-multipart 0.0.24` → 0.0.26 (CVE-2026-40347). No CI step would have caught these.
6. **There is no HTTP framework adapter at all.** `pykit-server` is gRPC-only (`packages/pykit-server/src/pykit_server/base.py:25-119`); `pykit-server-middleware` is hand-rolled raw-ASGI (tracing, prometheus, ratelimit, tenant). Missing: **AuthMiddleware**, **`/healthz`/`/readyz`**, **CORS**, **CSRF**, **OIDC ID-token verifier** (only `refresh_token` exists), **JWKS cache**. Anything HTTP-shaped a downstream user wants is an exercise for the reader.
7. **Coverage 90.81% global is misleading.** Three packages live well below the supposed 80% floor: `pykit-discovery` 42.7%, `pykit-vector-store` 66.7%, `pykit-dataset` 68.4%. The `fail_under` gate is set to **60** (`pyproject.toml:236`) — half of actual — so regressions to ~61% would still pass.
8. **CI is one workflow, all jobs unpinned, no security, no release, no matrix.** `.github/workflows/ci.yml` exists; that's the entire automation surface. `actions/checkout@v4` and `astral-sh/setup-uv@v5` use mutable tags (12 references). No CodeQL, Semgrep, Bandit, pip-audit, SBOM, Sigstore, no PyPI Trusted Publishing, no Dependabot, no fuzz job. No `uv sync --locked` gate. `uv.lock` is in `.gitignore` (`.gitignore:171-173`) — workspace is **not byte-reproducible**.
9. **Project hygiene is half-shipped.** Missing root files: `SECURITY.md`, `CODE_OF_CONDUCT.md` (README **falsely** points to `docs/code_of_conduct.md` that does not exist), `MAINTAINERS.md`, `GOVERNANCE.md`, `CODEOWNERS`, `.editorconfig`, `.gitattributes`, `.pre-commit-config.yaml`, `.github/dependabot.yml`, `ISSUE_TEMPLATE/`, `PULL_REQUEST_TEMPLATE.md`, `CHANGELOG.md`. Existing docs assume tooling that is not present.
10. **What works.** Ruff + format pass clean; mypy/import-linter are at least *configured* (vs. "absent"); 88/88 `# type: ignore` are scoped (`[code]`); 53/55 `__init__.py` declare `__all__`; `hmac.compare_digest` and AES-GCM with random 96-bit nonce are used correctly where they appear; no `pickle`, no `yaml.load`, no `shell=True`, no SQL string interpolation in core lib; async-first I/O discipline with one notable lapse (CC-05). The discipline scaffolding is present — the discipline itself is missing.

---

## § 2.1 Findings table (severity-ordered)

| ID | Sev | Category | Evidence (path:lines) | Effort | Sibling? |
|---|---|---|---|---|---|
| PY-CR-01 | Critical | Toolchain / Types | mypy `--strict` only checks 5 of 55 packages **and** crashes on duplicate `test_edge_cases` module — `pyproject.toml:259-272`, `tooling-pykit.log.mypy:1-9`, `pykit-dim1:167-180`, `pykit-dim3:72-86`, `pykit-dim4:32` (CQ-10 / TS-01 / LT-04 / CI-06) | M | gokit CR-1 |
| PY-CR-02 | Critical | Architecture | Import-linter contract **broken** (pykit_grpc → pykit_discovery) and only 39/55 packages enumerated — `packages/pykit-grpc/src/pykit_grpc/discovery_channel.py:12-13`, `pyproject.toml:[tool.importlinter]`, `pykit-dim1:196-216` (AR-01) | M | gokit CR-2 |
| PY-CR-03 | Critical | Security / Auth | No OIDC ID-token verifier exists; only a refresh client. — `packages/pykit-auth-oidc/src/pykit_auth_oidc/`, `pykit-dim2:28-32` (SC-01) | L | gokit CR-3 |
| PY-CR-04 | Critical | Security / HTTP | No HTTP authentication middleware in `pykit-server-middleware`. — `packages/pykit-server-middleware/src/pykit_server_middleware/`, `pykit-dim2:34-43` (SC-02) | L | gokit CR-4 |
| PY-CR-05 | Critical | Observability | No `/healthz` or `/readyz` handler is shipped. — `packages/pykit-health/`, `packages/pykit-server-middleware/`, `pykit-dim2:442-446` (OB-01) | M | gokit CR-5 |
| PY-CR-06 | Critical | CI / Release | No release workflow; nothing has ever shipped. 55 pkgs all `0.1.0`; no `release.yml`, no `uv publish`, no PyPI Trusted Publishing. — `.github/workflows/`, `pykit-dim4:27` (CI-01 / REL-01) | L | gokit CR-6 |
| PY-CR-07 | Critical | CI / Security | No security scanning of any kind in CI (no CodeQL, Semgrep, Bandit, pip-audit, safety). — `.github/workflows/ci.yml`, `tooling-pykit.log.audit3`, `pykit-dim4:28` (CI-02) | L | gokit CR-7 |
| PY-CR-08 | Critical | Toolchain | No Dependabot / Renovate config. `.github/dependabot.yml` absent. — `.github/`, `pykit-dim4:42` (TC-01) | XS | gokit CR-8 |
| PY-CR-09 | Critical | Toolchain | `uv.lock` is gitignored — workspace is not byte-reproducible. — `.gitignore:171-173`, `pykit-dim4:43` (TC-02) | XS | gokit CR-9 |
| PY-CR-10 | Critical | Release | No PyPI Trusted Publishing OIDC config; `id-token: write` job missing; no Sigstore signing. — `.github/workflows/`, `pykit-dim4:60` (REL-02) | M | gokit CR-10 |
| PY-CR-11 | Critical | Release / Versioning | All 55 packages frozen at `version = "0.1.0"` with no per-package CHANGELOG, no tag, no provenance. Nothing has been released. — `packages/*/pyproject.toml`, `pykit-dim4:59` (REL-01 amplification) | M | gokit CR-11 |
| PY-HI-01 | High | Code Quality | `Container.resolve` returns unsafe `T` when `type_hint=None`. — `packages/pykit-container/src/pykit_container/container.py:120-160`, `pykit-dim1:24-48` (CQ-01) | S | — |
| PY-HI-02 | High | Code Quality | `# noqa: F821` masking a missing import. — `pykit-dim1:49-58` (CQ-02) | XS | — |
| PY-HI-03 | High | Code Quality | 117 `raise X(...)` without `from e` in lib code (cause-chain loss). — `pykit-dim1:59-70` (CQ-03) | M | gokit ER-* |
| PY-HI-04 | High | Code Quality | 8 `assert` in lib code (stripped under `python -O`). — `pykit-dim1:76-92` (CQ-05) | S | — |
| PY-HI-05 | High | Code Quality | 99 `: Any` / `-> Any` annotations leak in non-test code (46 files). — `pykit-dim1:107-131` (CQ-07) | M | LT-03 |
| PY-HI-06 | High | Architecture | Three module-level mutable registries with inconsistent API. — `pykit-dim1:217-238` (AR-02) | M | — |
| PY-HI-07 | High | Architecture | `Component.start_all` lacks rollback on partial failure. — `packages/pykit-component/src/pykit_component/lifecycle.py`, `pykit-dim1:239-284` (AR-03) | M | gokit AR-* |
| PY-HI-08 | High | Architecture | `Container._resolving` set is process-global, not per-task/thread (cycle detection broken under concurrency). — `pykit-dim1:315-343` (AR-07) | S | — |
| PY-HI-09 | High | Concurrency | `asyncio.create_task(self.stop())` lambda is fire-and-forget — `RuntimeWarning: coroutine was never awaited` race. — `pykit-dim1:344-362` (CC-01) | S | — |
| PY-HI-10 | High | Concurrency | `RateLimiter._cleanup_task` reference dropped on `stop()`. — `pykit-dim1:363-388` (CC-02) | S | — |
| PY-HI-11 | High | Concurrency | `RateLimiter` mixes `threading.Lock` with async cleanup. — `pykit-dim1:389-408` (CC-03) | S | SC-14 |
| PY-HI-12 | High | Concurrency | `asyncio.gather(*tasks)` without `return_exceptions=True` in DAG engine — partial-failure leak. — `pykit-dim1:409-427` (CC-04) | S | PF-03 |
| PY-HI-13 | High | Concurrency | `LocalSource.fetch` does sync file I/O in `async def`. — `pykit-dim1:428-449` (CC-05) | S | — |
| PY-HI-14 | High | Security | `JWTService` has no leeway, no HMAC secret-length check, exposes `decode_unverified`. — `packages/pykit-auth-jwt/src/pykit_auth_jwt/`, `pykit-dim2:45-62` (SC-03) | S | — |
| PY-HI-15 | High | Security | `PasswordHasher.HashAlgorithm.ARGON2` is **not** Argon2 — it is `hashlib.scrypt` with non-constant-time compare. — `packages/pykit-auth-password/src/pykit_auth_password/`, `pykit-dim2:63-88` (SC-04) | S | — |
| PY-HI-16 | High | Security / CI | CI is missing pip-audit, bandit, ruff `S` ruleset, SBOM, signing. — `.github/workflows/ci.yml`, `pykit-dim2:89-107` (SC-05) | M | CI-02 |
| PY-HI-17 | High | Security | pip-audit cannot complete because workspace pkgs aren't on PyPI; no transitive scan happens in CI. — `tooling-pykit.log.audit:1-2`, `pykit-dim2:108-114` (SC-06) | M | — |
| PY-HI-18 | High | Security | `TLSConfig.is_enabled()` excludes `min_version` — silent downgrade to httpx defaults. — `pykit-dim2:115-138` (SC-07) | XS | — |
| PY-HI-19 | High | Security | `BaseServer.add_insecure_port` is the only TCP option — no TLS exposed for gRPC. — `packages/pykit-server/src/pykit_server/base.py`, `pykit-dim2:139-146` (SC-08) | M | — |
| PY-HI-20 | High | Security | OIDC `refresh_token` leaks token-endpoint response body into the exception message. — `packages/pykit-auth-oidc/src/pykit_auth_oidc/refresh.py`, `pykit-dim2:147-167` (SC-09) | XS | ER-02 |
| PY-HI-21 | High | Errors | `_TYPE_BASE_URI` is a module-level mutable global; no per-server isolation. — `packages/pykit-errors/src/pykit_errors/`, `pykit-dim2:288-300` (ER-01) | S | — |
| PY-HI-22 | High | Errors | `AppError.__str__` leaks `cause` text → secrets bleed into logs. — `packages/pykit-errors/`, `pykit-dim2:301-313` (ER-02) | S | OB-08 |
| PY-HI-23 | High | Errors | No `Wrap` classifier — every caller does `if isinstance(e, AppError) else AppError.internal(e)` by hand. — `pykit-dim2:314-343` (ER-03) | M | — |
| PY-HI-24 | High | Observability | `setup_tracing/setup_metrics/setup_otlp_*` mutate OTel globals; second call wins, no shutdown returned. — `packages/pykit-telemetry/`, `pykit-dim2:448-457` (OB-02) | M | — |
| PY-HI-25 | High | Observability | `setup_tracing` configures `TracerProvider` *with no exporter* — spans go nowhere. — `pykit-dim2:458-463` (OB-03) | XS | — |
| PY-HI-26 | High | Observability | No global `TextMapPropagator` is set anywhere — incoming W3C TraceContext may not be honored. — `pykit-dim2:464-476` (OB-04) | XS | — |
| PY-HI-27 | High | Testing / Types | mypy is broken in CI; only 5 of 55 packages strict-checked. — `pykit-dim3:72-86` (TS-01) [overlap PY-CR-01] | — | — |
| PY-HI-28 | High | Testing | `pytest-xdist` advertised in tooling but not installed; runs serial. — `pyproject.toml`, `pykit-dim3:87-92` (TS-02) | XS | — |
| PY-HI-29 | High | Testing | Three packages well below 80% floor; coverage gate is 60%. — `pyproject.toml:236`, `pykit-dim3:93-107` (TS-03) | M | — |
| PY-HI-30 | High | Testing | Zero integration test separation (no `@pytest.mark.integration`, no markers, all in one job). — `pykit-dim3:108-122` (TS-04) | S | — |
| PY-HI-31 | High | Testing | No deterministic clock; 90 wall-clock call sites in production code; `freezegun` absent. — `pykit-dim3:123-141` (TS-05) | M | — |
| PY-HI-32 | High | Testing | No property-based or fuzz testing; `hypothesis`/`atheris` absent. — `pykit-dim3:142-154` (TS-06) | M | CI-08 |
| PY-HI-33 | High | Testing | `pykit-discovery` test broken; 10 failures from `DiscoveryComponent` ctor drift; layer violation. — `tooling-pykit.log.tests2`, `packages/pykit-discovery/tests/test_discovery.py:150,166,177,188,195`, `tests/test_discovery_extended.py:203,210,219,229,234`, `pykit-dim3:155-161` (TS-07) | S | PY-CR-02 |
| PY-HI-34 | High | Performance | No code performance benchmarking infrastructure (no pytest-benchmark, no pyperf). — `pykit-dim3:191-204` (PF-01) | M | — |
| PY-HI-35 | High | Performance | Zero `functools.lru_cache`/`functools.cache` adoption in hot paths. — `pykit-dim3:205-210` (PF-02) | S | — |
| PY-HI-36 | High | Lint | Ruff rule selection misses 11 high-value rule families (`S`, `TRY`, `PT`, `LOG`, `G`, `DTZ`, `PERF`, `C4`, `PIE`, `RET`, `T20`, `N`, `FURB`, `ANN`). — `pyproject.toml`, `pykit-dim3:267-287` (LT-01) | XS | — |
| PY-HI-37 | High | Lint | 271 `Any` annotations leak into public APIs of 50 unchecked packages. — `tooling-pykit.log.audit`, `pykit-dim3:298-326` (LT-03) | M | CQ-07 |
| PY-HI-38 | High | Lint / Types | mypy strict scope covers 5 of 55 packages — duplicate axis of TS-01. — `pykit-dim3:327-329` (LT-04) | — | PY-CR-01 |
| PY-HI-39 | High | CI | Every action is unpinned; 12 mutable `@v4`/`@v5` references. — `.github/workflows/ci.yml:20,21,32,33,43,44,54,55,65,66`, `pykit-dim4:29` (CI-03) | XS | — |
| PY-HI-40 | High | CI | No build matrix — single `ubuntu-latest` × single Python; no macOS/Windows/arm64/N-1 Python. — `.github/workflows/ci.yml`, `pykit-dim4:30` (CI-04) | S | — |
| PY-HI-41 | High | CI | Coverage XML generated but never uploaded (no Codecov). — `.github/workflows/ci.yml:52-59`, `pykit-dim4:31` (CI-05) | XS | — |
| PY-HI-42 | High | CI | mypy `--strict` runs against only 5 of 55 packages. — `.github/workflows/ci.yml:42-48`, `pyproject.toml:259-272`, `pykit-dim4:32` (CI-06) | M | PY-CR-01 |
| PY-HI-43 | High | CI | No `uv lock --check` / `uv sync --locked` / `--frozen` gate anywhere. — `pykit-dim4:33` (CI-07) | XS | TC-02 |
| PY-HI-44 | High | CI | No fuzz job (atheris) for `pykit-media`, `pykit-errors` RFC 7807 deser, `pykit-validation`, `pykit_messaging.kafka`. — `pykit-dim4:34` (CI-08) | M | TS-06 |
| PY-HI-45 | High | Toolchain | No `pre-commit` config (`.pre-commit-config.yaml` absent). — `pykit-dim4:44` (TC-03) | XS | — |
| PY-HI-46 | High | Toolchain | No `.editorconfig`, no `.gitattributes`. — `pykit-dim4:45` (TC-04) | XS | — |
| PY-HI-47 | High | Toolchain | `python-version` policy not pinned across packages (some allow 3.11, some 3.13). — `pykit-dim4:46` (TC-05) | S | — |
| PY-HI-48 | High | Toolchain | hatch metadata incomplete: missing `[project.urls]`, classifiers, license-files. — `packages/*/pyproject.toml`, `pykit-dim4:47` (TC-06) | M | — |
| PY-HI-49 | High | Toolchain | `pyproject.toml` `[project.optional-dependencies]` missing — no `pip install pykit[grpc]` story. — `pykit-dim4:48` (TC-07) | M | — |
| PY-HI-50 | High | Docs | No `SECURITY.md`. — `pykit-dim4:71` (DOC-01) | XS | — |
| PY-HI-51 | High | Docs | README claims a CODE_OF_CONDUCT in `docs/code_of_conduct.md` that does not exist. — `README.md`, `pykit-dim4:72` (DOC-02) | XS | — |
| PY-HI-52 | High | Docs | No `MAINTAINERS.md`, no `GOVERNANCE.md`, no `CODEOWNERS`. — `pykit-dim4:73` (DOC-03) | XS | — |
| PY-HI-53 | High | Docs | No per-package READMEs / `docs/` site / mkdocs / Sphinx. — `pykit-dim4:74` (DOC-04) | M | — |
| PY-HI-54 | High | Release | All packages stuck at `0.1.0`; no SemVer policy; no per-pkg changelog. — `pykit-dim4:61` (REL-03) | M | PY-CR-11 |
| PY-HI-55 | High | Release | No git tag protection / no signed tags / no release notes generation (`release-drafter`/`release-please`). — `pykit-dim4:62` (REL-04) | S | — |
| PY-HI-56 | High | Release | No SBOM publication (CycloneDX/SPDX); no Sigstore attestations. — `pykit-dim4:63` (REL-05) | M | — |
| PY-HI-57 | High | Release | No deprecation policy / no `__deprecated__` decorator / no `DeprecationWarning` discipline. — `pykit-dim4:64` (REL-06) | S | — |
| PY-HI-58 | High | Hygiene | No ISSUE_TEMPLATE/, no PULL_REQUEST_TEMPLATE.md. — `.github/`, `pykit-dim4:88` (HY-01) | XS | — |
| PY-HI-59 | High | Hygiene | No CHANGELOG.md (root or per-package); no Keep-A-Changelog format. — `pykit-dim4:89` (HY-02) | S | — |
| PY-HI-60 | High | Hygiene | No CONTRIBUTING.md (only README "Contributing" section, no DCO/CLA, no signoff policy). — `pykit-dim4:90` (HY-03) | S | — |
| PY-ME-01 | Medium | Code Quality | Add `S` (bandit), `ANN`, `PT`, `N`, `C4`, `PIE`, `RET` to Ruff. — `pykit-dim1:71-75` (CQ-04) | XS | LT-01 |
| PY-ME-02 | Medium | Code Quality | `print()` in `pykit-logging` import-error fallback. — `pykit-dim1:93-106` (CQ-06) | XS | OB-05 |
| PY-ME-03 | Medium | Code Quality | `# type: ignore[type-arg]` & `[call-arg]` in encryption factory. — `pykit-dim1:132-156` (CQ-08) | S | — |
| PY-ME-04 | Medium | Code Quality | Untyped function signatures in `pykit-database` core. — `pykit-dim1:157-166` (CQ-09) | S | — |
| PY-ME-05 | Medium | Code Quality | `match` is used in only 3 places — pattern adoption inconsistent. — `pykit-dim1:181-184` (CQ-11) | S | — |
| PY-ME-06 | Medium | Code Quality | `pydantic` vs `dataclass` discipline is inconsistent. — `pykit-dim1:185-195` (CQ-12) | M | — |
| PY-ME-07 | Medium | Architecture | `pykit` facade is stale (lazy facade out of date with packages). — `pykit-dim1:285-289` (AR-04) | S | — |
| PY-ME-08 | Medium | Architecture | 55 packages: some splits are not justified. — `pykit-dim1:290-301` (AR-05) | M | — |
| PY-ME-09 | Medium | Architecture | `pykit-discovery` eagerly imports `httpx` at `__init__`. — `pykit-dim1:302-314` (AR-06) | XS | — |
| PY-ME-10 | Medium | Concurrency | Tasks created without retained reference (lost-task risk catalog). — `pykit-dim1:450-465` (CC-06) | S | — |
| PY-ME-11 | Medium | Concurrency | `asyncio.shield(future) + wait_for` with cancel race. — `pykit-dim1:466-484` (CC-07) | S | — |
| PY-ME-12 | Medium | Concurrency | `_REGISTRY` mutation without lock; `register_provider` racy. — `pykit-dim1:485-490` (CC-08) | XS | CC-03 |
| PY-ME-13 | Medium | Concurrency | `WorkerPool` not actually pool-limited at submit time. — `pykit-dim1:491-507` (CC-09) | S | — |
| PY-ME-14 | Medium | Security | `_parse_token_response` swallows its own raised `RefreshError` via broad `except Exception`. — `pykit-dim2:168-181` (SC-10) | XS | — |
| PY-ME-15 | Medium | Security | `pykit-encryption` derives keys via plain SHA-256, no salt, no KDF, no AAD, no key versioning. — `pykit-dim2:182-196` (SC-11) | M | — |
| PY-ME-16 | Medium | Security | `pykit-process.run_shell` exists at all; trivial command-injection vector. — `pykit-dim2:197-203` (SC-12) | XS | — |
| PY-ME-17 | Medium | Security | `APIKeyMiddleware` swallows all exceptions into a generic 401 — no logging of *why*. — `pykit-dim2:204-216` (SC-13) | XS | — |
| PY-ME-18 | Medium | Security | `RateLimitMiddleware._lock = threading.Lock()` mixed with asyncio. — `pykit-dim2:217-222` (SC-14) | XS | CC-03 |
| PY-ME-19 | Medium | Security | `PrometheusMiddleware` uses raw `path` as a label → unbounded cardinality. — `pykit-dim2:223-228` (SC-15) | XS | OB-06 |
| PY-ME-20 | Medium | Errors | Auth response shape diverges from `ProblemDetail`. — `pykit-dim2:344-358` (ER-04) | S | — |
| PY-ME-21 | Medium | Errors | `RefreshError` is its own one-off `Exception` subclass — not in `AppError` taxonomy. — `pykit-dim2:359-375` (ER-05) | S | ER-03 |
| PY-ME-22 | Medium | Errors | Module-level taxonomy maps are exhaustive but not guarded. — `pykit-dim2:376-387` (ER-06) | S | — |
| PY-ME-23 | Medium | Observability | `print()` in `setup_logging` warm-fail path. — `pykit-dim2:477-484` (OB-05) | XS | CQ-06 |
| PY-ME-24 | Medium | Observability | `OperationMetrics` labels include unbounded `method` / `status` strings without normalization. — `pykit-dim2:485-498` (OB-06) | XS | SC-15 |
| PY-ME-25 | Medium | Observability | No span around OIDC `refresh_token` HTTP call. — `pykit-dim2:499-504` (OB-07) | XS | — |
| PY-ME-26 | Medium | Observability | `ErrorHandlingInterceptor` does not call `record_exception` on the active span. — `pykit-dim2:505-516` (OB-08) | XS | — |
| PY-ME-27 | Medium | Testing | Mocking-heavy where fakes exist; no `caplog` log-content assertions. — `pykit-dim3:162-167` (TS-08) | M | — |
| PY-ME-28 | Medium | Testing | 8 packages have no coverage measurement at all. — `pykit-dim3:168-173` (TS-09) | S | TS-03 |
| PY-ME-29 | Medium | Performance | `asyncio.gather` used where `TaskGroup` is now correct. — `pykit-dim3:211-224` (PF-03) | S | CC-04 |
| PY-ME-30 | Medium | Performance | String concatenation in tight parser loop. — `pykit-dim3:225-237` (PF-04) | XS | — |
| PY-ME-31 | Medium | Performance | No profiling integration hooks (pyinstrument). — `pykit-dim3:238-242` (PF-05) | S | — |
| PY-ME-32 | Medium | Lint | `TC001/TC002/TC003` blanket-ignored — defeats `TCH`. — `pyproject.toml`, `pykit-dim3:288-297` (LT-02) | XS | — |
| PY-ME-33 | Medium | Lint | No `import-linter` *independence* contract; only layered. — `pykit-dim3:330-346` (LT-05) | S | — |
| PY-ME-34 | Medium | Lint | No bandit, no pip-audit failure gate, no SBOM. — `pykit-dim3:347-351` (LT-06) | S | SC-05 |
| PY-ME-35 | Medium | CI | Per-job permissions never downgraded below default `contents: read`. — `.github/workflows/ci.yml:14-99`, `pykit-dim4:35` (CI-09) | XS | — |
| PY-ME-36 | Medium | CI | No caching (`enable-cache: true` on `setup-uv`). — `.github/workflows/ci.yml:18-70`, `pykit-dim4:36` (CI-10) | XS | — |
| PY-ME-37 | Medium | CI | No concurrency group; redundant runs on rapid pushes. — `pykit-dim4:37` (CI-11) | XS | — |
| PY-ME-38 | Medium | CI | No required-status-checks documentation; branch protection unverified. — `pykit-dim4:38` (CI-12) | S | — |
| PY-ME-39 | Medium | CI | No nightly job (`schedule: cron`) for slow integration / pip-audit. — `pykit-dim4:39` (CI-13) | S | — |
| PY-ME-40 | Medium | Toolchain | No `tool.uv.workspace` exclude rules; example packages will ship. — `pykit-dim4:49` (TC-08) | S | — |
| PY-ME-41 | Medium | Toolchain | No `[tool.hatch.version]` source — versions hand-edited. — `pykit-dim4:50` (TC-09) | S | — |
| PY-ME-42 | Medium | Toolchain | No `py.typed` marker file in some packages. — `pykit-dim4:51` (TC-10) | XS | — |
| PY-ME-43 | Medium | Toolchain | `tool.coverage.run.source` not declared per package. — `pykit-dim4:52` (TC-11) | S | — |
| PY-ME-44 | Medium | Docs | No ARCHITECTURE.md / no C4 diagrams. — `pykit-dim4:75` (DOC-05) | M | — |
| PY-ME-45 | Medium | Docs | No `docs/release-process.md`. — `pykit-dim4:76` (DOC-06) | S | REL-* |
| PY-ME-46 | Medium | Docs | No examples/ runnable samples. — `pykit-dim4:77` (DOC-07) | M | — |
| PY-ME-47 | Medium | Docs | API reference auto-gen absent. — `pykit-dim4:78` (DOC-08) | M | DOC-04 |
| PY-ME-48 | Medium | Release | No `tool.hatch.build.targets.wheel.packages` validated for monorepo. — `pykit-dim4:65` (REL-07) | S | — |
| PY-ME-49 | Medium | Hygiene | `.gitignore` over-broad in spots; some build artefacts missing. — `pykit-dim4:91` (HY-04) | XS | — |
| PY-ME-50 | Medium | Hygiene | No `FUNDING.yml`. — `pykit-dim4:92` (HY-05) | XS | — |
| PY-ME-51 | Medium | Hygiene | No `bug_report.yml`/`feature_request.yml` issue forms. — `pykit-dim4:93` (HY-06) | XS | HY-01 |
| PY-ME-52 | Medium | Hygiene | No labeler config (`.github/labeler.yml`). — `pykit-dim4:94` (HY-07) | XS | — |
| PY-ME-53 | Medium | Hygiene | No stale-bot / lock-bot policy. — `pykit-dim4:95` (HY-08) | XS | — |
| PY-LO-01 | Low | Security | `_RateLimitMiddleware` reaches into private state of the limiter. — `pykit-dim2:229-235` (SC-16) | XS | — |
| PY-LO-02 | Low | Security | No CORS, no CSRF helpers in the kit. — `pykit-dim2:236-241` (SC-17) | M | — |
| PY-LO-03 | Low | Errors | `Wrap`/cause chain not preserved when `interceptors.ErrorHandlingInterceptor` aborts. — `pykit-dim2:388-392` (ER-07) | XS | ER-03 |
| PY-LO-04 | Low | Errors | `LoggingInterceptor` formats `error=str(exc)` — ER-02 amplification on the gRPC side. — `pykit-dim2:393-396` (ER-08) | XS | ER-02 |
| PY-LO-05 | Low | Observability | `ServiceHealth` lacks `checked_at` / `latency_ms` per component. — `pykit-dim2:517-521` (OB-09) | XS | OB-01 |
| PY-LO-06 | Low | Observability | `correlation_id_var` is set but TracingMiddleware does not link it to span attributes. — `pykit-dim2:522-526` (OB-10) | XS | — |
| PY-LO-07 | Low | Observability | No metric on the rate-limit middleware (denials, key cardinality). — `pykit-dim2:527-540` (OB-11) | XS | — |
| PY-LO-08 | Low | Testing | `--import-mode=importlib` good, but no `conftest.py` at root. — `pykit-dim3:174-190` (TS-10) | XS | — |
| PY-LO-09 | Low | Performance | No object pool / no `__slots__` audit on hot dataclasses. — `pykit-dim3:243-247` (PF-06) | S | — |
| PY-LO-10 | Low | Performance | `pykit-bench` and `bench/` naming collision with code-perf bench. — `pykit-dim3:248-266` (PF-07) | XS | — |
| PY-LO-11 | Low | Lint | Ruff `per-file-ignores` only relaxes `E402` for tests. — `pykit-dim3:352-361` (LT-07) | XS | — |
| PY-LO-12 | Low | Lint | `print(...)` in library code (also in tooling log). — `pykit-dim3:362-374` (LT-08) | XS | CQ-06 |
| PY-LO-13 | Low | CI | No `actions: write`/`packages: write` minimization audit. — `pykit-dim4:40` (CI-14) | XS | CI-09 |
| PY-LO-14 | Low | CI | No CI status badge / trophy in README. — `pykit-dim4:41` (CI-15) | XS | — |
| PY-LO-15 | Low | Toolchain | No `[tool.uv.sources]` private-index documentation. — `pykit-dim4:53` (TC-12) | XS | — |
| PY-LO-16 | Low | Docs | No "Install" section quickstart in README beyond `uv add`. — `pykit-dim4:79` (DOC-09) | XS | — |
| PY-LO-17 | Low | Docs | No glossary / no "concepts" page. — `pykit-dim4:80` (DOC-10) | S | — |
| PY-LO-18 | Low | Hygiene | No `.gitleaks.toml` config. — `pykit-dim4:96` (HY-09) | XS | — |
| PY-LO-19 | Low | Hygiene | No `commitlint`/conventional-commits enforcement. — `pykit-dim4:97` (HY-10) | XS | — |
| PY-NI-01 | Nit | Security | `pyjwt 2.12.1`, `cryptography 46.0.6`, `bcrypt 5.0.0`, `httpx 0.28.1` — versions look current at audit-time (modulo CVEs called out in § 1 #5). — `pykit-dim2:242-260` (SC-18) | — | — |

**Severity totals: 11 Critical · 60 High · 53 Medium · 19 Low · 1 Nit · 144 total.**

---

## § 2.2 Per-Critical and Per-High inline detail

Med/Low/Nit findings retain their full narrative in the source `pykit-dim*.md` files (line refs in the table). Critical and High items get an inline block here so this document is self-contained for triage.

### PY-CR-01 — mypy `--strict` covers 5 of 55 packages and crashes on duplicate test module
**What.** `pyproject.toml:259-272` declares `[tool.mypy] packages = ["pykit_errors", "pykit_config", "pykit_logging", "pykit_provider", "pykit_pipeline"]`. Running `uv run mypy` from the workspace root therefore type-checks **9% of the codebase**. The remaining 50 packages — including `pykit_database`, `pykit_grpc`, `pykit_auth`, `pykit_messaging`, `pykit_server`, `pykit_server_middleware`, `pykit_telemetry` — have no static type gate at all. Adding `--strict` to the same 5 packages produces (`tooling-pykit.log.mypy:1-9`):
```
packages/pykit-discovery/tests/test_edge_cases.py: error: Source file found twice under different module names: "test_edge_cases" and "tests.test_edge_cases"  [misc]
Found 1 error in 1 file (errors prevented further checking)
```
The duplicate stems from no `explicit_package_bases = true` + no `namespace_packages = true` + tests not excluded.
**Fix.** (i) `[tool.mypy] packages = [...]` → enumerate **all 55**; (ii) add `explicit_package_bases = true`, `namespace_packages = true`, `exclude = ["tests/", "examples/"]`; (iii) split test type-check into `[tool.mypy-tests]` overlay; (iv) gate in CI on every PR; (v) Phase the strictness ladder (`disallow_any_generics` → `disallow_untyped_defs` → `--strict`) per-package as type-debt is paid.
**Effort.** M (1-2 days for config + initial pass; weeks of ongoing `Any` cleanup tracked separately as PY-HI-05/PY-HI-37).

### PY-CR-02 — Import-linter contract is *broken* and covers only 39 of 55 packages
**What.** `pyproject.toml [tool.importlinter]` declares a layered contract with `pykit_grpc` strictly above `pykit_discovery`. Yet:
```python
# packages/pykit-grpc/src/pykit_grpc/discovery_channel.py:12-13
from pykit_discovery.types import ServiceInstance
from pykit_discovery.protocols import DiscoveryProvider
```
This is a **direct** layer violation at HEAD; CI is not running `lint-imports` so the violation is silent. Worse, only 39 of the 55 packages are even *named* in any contract — 16 packages are governed by no architectural rule at all. `pykit-dim1:196-216` enumerates the missing ones.
**Fix.** (i) Move the discovery channel adapter into a new `pykit_discovery_grpc` extension package, OR invert the dependency by defining `pykit_grpc.channel.Provider` Protocol that `pykit_discovery` implements; (ii) extend the layered contract to enumerate all 55 packages; (iii) add an `independence` contract for `pykit_errors`, `pykit_config`, `pykit_logging` (foundation tier) — they must depend on *nothing* in the workspace; (iv) add a CI step `uv run lint-imports` that fails on any contract violation; (v) add a `forbidden` contract barring `tests/` from cross-package imports.
**Effort.** M (1 day to fix the contract + extract `discovery_channel.py`; CI integration trivial).

### PY-CR-03 — No OIDC ID-token verifier exists; only a refresh client
**What.** `pykit-auth-oidc/` contains only a `refresh_token` client. There is **no ID-token verifier** anywhere in the workspace — no JWKS fetch, no `kid → key` rotation, no `iss`/`aud`/`nonce`/`exp`/`nbf` checks, no leeway, no alg-binding. Any downstream service performing OIDC code-flow login must roll its own verifier and will almost certainly get one or more of: `alg=none` accepted, HMAC alg-confusion against the IdP RSA key, missing nonce, missing audience binding, missing issuer pinning, no clock skew tolerance. gokit ships exactly this verifier in `auth/oidc/verifier.go` (still flagged as MEDIUM there because *the file existed*); pykit doesn't ship the file at all.
**Fix.** New module `pykit_auth_oidc.verifier`:
```python
class Verifier:
    def __init__(
        self,
        issuer: str,
        audience: str,
        jwks_cache: JWKSCache,
        *,
        leeway_seconds: int = 60,
        require_nonce: bool = False,
        allowed_algs: frozenset[str] = frozenset({"RS256", "ES256"}),
    ) -> None: ...
    async def verify(self, token: str, *, nonce: str | None = None) -> Claims: ...
```
Use `cryptography.hazmat.primitives.asymmetric.{rsa,ec,padding}` for verification; reject `none` and HMAC families up-front; bind alg to the JWK's `alg` field per RFC 8725 §3.1; require nonce when `require_nonce=True`; enforce `iat`/`nbf`/`exp` with leeway. Pair with the `JWKSCache` redesign in § 4.
**Effort.** L (3-5 days incl. tests against a live IdP fixture).

### PY-CR-04 — No HTTP authentication middleware in `pykit-server-middleware`
**What.** `pykit-server-middleware/` ships `tracing`, `prometheus`, `ratelimit`, `tenant` middlewares, all hand-rolled raw-ASGI. There is **no `AuthMiddleware`**. There is **no `Mode` enum** (`Disabled`/`Optional`/`Required`). There is **no integration with FastAPI/Starlette** at all. Anyone wanting "authenticate this request" must reach into `pykit-auth-jwt` or `pykit-api-key` directly from their handler, which means: (1) every handler re-implements bearer/cookie/header parsing; (2) RFC 6750 `WWW-Authenticate` challenges are ad-hoc; (3) public endpoints (`/healthz`, `/metrics`) cannot be excluded uniformly; (4) no centralized place to attach `request.state.principal`.
**Fix.** New `pykit_server_middleware.auth.AuthMiddleware` (sketch in § 4) parameterized by:
- `verifier: AuthVerifier` Protocol (sole abstraction, accepts JWT or API-key impls);
- `mode: Mode = Mode.Required` (`Disabled` → no-op, `Optional` → set principal if present, `Required` → 401 on missing/invalid);
- `excluded: tuple[str, ...] = ()` (path prefixes; never substring match);
- `bearer_only: bool = True` (no query-string token fallback — avoid gokit SC-10 entirely).
Returns RFC 6750 `WWW-Authenticate: Bearer error="invalid_token", error_description="…"` on 401.
**Effort.** L (3-4 days including JWT + API-key + OIDC verifier integrations).

### PY-CR-05 — No `/healthz` or `/readyz` handler is shipped
**What.** No package ships an HTTP `/healthz` or `/readyz` endpoint. `pykit-health/` defines `HealthStatus` enum and `ServiceHealth` dataclass but no ASGI handler, no Starlette route, no gRPC health service implementation. K8s liveness/readiness probes have nothing to call. Compare gokit which ships `health.Handler` — pykit doesn't.
**Fix.** New `pykit_health.HealthRegistry` ASGI app (sketch in § 4) supporting `/healthz` (liveness) and `/readyz` (readiness with per-component checks), JSON shape `{status, components: [{name, status, latency_ms, checked_at, error?}]}`. Plus a `pykit_grpc.health` adapter exposing the standard `grpc.health.v1.Health` service.
**Effort.** M (2-3 days including K8s integration tests).

### PY-CR-06 — No release workflow; nothing has ever shipped
**What.** `.github/workflows/` contains only `ci.yml`. There is no `release.yml`, no `pypi-publish.yml`, no `hatch publish`, no `uv publish`. With 55 packages all at `version = "0.1.0"`, **nothing has ever shipped to PyPI**. There is no PyPI Trusted Publishing OIDC config, no `id-token: write` job, no Sigstore signing, no SBOM upload, no GitHub Release creation, no provenance attestation. Compare gokit which at least has signed git tags.
**Fix.** Add `release.yml` (drop-in in § 5) triggered on `v*` tags, using PyPI Trusted Publishing (no PYPI_API_TOKEN secret), `actions/attest-build-provenance` for SLSA, `sigstore/cosign-installer` for signing, `anchore/sbom-action` for CycloneDX SBOM upload.
**Effort.** L (release pipeline + PyPI Trusted Publishing config + per-package version bumping is multi-day work; pair with PY-CR-10 and PY-CR-11).

### PY-CR-07 — No security scanning of any kind in CI
**What.** `.github/workflows/ci.yml` has zero security jobs. No CodeQL, Semgrep, Bandit, pip-audit, safety, or Snyk. The 5 live CVEs in the resolved environment (`tooling-pykit.log.audit3`) — `cryptography 46.0.6`, `pip 26.0.1`, `pygments 2.19.2`, `pytest 9.0.2`, `python-multipart 0.0.24` — would have been blocked by any of these gates. The audit was run **manually** (`tooling-pykit.log.audit:1-2`) and even that failed because workspace packages aren't on PyPI (see PY-HI-17), so pip-audit cannot resolve transitively without a custom `--requirement` export.
**Fix.** Add `security.yml` (drop-in in § 5) with three jobs: (1) **CodeQL** for Python; (2) **pip-audit** with `uv export --no-emit-workspace --format requirements-txt | pip-audit -r /dev/stdin --strict --vulnerability-service osv`; (3) **bandit** with `-c pyproject.toml -lll -iii -r packages/`. All required-status-checks. Plus weekly cron for upstream drift.
**Effort.** L (1 day for first pass; ongoing tuning).

### PY-CR-08 — No Dependabot / Renovate config
**What.** `.github/dependabot.yml` does not exist. `renovate.json` does not exist. There is no automation for transitive dependency bumps, GitHub Action SHA bumps, Docker base image bumps, or python-version bumps. The 5 CVEs in PY-CR-07 illustrate the cost.
**Fix.** Add `.github/dependabot.yml` (drop-in in § 5) with `package-ecosystem: pip` (per package directory), `package-ecosystem: github-actions` (root), `package-ecosystem: docker` if any Dockerfiles exist. Weekly schedule, grouped updates by major/minor, auto-merge minor on green CI.
**Effort.** XS (one file; the bigger task is configuring auto-merge policy).

### PY-CR-09 — `uv.lock` is gitignored — workspace is not byte-reproducible
**What.** `.gitignore:171-173`:
```
uv.lock
.python-version
*.lock
```
Without a committed `uv.lock`, every `uv sync` resolves fresh against PyPI ranges. Two contributors at the same SHA can produce different installed environments. CI cannot pin exactly. Reproducible builds, supply-chain attestations, and deterministic CVE scanning are all impossible.
**Fix.** (i) Remove `uv.lock` and `*.lock` from `.gitignore`; (ii) commit current `uv.lock`; (iii) add CI step `uv lock --check` (or `uv sync --locked` / `--frozen`) — see PY-HI-43; (iv) document the lockfile policy in `docs/release-process.md`.
**Effort.** XS.

### PY-CR-10 — No PyPI Trusted Publishing OIDC config
**What.** Even when a release workflow is added (PY-CR-06), the path of least resistance is `PYPI_API_TOKEN` as a long-lived secret. PyPI now offers **Trusted Publishing** via OIDC — short-lived tokens, scoped to a single GitHub workflow file + environment, no secret rotation needed. Pykit has neither configured.
**Fix.** Configure pypi.org pending publisher per package (or use `pypi-publishing-policy` for monorepo trust); release workflow uses `permissions: id-token: write` and `pypa/gh-action-pypi-publish@release/v1` with no `password` argument. Pair with `environment: pypi` for protected approvals.
**Effort.** M (depends on per-pkg pypi.org configuration; CI side is ~10 lines).

### PY-CR-11 — All 55 packages frozen at `0.1.0`
**What.** Every `packages/*/pyproject.toml` declares `version = "0.1.0"`. No git tag exists. No `CHANGELOG.md` per package. No SemVer policy is documented. There is no `__version__` source of truth — version is hand-edited TOML. There is no story for "release `pykit-errors 0.2.0` without releasing all 55".
**Fix.** (i) Adopt `[tool.hatch.version] source = "vcs"` per package (or one shared `_version.py`); (ii) document SemVer policy in `docs/release-process.md`; (iii) add `release-please` (or `release-drafter`) per package via `release-please-config.json` for changelog automation; (iv) tag scheme `pykit-errors/v0.2.0` for monorepo per-package release; (v) add `__deprecated__` decorator + DeprecationWarning discipline (PY-HI-57).
**Effort.** L (multi-week — requires deciding monorepo release strategy first).

### PY-HI-01 — `Container.resolve` returns unsafe `T` when `type_hint=None`
**What.** `pykit-container/src/pykit_container/container.py:120-160` (per dim1:24-48) — when called without an explicit `type_hint`, `resolve` returns `Any` cast to `T`, defeating both runtime and static typing. Callers downstream get `mypy` clean code that can return literally any object.
**Fix.** Make `type_hint` mandatory; provide overload pair `resolve(t: type[T]) -> T` and `resolve_optional(t: type[T]) -> T | None`. Mark old API `@deprecated`. See pykit-dim1:24-48 for full sketch.

### PY-HI-02 — `# noqa: F821` masking a missing import
**What.** A `noqa: F821` directive hides a real undefined-name error (pykit-dim1:49-58). Will explode at runtime on the affected branch.
**Fix.** Add the missing import; remove the noqa; add a regression test for the branch.

### PY-HI-03 — 117 `raise X(...)` without `from e` in lib code
**What.** Cause-chain loss in 117 sites breaks debuggability and traceback ergonomics (pykit-dim1:59-70). Identical defect class to gokit's "wrap loss" finding.
**Fix.** Ruff `TRY200`/`B904` rules to enforce `from e` (or `from None` when intentional); fix all sites mechanically; add to required-status-checks.

### PY-HI-04 — 8 `assert` in lib code
**What.** `assert` statements are no-ops under `python -O`; using them for validation in library code is a security bug (pykit-dim1:76-92).
**Fix.** Replace with explicit `raise` of `pykit_errors.AppError.invalid_argument(...)`; enable Ruff `S101` (no assert in non-test code).

### PY-HI-05 — 99 `Any` in non-test code (46 files)
**What.** Public APIs leak `Any` annotations in 99 sites across 46 files (pykit-dim1:107-131). Defeats the type contract for downstream users.
**Fix.** Per-file remediation; introduce `Protocol`s where structural typing is needed; add `disallow_any_explicit = true` to mypy strict packages first, then expand. Tracked alongside PY-HI-37 (271 in unchecked packages).

### PY-HI-06 — Three module-level mutable registries with inconsistent API
**What.** Three packages (per pykit-dim1:217-238) expose module-level dict-like registries with subtly different signatures (`register`, `add`, `set`). API drift; thread-unsafe.
**Fix.** Adopt the typed `Registry[K, V]` redesign (sketch RP-1 in § 4). Single class, asyncio.Lock for mutation, `register/get/list/clear` API; replace all three sites.

### PY-HI-07 — `Component.start_all` lacks rollback on partial failure
**What.** `pykit-component/src/pykit_component/lifecycle.py` `start_all` starts components sequentially; if component N fails, components 0..N-1 are left started, no `stop()` called (pykit-dim1:239-284). Resource leak, especially for connection pools.
**Fix.** TaskGroup-based redesign (sketch RP-2 in § 4) using `asyncio.TaskGroup` + `BaseExceptionGroup` (PEP 654). On any failure, `stop()` the started subset in reverse order. Same pattern for `stop_all` to surface aggregate errors.

### PY-HI-08 — `Container._resolving` set is process-global
**What.** `Container` uses a single `set[type]` to detect resolution cycles (pykit-dim1:315-343). Under concurrent task resolution, two tasks resolving disjoint graphs collide on the same set; one falsely sees a "cycle".
**Fix.** ContextVar-based per-task resolve stack (sketch RP-5 in § 4). `_resolving: ContextVar[set[type]]` reset per resolve entry.

### PY-HI-09 — `asyncio.create_task(self.stop())` lambda is fire-and-forget
**What.** Lambda creates a coroutine and discards the Task reference; no exception propagation, no awaiting on shutdown (pykit-dim1:344-362). Race with interpreter shutdown produces `coroutine was never awaited` warnings.
**Fix.** Refactor to `await self.stop()` in async context, or capture the task and `await asyncio.shield(task)` in `__del__`-equivalent finalizer. Better: drive lifecycle through TaskGroup (RP-2).

### PY-HI-10 — `RateLimiter._cleanup_task` reference dropped on `stop()`
**What.** `pykit-dim1:363-388` — cleanup task ref nulled before await; `__del__` then warns about pending task.
**Fix.** Hold reference until `await task` completes; cancel-then-await pattern with `asyncio.shield` to absorb cancellation race.

### PY-HI-11 — `RateLimiter` mixes `threading.Lock` with async cleanup
**What.** `threading.Lock` blocks the event loop; should be `asyncio.Lock` (pykit-dim1:389-408). Sibling: SC-14 same defect in `RateLimitMiddleware`.
**Fix.** Switch to `asyncio.Lock`; drop sync entry points (or split sync/async classes).

### PY-HI-12 — `asyncio.gather(*tasks)` without `return_exceptions=True`
**What.** DAG engine in `pykit-pipeline` (per pykit-dim1:409-427) cancels surviving tasks on first failure but never awaits them, leaking partial state. Sibling: PF-03.
**Fix.** Migrate to `asyncio.TaskGroup`; use `BaseExceptionGroup` to aggregate. Where strict gather semantics are required, use `return_exceptions=True` + explicit raise of the first non-CancelledError.

### PY-HI-13 — `LocalSource.fetch` does sync file I/O in `async def`
**What.** `pykit-dim1:428-449` — `open(...).read()` blocks the event loop. Will starve concurrent tasks under load.
**Fix.** Use `aiofiles` or wrap in `asyncio.to_thread(...)`. Add Ruff `ASYNC230`/`ASYNC101` rules to catch new occurrences.

### PY-HI-14 — `JWTService` no leeway, no HMAC secret-length check, exposes `decode_unverified`
**What.** `pykit-dim2:45-62` — `JWTConfig.secret: str` accepts any length (4-byte HS256 = brute-forceable in seconds; RFC 8725 §3.2 mandates ≥32 bytes). No clock skew leeway. Public `decode_unverified()` method tempts misuse.
**Fix.** Validate `len(secret.encode()) >= 32` in `__post_init__`; expose `leeway_seconds: int = 60`; rename `decode_unverified` → `_decode_unverified` (private) and document only for diagnostic use; add Ruff/mypy ban via `flake8-bandit`-style check.

### PY-HI-15 — `PasswordHasher.HashAlgorithm.ARGON2` is *not* Argon2
**What.** `pykit-dim2:63-88` — enum value `ARGON2` is implemented as `hashlib.scrypt`, with non-constant-time `==` compare on hash output. Both the *name lie* and the *timing leak* are bugs.
**Fix.** (i) Add real `argon2-cffi` backend keyed to enum `ARGON2`; (ii) keep `SCRYPT` as its own enum value; (iii) replace `==` with `hmac.compare_digest`; (iv) add property test that `verify(hash(p)) is True` for random `p`.

### PY-HI-16 — CI missing pip-audit, bandit, ruff `S` ruleset, SBOM, signing
**What.** `pykit-dim2:89-107` — same fact pattern as PY-CR-07; called out separately in dim2 from the security angle.
**Fix.** Covered by PY-CR-07 + § 5 `security.yml`. Add Ruff `S` family in `pyproject.toml` (§ 6). Add SBOM job to `release.yml`.

### PY-HI-17 — pip-audit cannot complete because workspace pkgs aren't on PyPI
**What.** `tooling-pykit.log.audit:1-2` — `pip-audit` aborts with `pykit-agent: Dependency not found on PyPI`. Cannot resolve the workspace transitively because workspace members are unpublished.
**Fix.** Use `uv export --no-emit-workspace --format requirements-txt > /tmp/req.txt` then `pip-audit -r /tmp/req.txt --strict`. Wire into `security.yml`. Once REL-01 ships, fall back to direct workspace audit.

### PY-HI-18 — `TLSConfig.is_enabled()` excludes `min_version`
**What.** `pykit-dim2:115-138` — `is_enabled()` checks `cert_file` + `key_file` but not `min_version`. Caller with only `min_version='TLSv1.3'` set silently falls through to httpx defaults.
**Fix.** Include all TLS-relevant fields in the enable check, or return a structured `TLSMode` enum.

### PY-HI-19 — `BaseServer.add_insecure_port` is the only TCP option
**What.** `packages/pykit-server/src/pykit_server/base.py` (pykit-dim2:139-146) — gRPC server only binds via `add_insecure_port`. No TLS/mTLS path. Production gRPC services cannot use pykit as-is.
**Fix.** Add `add_secure_port(creds: grpc.ServerCredentials)` wrapper; load from `TLSConfig`; document in README.

### PY-HI-20 — OIDC `refresh_token` leaks token-endpoint response body into exception
**What.** `pykit-dim2:147-167` — on non-200, the raised exception message includes `response.text`, which often contains client_secret echo or refresh_token reflection. Sibling: ER-02 same class.
**Fix.** Raise `RefreshError(status_code=..., reason="…")` with no body; log body at DEBUG level only with redaction of `client_secret`/`refresh_token`/`code` fields.

### PY-HI-21 — `_TYPE_BASE_URI` is a module-level mutable global
**What.** `pykit-dim2:288-300` — module-global mutable URI prefix in `pykit-errors`; cannot run two services in one process with different URIs (relevant for tests, in-proc gateway).
**Fix.** Move to instance attribute on `ProblemDetailFactory`; deprecate module-level setter.

### PY-HI-22 — `AppError.__str__` leaks `cause` text
**What.** `pykit-dim2:301-313` — `str(err)` includes `self.cause` which is the original exception. `logger.error("op failed", err=exc)` then prints DB connection strings, refresh tokens, etc.
**Fix.** `__str__` returns only `code` + `message`; `__repr__` may include cause; structured loggers should consume `.code/.message/.fields` not `str()`.

### PY-HI-23 — No `Wrap` classifier
**What.** `pykit-dim2:314-343` — every caller hand-writes `if isinstance(e, AppError): raise; raise AppError.internal(e)`. Verbose, easy to forget, cannot evolve mapping rules centrally.
**Fix.** Add `pykit_errors.wrap(e: BaseException, *, code: ErrorCode | None = None) -> AppError` that classifies common stdlib exceptions (TimeoutError → DEADLINE_EXCEEDED, ConnectionError → UNAVAILABLE, etc.) and preserves cause chain. Sketch in pykit-dim2:328-343.

### PY-HI-24 — `setup_tracing/setup_metrics/setup_otlp_*` mutate OTel globals
**What.** `pykit-dim2:448-457` — provider setters with no idempotency, no `shutdown` returned. Second call wins; spans from before are lost; tests cannot tear down cleanly.
**Fix.** New `Telemetry.init(config) -> Telemetry` returning a context manager / explicit `await tel.shutdown()`. Idempotent; subsequent `init` calls warn and return existing instance. Sketch RP in pykit-dim2:746-837.

### PY-HI-25 — `setup_tracing` configures TracerProvider with no exporter
**What.** `pykit-dim2:458-463` — Spans are created and dropped on the floor.
**Fix.** Default to OTLP HTTP exporter when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, else `ConsoleSpanExporter`; never silent no-op.

### PY-HI-26 — No global `TextMapPropagator` set
**What.** `pykit-dim2:464-476` — incoming W3C TraceContext / B3 / Baggage headers may not be propagated; distributed traces break across the pykit boundary.
**Fix.** Call `propagate.set_global_textmap(CompositePropagator([TraceContextTextMapPropagator(), W3CBaggagePropagator()]))` in `Telemetry.init`.

### PY-HI-27 — mypy broken in CI; only 5 of 55 packages strict-checked (TS-01)
**What.** Same fact pattern as PY-CR-01; called out from the testing angle in pykit-dim3:72-86.
**Fix.** See PY-CR-01.

### PY-HI-28 — `pytest-xdist` not installed; `-n auto` silently ignored
**What.** `pykit-dim3:87-92` — `.github/workflows/ci.yml` runs `pytest -n auto` but `pytest-xdist` is not in any dev dependency group. pytest accepts `-n` as unknown and runs serial.
**Fix.** Add `pytest-xdist` to `[dependency-groups] dev`; verify `pytest -n auto -p xdist --collect-only | head` shows worker spawn; document worker count policy.

### PY-HI-29 — Coverage `fail_under = 60` while actual is 90.81%
**What.** `pyproject.toml:236` — gate is half of actual. Three packages already below 80%: `pykit-discovery 42.7%`, `pykit-vector-store 66.7%`, `pykit-dataset 68.4%` (pykit-dim3:93-107). Regression to 61% would still pass.
**Fix.** Raise `fail_under = 85` workspace-wide; carve per-pkg overrides only for the three laggards (with a sunset date in `docs/release-process.md`).

### PY-HI-30 — Zero integration test separation
**What.** `pykit-dim3:108-122` — no `@pytest.mark.integration`, no marker definitions in `pyproject.toml`, no separate CI job. Integration tests against `localhost:4318` (OTLP collector) hang in unit-test runs.
**Fix.** Define markers `unit`, `integration`, `slow`, `e2e` in `pyproject.toml`; default `addopts = "-m 'not integration and not e2e'"`; add `integration` job in CI with services. Sketch in § 5.

### PY-HI-31 — No deterministic clock; 90 wall-clock call sites
**What.** `pykit-dim3:123-141` — auth token expiry, OIDC refresh windows, JWT exp/iat/nbf, bench timing all use `time.time()`/`datetime.now()` directly. `freezegun`/`time-machine` absent. Tests are fragile.
**Fix.** Inject `Clock` Protocol (`now() -> datetime`, `monotonic() -> float`); default impl uses stdlib; tests use `FakeClock`. Add Ruff `DTZ` rule family to ban naive `datetime.now()` in lib code.

### PY-HI-32 — No property-based or fuzz testing
**What.** `pykit-dim3:142-154` — `hypothesis`, `atheris` absent. RFC 7807 deserialization, magic-byte detection in `pykit-media`, JWT parsers, all untested for adversarial inputs.
**Fix.** Add `hypothesis` to dev group; write strategies for `ProblemDetail`, `JWT`, `MediaType`. Add atheris fuzz harnesses (sketch in § 5 fuzz.yml).

### PY-HI-33 — `pykit-discovery` 10 test failures + layer violation
**What.** `tooling-pykit.log.tests2` — `DiscoveryComponent.__init__` requires `config=...` but tests pass `provider=...`; 10 failures at `test_discovery.py:150,166,177,188,195` and `test_discovery_extended.py:203,210,219,229,234`. Same test file path is implicated in PY-CR-01 mypy crash.
**Fix.** Decide canonical ctor signature; either (a) accept `provider` and adapt internally, or (b) update tests; either way add a kw-only API surface and `@deprecated` shim. Re-check `pykit_grpc → pykit_discovery` import (PY-CR-02) is the underlying architectural smell.

### PY-HI-34 — No code performance benchmarking infrastructure
**What.** `pykit-dim3:191-204` — no `pytest-benchmark`, no `pyperf`, no `pyinstrument`. The `bench/` directory and `pykit-bench` package are *workload generators*, not microbenchmarks.
**Fix.** Add `pytest-benchmark` to dev group; create `tests/bench/` with hot-path microbenches (Container.resolve, Errors.wrap, JWT verify, Registry lookup); CI bench job with `--benchmark-compare` against `main` baseline. Sketch in § 5 bench job.

### PY-HI-35 — Zero `lru_cache`/`cache` adoption
**What.** `pykit-dim3:205-210` — recomputing static lookups in hot paths (taxonomy maps, type→string, etc.).
**Fix.** Audit hot paths; apply `@functools.cache` to pure functions of immutable inputs; document cache-eviction policy where not lifelong.

### PY-HI-36 — Ruff misses 11 high-value rule families
**What.** `pyproject.toml` `[tool.ruff.lint] select = ["E","F","I","B","UP","SIM","TCH"]` — misses `S` (security), `TRY` (try-except), `PT` (pytest), `LOG` (logging), `G` (logging-format), `DTZ` (timezone), `PERF`, `C4` (comprehensions), `PIE`, `RET`, `T20` (no print), `N` (naming), `FURB`, `ANN` (annotations). pykit-dim3:267-287.
**Fix.** § 6 lint blueprint enables all of them with sensible per-file ignores.

### PY-HI-37 — 271 `Any` in public APIs of 50 unchecked packages
**What.** `pykit-dim3:298-326` — companion to PY-HI-05 (which counts only the 5 type-checked packages). Total `Any` blast radius is 271 + 99 = 370 sites.
**Fix.** Phased: (i) enable mypy on all 55 (PY-CR-01); (ii) per-package `disallow_any_explicit` ratchet; (iii) introduce `Protocol`s where structural; (iv) CI gate that diff cannot increase `Any` count.

### PY-HI-38 — mypy strict scope covers 5 of 55 (LT-04)
**What.** Duplicate axis of TS-01/CI-06; called out from the lint angle. See PY-CR-01.
**Fix.** See PY-CR-01.

### PY-HI-39 — Every action unpinned (12 references)
**What.** `.github/workflows/ci.yml:20,21,32,33,43,44,54,55,65,66` — `actions/checkout@v4`, `astral-sh/setup-uv@v5` repeated across six jobs. Mutable tags = supply-chain risk.
**Fix.** Pin to commit SHA with version comment: `uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1`. Wire `dependabot.yml` (PY-CR-08) `package-ecosystem: github-actions` for auto-bumps.

### PY-HI-40 — No build matrix
**What.** Single `ubuntu-latest`, single Python (whatever `setup-uv` resolves from `.python-version = 3.13`). No macOS, Windows, arm64, or N-1 Python (3.12).
**Fix.** § 5 ci.yml uses `strategy.matrix` over `os: [ubuntu-latest, ubuntu-latest-arm, macos-14, windows-latest]` × `python-version: ["3.12", "3.13"]`. Mark some combos `continue-on-error: true` initially; ratchet to required.

### PY-HI-41 — Coverage XML never uploaded
**What.** `.github/workflows/ci.yml:52-59` — `--cov-report=xml` is dead output; no `codecov/codecov-action` or artifact upload.
**Fix.** Either drop the flag or add Codecov upload (preferred). Add per-package `flag` to enable per-pkg trends.

### PY-HI-42 — mypy `--strict` on 5 of 55 in CI
**What.** Same as PY-CR-01 from the CI angle. `.github/workflows/ci.yml:42-48` invokes `uv run mypy` which uses the limited `[tool.mypy] packages` list.
**Fix.** See PY-CR-01.

### PY-HI-43 — No `uv lock --check` gate
**What.** `pykit-dim4:33` — combined with PY-CR-09 (`uv.lock` gitignored), there is zero lockfile hygiene. Even if lockfile were committed, no CI step verifies `uv.lock` matches `pyproject.toml`.
**Fix.** After PY-CR-09 commits the lockfile, add CI step `uv lock --check` (or `uv sync --frozen` in every job). Required-status-check.

### PY-HI-44 — No fuzz job (atheris)
**What.** `pykit-dim4:34` — parsers exist that warrant atheris (`pykit-media`, `pykit-errors` RFC 7807, `pykit-validation`, `pykit_messaging.kafka`).
**Fix.** § 5 `fuzz.yml` runs nightly (long timebox); short corpus run on each PR.

### PY-HI-45 — No `pre-commit` config
**What.** `pykit-dim4:44` — `.pre-commit-config.yaml` absent. Lint/format issues only caught in CI; round-trip wastes contributor time.
**Fix.** § 6 pre-commit config drop-in.

### PY-HI-46 — No `.editorconfig`, no `.gitattributes`
**What.** `pykit-dim4:45` — encoding and line-ending hygiene missing; cross-OS contributors will diff-spam.
**Fix.** § 6 drop-ins.

### PY-HI-47 — Python-version policy not pinned across packages
**What.** `pykit-dim4:46` — some package `requires-python` allows `>=3.11`, others `>=3.13`. Inconsistent.
**Fix.** Decide single floor (`>=3.12` recommended for current `match` + `TaskGroup` use); enforce via lint of all `pyproject.toml`.

### PY-HI-48 — hatch metadata incomplete
**What.** `pykit-dim4:47` — Missing `[project.urls]` (Source/Documentation/Changelog/Issues), classifiers (`Development Status`, `Programming Language :: Python :: 3.13`, `License`), `license-files`. PyPI listings will be barebones.
**Fix.** Add a shared `pyproject-template.toml`; CI lint that every package has the required keys.

### PY-HI-49 — `[project.optional-dependencies]` missing
**What.** `pykit-dim4:48` — no `pip install pykit[grpc]` story; users must install all dependencies even if they only want one subsystem.
**Fix.** Define `[project.optional-dependencies]` per package: `grpc`, `otlp`, `redis`, `kafka`, `argon2`, etc. Document in README.

### PY-HI-50 — No SECURITY.md
**What.** `pykit-dim4:71` — no responsible-disclosure path. GitHub will not display the "Security policy" tab.
**Fix.** `SECURITY.md` with PGP key, email, response SLA, supported-versions matrix.

### PY-HI-51 — README falsely cites missing CODE_OF_CONDUCT
**What.** README links `docs/code_of_conduct.md`; file does not exist.
**Fix.** Add `CODE_OF_CONDUCT.md` at root (Contributor Covenant 2.1); update README link.

### PY-HI-52 — No MAINTAINERS / GOVERNANCE / CODEOWNERS
**What.** `pykit-dim4:73` — opaque maintainership; PRs cannot be auto-routed.
**Fix.** `MAINTAINERS.md` (with handles + scope), `GOVERNANCE.md` (decision-making), `.github/CODEOWNERS` (per-package owners).

### PY-HI-53 — No per-package READMEs / no docs site
**What.** `pykit-dim4:74` — root README is ~600 lines covering 55 packages; no per-package README, no `docs/` site, no mkdocs/Sphinx config.
**Fix.** Per-pkg `README.md` (auto-template); `mkdocs.yml` + `mkdocs-material` for the umbrella site; deploy via GitHub Pages on release.

### PY-HI-54 — All packages stuck at `0.1.0`; no SemVer policy
**What.** Same fact pattern as PY-CR-11 from REL angle.
**Fix.** See PY-CR-11.

### PY-HI-55 — No tag protection / no signed tags / no release notes
**What.** `pykit-dim4:62` — git tag policy unenforced; no `release-please`/`release-drafter`.
**Fix.** Configure GitHub tag protection rule for `v*`; add `release-please` workflow per package.

### PY-HI-56 — No SBOM / no Sigstore attestations
**What.** `pykit-dim4:63` — supply-chain provenance absent.
**Fix.** § 5 release.yml uses `anchore/sbom-action` + `actions/attest-build-provenance`.

### PY-HI-57 — No deprecation policy
**What.** `pykit-dim4:64` — no `@deprecated` decorator, no `DeprecationWarning` discipline.
**Fix.** Add `pykit_errors.deprecated(reason: str, since: str, removed_in: str)` decorator; wire `warnings.warn(category=DeprecationWarning, stacklevel=2)`; document removal timeline (one minor with warning, removal next major).

### PY-HI-58 — No ISSUE_TEMPLATE / PULL_REQUEST_TEMPLATE
**What.** `.github/` lacks these. Triage ergonomics suffer.
**Fix.** `.github/ISSUE_TEMPLATE/{bug_report.yml,feature_request.yml,config.yml}` + `PULL_REQUEST_TEMPLATE.md` with checklist (tests, CHANGELOG entry, signoff).

### PY-HI-59 — No CHANGELOG.md
**What.** `pykit-dim4:89` — no Keep-A-Changelog file root or per-package.
**Fix.** Per-package `CHANGELOG.md` auto-managed by `release-please` (see PY-HI-55); root meta-changelog optional.

### PY-HI-60 — No CONTRIBUTING.md
**What.** `pykit-dim4:90` — README "Contributing" section is too thin; no DCO/CLA, no signoff policy, no dev-loop walkthrough.
**Fix.** `CONTRIBUTING.md` with: dev-env setup (`uv sync --all-extras`), test loop (`uv run pytest -m 'not integration'`), DCO `Signed-off-by:` requirement (gate via `dco-action`), commit-message convention, PR checklist.

---

## § 3 — 14-dimension assessment

For each dimension: **What's good**, **Problems**, **Redesign anchor** (forward link to § 4). The narrative is condensed; full evidence is in the dim files referenced in § 2.1.

### 3.1 Code Quality (CQ)
- **Good.** 88/88 `# type: ignore` directives are scoped (`[code]`); 53/55 `__init__.py` declare `__all__`; no `print()` debug pollution in core lib (only in CLI/dataset legitimately, modulo CQ-06/OB-05 fallbacks); `match` used (sparingly — CQ-11) where it shines.
- **Problems.** 99 `Any` in non-test code (CQ-07); 117 `raise X` without `from e` (CQ-03); 8 `assert` in lib (CQ-05); `Container.resolve` returns unsafe `T` (CQ-01); `# noqa: F821` masking real defect (CQ-02); inconsistent `pydantic` vs `dataclass` discipline (CQ-12); type-ignore in encryption factory (CQ-08); untyped DB-core sigs (CQ-09); `print()` in logging fallback (CQ-06).
- **Redesigns.** Adopt full Ruff rule families (CQ-04 → § 6); typed Container API (RP-CONT in § 4).

### 3.2 Architecture (AR)
- **Good.** `[tool.importlinter]` declared; foundation tier (`pykit_errors/config/logging`) clearly placed at the bottom; 53/55 `__all__` discipline.
- **Problems.** Layered contract **broken** at HEAD (AR-01) — only 39/55 packages enumerated; three module-level mutable registries with inconsistent API (AR-02); `Component.start_all` no rollback (AR-03); `Container._resolving` is process-global (AR-07); pykit facade stale (AR-04); some 55-package splits unjustified (AR-05); `pykit-discovery` eagerly imports `httpx` at __init__ (AR-06).
- **Redesigns.** RP-1 typed `Registry[K, V]`; RP-2 TaskGroup lifecycle; RP-5 ContextVar resolve stack — all in § 4.

### 3.3 Concurrency (CC)
- **Good.** Async-first I/O posture (with one exception, CC-05); use of `asyncio.gather` consistent in style.
- **Problems.** Fire-and-forget `create_task(self.stop())` (CC-01); `_cleanup_task` ref dropped (CC-02); `threading.Lock` in async hot paths (CC-03 + SC-14); `gather` without `return_exceptions=True` (CC-04); sync I/O in `async def` (CC-05); lost-task catalog (CC-06); shield+wait_for cancel race (CC-07); `_REGISTRY` mutation unlocked (CC-08); `WorkerPool` not pool-limited at submit time (CC-09).
- **Redesigns.** RP-2 (TaskGroup lifecycle); RP-DAG (TaskGroup-based DAG with BaseExceptionGroup); RP-DISC (TaskGroup discovery channel) — § 4.

### 3.4 Security (SC)
- **Good.** `hmac.compare_digest` used in API-key verifier (where present); AES-GCM with 96-bit random nonce in `pykit-encryption`; no `pickle`, no `yaml.load`, no `shell=True` in core, no SQL string interpolation; `bcrypt 5.0.0` used correctly where it appears; `pyjwt 2.12.1` and `cryptography 46.0.6` are recent (SC-18) — modulo CVEs.
- **Problems.** No OIDC verifier (SC-01 critical); no Auth middleware (SC-02 critical); JWT no leeway / no secret-length / `decode_unverified` exposed (SC-03); fake-Argon2 + non-CT compare (SC-04); no CI security gates (SC-05); pip-audit blocked by unpublished workspace pkgs (SC-06); `TLSConfig.is_enabled()` ignores `min_version` (SC-07); only `add_insecure_port` for gRPC (SC-08); OIDC refresh leaks response body (SC-09); RefreshError swallowed by broad except (SC-10); SHA-256 KDF substitute (SC-11); `run_shell` exists at all (SC-12); APIKey 401 swallows reasons (SC-13); `threading.Lock` in async ratelimit (SC-14); unbounded path-label cardinality in Prometheus (SC-15); private-state reach-in (SC-16); no CORS/CSRF helpers (SC-17). **5 live CVEs** (cryptography/pip/pygments/pytest/python-multipart).
- **Redesigns.** RP-OIDC `Verifier` + `JWKSCache`; RP-AUTH `Mode` + `AuthMiddleware` — § 4.

### 3.5 Errors & Observability (ER + OB)
- **Good.** `AppError` taxonomy exists; ProblemDetail RFC 7807 mapper exists; structured logger via `pykit-logging`; OperationMetrics scaffold exists.
- **Problems.** `_TYPE_BASE_URI` global (ER-01); `__str__` leaks cause (ER-02); no `Wrap` classifier (ER-03); auth response shape diverges from ProblemDetail (ER-04); `RefreshError` not in taxonomy (ER-05); taxonomy maps unguarded (ER-06); cause loss in interceptor (ER-07); `error=str(exc)` in LoggingInterceptor (ER-08); **no /healthz** (OB-01 critical); OTel globals mutated (OB-02); no exporter wired (OB-03); no propagator set (OB-04); print in setup_logging (OB-05); unbounded labels (OB-06); no span on OIDC refresh (OB-07); no `record_exception` in interceptor (OB-08); ServiceHealth lacks per-component metadata (OB-09); correlation_id not linked to span (OB-10); no rate-limit metric (OB-11).
- **Redesigns.** RP-WRAP `wrap()` classifier; RP-TEL idempotent `Telemetry.init/shutdown`; RP-HEALTH `HealthRegistry` ASGI app; RP-RESULT `AppResult[T]` — § 4.

### 3.6 Performance (PF)
- **Good.** Async-first; no obvious N+1 patterns; `pykit-bench` workload generators exist.
- **Problems.** No microbenchmark infra (PF-01); zero `lru_cache` adoption (PF-02); `gather` where TaskGroup wins (PF-03); string concat in tight parser loop (PF-04); no profiling hooks (PF-05); no `__slots__` audit (PF-06); naming collision `pykit-bench` vs `bench/` (PF-07).
- **Redesigns.** pytest-benchmark harness + bench job — § 5/6.

### 3.7 Testing (TS)
- **Good.** Coverage 90.81% global; `--import-mode=importlib`; pytest config has reasonable defaults.
- **Problems.** mypy broken in CI (TS-01); xdist not installed (TS-02); 3 packages below 80% with gate at 60% (TS-03); no integration separation (TS-04); no deterministic clock (TS-05); no hypothesis/atheris (TS-06); 10 discovery test failures (TS-07); mock-heavy where fakes exist (TS-08); 8 packages with no coverage (TS-09); no root conftest.py (TS-10).
- **Redesigns.** Markers + integration job; Clock Protocol + FakeClock; pytest-benchmark harness — § 5/6.

### 3.8 Lint (LT)
- **Good.** Ruff + ruff-format + mypy + import-linter all *configured*. 88/88 `# type: ignore` are scoped.
- **Problems.** Ruff selection misses 11 rule families (LT-01); TCH001/2/3 blanket-ignored (LT-02); 271 `Any` in unchecked pkgs (LT-03); mypy 5/55 (LT-04); no independence contract (LT-05); no bandit/pip-audit gate (LT-06); test per-file-ignores too narrow (LT-07); print in lib code (LT-08).
- **Redesigns.** Full ruff/mypy/pre-commit blueprint — § 6.

### 3.9 CI/CD (CI)
- **Good.** A workflow exists; `setup-uv` is used (correct ecosystem choice).
- **Problems.** No release.yml (CI-01 critical); no security scanning (CI-02 critical); unpinned actions (CI-03); no matrix (CI-04); coverage-XML never uploaded (CI-05); mypy 5/55 (CI-06); no lock gate (CI-07); no fuzz (CI-08); no per-job permission scoping (CI-09); no caching (CI-10); no concurrency group (CI-11); branch-protection unverified (CI-12); no nightly job (CI-13); no actions/packages perm minimization audit (CI-14); no badge (CI-15).
- **Redesigns.** ci.yml / security.yml / fuzz.yml / release.yml drop-ins — § 5.

### 3.10 Toolchain (TC)
- **Good.** uv chosen (modern); hatch chosen (PEP 621); Python 3.13.
- **Problems.** No dependabot (TC-01 critical); `uv.lock` gitignored (TC-02 critical); no pre-commit (TC-03); no .editorconfig/.gitattributes (TC-04); python-version inconsistent (TC-05); hatch metadata incomplete (TC-06); no optional-dependencies (TC-07); no workspace excludes (TC-08); no hatch.version source (TC-09); some packages lack py.typed (TC-10); coverage source not declared per-pkg (TC-11); no `[tool.uv.sources]` private-index docs (TC-12).
- **Redesigns.** Per-package `pyproject-template.toml`; root `dependabot.yml`; `pre-commit-config.yaml` — § 5/6.

### 3.11 Docs (DOC)
- **Good.** Root README is comprehensive; some packages have docstrings.
- **Problems.** No SECURITY.md (DOC-01); README references missing CoC (DOC-02); no MAINTAINERS/GOVERNANCE/CODEOWNERS (DOC-03); no per-pkg READMEs / no docs site (DOC-04); no ARCHITECTURE.md (DOC-05); no release-process doc (DOC-06); no examples/ (DOC-07); no API reference auto-gen (DOC-08); README quickstart thin (DOC-09); no glossary/concepts page (DOC-10).
- **Redesigns.** mkdocs scaffold; root files; per-pkg README template.

### 3.12 Release (REL)
- **Good.** Decision to use uv + hatch is forward-looking. Packages have unique names.
- **Problems.** No release workflow (REL-01 critical); no PyPI Trusted Publishing (REL-02 critical); all packages 0.1.0 (REL-03); no signed tags / no release notes automation (REL-04); no SBOM/Sigstore (REL-05); no deprecation policy (REL-06); hatch wheel.packages not validated for monorepo (REL-07).
- **Redesigns.** release.yml + per-package release-please + SemVer policy doc — § 5/7.

### 3.13 Hygiene (HY)
- **Good.** Mostly tidy git history; sensible `.gitignore` skeleton.
- **Problems.** No issue/PR templates (HY-01); no CHANGELOG (HY-02); no CONTRIBUTING.md (HY-03); .gitignore over-broad/under-broad (HY-04); no FUNDING.yml (HY-05); no issue forms (HY-06); no labeler config (HY-07); no stale-bot policy (HY-08); no .gitleaks.toml (HY-09); no commitlint/conventional-commits (HY-10).
- **Redesigns.** GitHub community-health files batch — § 5.

### 3.14 Cross-Sibling — pykit vs gokit vs rskit
- **Discipline parity.** pykit ships ruff + mypy + import-linter — same toolchain bench as gokit's golangci-lint + go vet + go-arch-lint. The *discipline* is missing in both (rules under-tightened, contracts broken at HEAD).
- **HTTP framework gap.** This is the single biggest pykit-only deficit. gokit has chi/gin patterns and at least *attempts* HTTP middleware; pykit ships **only gRPC** as a server stack — no FastAPI/Starlette adapter. Auth, healthz, CORS, CSRF all missing as a consequence (PY-CR-04, PY-CR-05).
- **Lockfile parity.** gokit relies on `go.sum` (committed by default); pykit's choice to gitignore `uv.lock` is a *regression* against ecosystem norms.
- **Release parity.** gokit ships *signed git tags* at minimum; pykit has neither tags nor releases (PY-CR-11). All three kits lack PyPI/proxy.golang.org/crates.io publication automation, but pykit is furthest behind.
- **Coverage parity.** pykit's 90.81% is **best of the three** by raw number, but its `fail_under = 60` makes the gate weakest. gokit and rskit both gate at ~80%.
- **Recommendation.** Treat the three kits as one supply-chain perimeter: shared `release-please` config, shared `dependabot.yml` template, shared community-health files, shared SECURITY.md disclosure address.

---

## § 4 Redesign sketches

All sketches are compileable Python 3.13 (no pseudo-code). They are intended to be lifted directly into the repository.

### RP-1 Typed `Registry[K, V]` (replaces three module-level dicts; AR-02, CC-08)
```python
from __future__ import annotations
import asyncio
from collections.abc import Iterator, Mapping
from typing import Generic, TypeVar

K = TypeVar("K", bound=str)
V = TypeVar("V")

class RegistryError(Exception):
    pass

class Registry(Generic[K, V]):
    """Async-safe typed registry. Replaces ad-hoc module-level dicts."""

    __slots__ = ("_name", "_lock", "_entries")

    def __init__(self, name: str) -> None:
        self._name = name
        self._lock = asyncio.Lock()
        self._entries: dict[K, V] = {}

    async def register(self, key: K, value: V, *, replace: bool = False) -> None:
        async with self._lock:
            if not replace and key in self._entries:
                raise RegistryError(f"{self._name}: {key!r} already registered")
            self._entries[key] = value

    async def unregister(self, key: K) -> V | None:
        async with self._lock:
            return self._entries.pop(key, None)

    def get(self, key: K) -> V | None:
        return self._entries.get(key)

    def require(self, key: K) -> V:
        v = self._entries.get(key)
        if v is None:
            raise RegistryError(f"{self._name}: {key!r} not registered")
        return v

    def __iter__(self) -> Iterator[K]:
        return iter(self._entries)

    def items(self) -> Mapping[K, V]:
        return dict(self._entries)
```

### RP-2 TaskGroup-based lifecycle with rollback (AR-03, CC-01)
```python
from __future__ import annotations
import asyncio
from collections.abc import Sequence
from typing import Protocol

class Component(Protocol):
    name: str
    async def start(self) -> None: ...
    async def stop(self) -> None: ...

class LifecycleError(ExceptionGroup):
    pass

async def start_all(components: Sequence[Component]) -> list[Component]:
    """Start in declared order; on failure, stop the started subset in LIFO."""
    started: list[Component] = []
    try:
        for c in components:
            await c.start()
            started.append(c)
        return started
    except BaseException as primary:
        rollback_errors: list[BaseException] = []
        for c in reversed(started):
            try:
                await c.stop()
            except BaseException as e:
                rollback_errors.append(e)
        if rollback_errors:
            raise LifecycleError(
                "start_all rolled back with errors",
                [primary, *rollback_errors],
            )
        raise

async def stop_all(components: Sequence[Component]) -> None:
    """Stop in reverse order; aggregate errors via ExceptionGroup."""
    errors: list[BaseException] = []
    for c in reversed(components):
        try:
            await c.stop()
        except BaseException as e:
            errors.append(e)
    if errors:
        raise LifecycleError("stop_all errors", errors)
```

### RP-3 ContextVar-scoped DI resolve stack (AR-07)
```python
from __future__ import annotations
from contextvars import ContextVar
from typing import TypeVar

T = TypeVar("T")
_resolving: ContextVar[frozenset[type]] = ContextVar("_resolving", default=frozenset())

class CycleError(RuntimeError):
    pass

class Container:
    def resolve(self, t: type[T]) -> T:
        stack = _resolving.get()
        if t in stack:
            raise CycleError(f"DI cycle: {' -> '.join(s.__name__ for s in stack)} -> {t.__name__}")
        token = _resolving.set(stack | {t})
        try:
            return self._build(t)  # implementation
        finally:
            _resolving.reset(token)

    def resolve_optional(self, t: type[T]) -> T | None:
        try:
            return self.resolve(t)
        except KeyError:
            return None

    def _build(self, t: type[T]) -> T: ...  # impl elided
```

### RP-OIDC `Verifier` + `JWKSCache` (PY-CR-03)
```python
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
import httpx
import jwt
from jwt import PyJWK, PyJWKSet, InvalidTokenError

@dataclass(frozen=True)
class Claims:
    sub: str
    iss: str
    aud: str
    exp: int
    iat: int
    raw: dict[str, Any]

class JWKSCache:
    """Single-flight JWKS fetcher with TTL + 304-aware refresh."""

    def __init__(self, jwks_uri: str, *, ttl_seconds: int = 600, http: httpx.AsyncClient | None = None) -> None:
        self._uri = jwks_uri
        self._ttl = ttl_seconds
        self._http = http or httpx.AsyncClient(timeout=5.0)
        self._lock = asyncio.Lock()
        self._inflight: asyncio.Task[PyJWKSet] | None = None
        self._cached: tuple[PyJWKSet, float] | None = None

    async def get(self, *, force: bool = False) -> PyJWKSet:
        now = time.monotonic()
        if not force and self._cached and (now - self._cached[1]) < self._ttl:
            return self._cached[0]
        async with self._lock:
            if not force and self._cached and (time.monotonic() - self._cached[1]) < self._ttl:
                return self._cached[0]
            if self._inflight is None or self._inflight.done():
                self._inflight = asyncio.create_task(self._fetch())
        return await self._inflight

    async def _fetch(self) -> PyJWKSet:
        r = await self._http.get(self._uri)
        r.raise_for_status()
        ks = PyJWKSet.from_dict(r.json())
        self._cached = (ks, time.monotonic())
        return ks

class Verifier:
    """OIDC ID-token verifier — RFC 8725 hardened."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks: JWKSCache,
        leeway_seconds: int = 60,
        require_nonce: bool = False,
        allowed_algs: frozenset[str] = frozenset({"RS256", "ES256"}),
    ) -> None:
        if not allowed_algs.issubset({"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}):
            raise ValueError("HMAC and 'none' algorithms are forbidden")
        self._iss, self._aud = issuer, audience
        self._jwks, self._leeway = jwks, leeway_seconds
        self._require_nonce = require_nonce
        self._algs = allowed_algs

    async def verify(self, token: str, *, nonce: str | None = None) -> Claims:
        try:
            unverified = jwt.get_unverified_header(token)
        except InvalidTokenError as e:
            raise InvalidTokenError("malformed token header") from e
        kid = unverified.get("kid")
        alg = unverified.get("alg")
        if alg not in self._algs:
            raise InvalidTokenError(f"alg {alg!r} not in allowed set")
        ks = await self._jwks.get()
        try:
            jwk: PyJWK = ks[kid]
        except KeyError:
            ks = await self._jwks.get(force=True)
            jwk = ks[kid]
        if jwk.algorithm_name != alg:
            raise InvalidTokenError("alg/jwk mismatch")
        payload = jwt.decode(
            token, key=jwk.key, algorithms=[alg],
            audience=self._aud, issuer=self._iss,
            leeway=self._leeway,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
        if self._require_nonce or nonce is not None:
            if payload.get("nonce") != nonce:
                raise InvalidTokenError("nonce mismatch")
        return Claims(sub=payload["sub"], iss=payload["iss"], aud=payload["aud"],
                      exp=payload["exp"], iat=payload["iat"], raw=payload)
```

### RP-AUTH `Mode` enum + `AuthMiddleware` (PY-CR-04)
```python
from __future__ import annotations
import enum
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

class Mode(enum.Enum):
    Disabled = "disabled"
    Optional = "optional"
    Required = "required"

class Principal(Protocol):
    @property
    def subject(self) -> str: ...
    @property
    def claims(self) -> dict[str, Any]: ...

class AuthVerifier(Protocol):
    async def verify(self, token: str) -> Principal: ...

ASGIApp = Callable[[dict, Callable, Callable], Awaitable[None]]

class AuthMiddleware:
    """RFC 6750 bearer-only auth middleware."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        verifier: AuthVerifier,
        mode: Mode = Mode.Required,
        excluded: tuple[str, ...] = (),
    ) -> None:
        self._app, self._verifier, self._mode = app, verifier, mode
        self._excluded = tuple(excluded)

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http" or self._mode is Mode.Disabled:
            return await self._app(scope, receive, send)
        path = scope["path"]
        if any(path == p or path.startswith(p + "/") for p in self._excluded):
            return await self._app(scope, receive, send)
        token = self._extract_bearer(scope)
        if token is None:
            if self._mode is Mode.Optional:
                return await self._app(scope, receive, send)
            return await self._challenge(send, "invalid_request", "missing bearer token")
        try:
            principal = await self._verifier.verify(token)
        except Exception:
            return await self._challenge(send, "invalid_token", "token verification failed")
        scope.setdefault("state", {})["principal"] = principal
        await self._app(scope, receive, send)

    @staticmethod
    def _extract_bearer(scope: dict) -> str | None:
        for name, value in scope.get("headers", []):
            if name == b"authorization":
                v = value.decode("latin-1")
                if v.lower().startswith("bearer "):
                    return v[7:].strip() or None
        return None

    @staticmethod
    async def _challenge(send: Callable, error: str, desc: str) -> None:
        await send({"type": "http.response.start", "status": 401, "headers": [
            (b"www-authenticate", f'Bearer error="{error}", error_description="{desc}"'.encode("latin-1")),
            (b"content-type", b"application/problem+json"),
        ]})
        body = (
            '{"type":"about:blank","title":"Unauthorized","status":401,'
            f'"detail":"{desc}"}}'
        ).encode()
        await send({"type": "http.response.body", "body": body})
```

### RP-HEALTH `HealthRegistry` ASGI app (PY-CR-05)
```python
from __future__ import annotations
import asyncio
import enum
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

class Status(enum.Enum):
    Healthy = "healthy"
    Degraded = "degraded"
    Unhealthy = "unhealthy"

@dataclass(frozen=True)
class ComponentHealth:
    name: str
    status: Status
    latency_ms: float
    checked_at: float
    error: str | None = None

CheckFn = Callable[[], Awaitable[None]]

class HealthRegistry:
    def __init__(self) -> None:
        self._liveness: dict[str, CheckFn] = {}
        self._readiness: dict[str, CheckFn] = {}

    def add_liveness(self, name: str, fn: CheckFn) -> None:
        self._liveness[name] = fn

    def add_readiness(self, name: str, fn: CheckFn) -> None:
        self._readiness[name] = fn

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            return
        path = scope["path"]
        if path == "/healthz":
            checks = self._liveness
        elif path == "/readyz":
            checks = self._readiness
        else:
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b""})
            return
        results = await asyncio.gather(*(self._run(n, fn) for n, fn in checks.items()))
        overall = Status.Healthy if all(r.status is Status.Healthy for r in results) else (
            Status.Unhealthy if any(r.status is Status.Unhealthy for r in results) else Status.Degraded
        )
        body = json.dumps({
            "status": overall.value,
            "components": [
                {"name": r.name, "status": r.status.value,
                 "latency_ms": r.latency_ms, "checked_at": r.checked_at,
                 **({"error": r.error} if r.error else {})}
                for r in results
            ],
        }).encode()
        status_code = 200 if overall is not Status.Unhealthy else 503
        await send({"type": "http.response.start", "status": status_code,
                    "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    async def _run(name: str, fn: CheckFn) -> ComponentHealth:
        start = time.monotonic()
        try:
            await asyncio.wait_for(fn(), timeout=2.0)
            return ComponentHealth(name, Status.Healthy, (time.monotonic() - start) * 1000, time.time())
        except Exception as e:
            return ComponentHealth(name, Status.Unhealthy, (time.monotonic() - start) * 1000, time.time(), str(e))
```

### RP-WRAP `wrap()` exception classifier (ER-03)
```python
from __future__ import annotations
import asyncio
from typing import Any
from .codes import ErrorCode
from .app_error import AppError

_CLASS_TO_CODE: dict[type[BaseException], ErrorCode] = {
    asyncio.TimeoutError: ErrorCode.DEADLINE_EXCEEDED,
    TimeoutError: ErrorCode.DEADLINE_EXCEEDED,
    PermissionError: ErrorCode.PERMISSION_DENIED,
    FileNotFoundError: ErrorCode.NOT_FOUND,
    ConnectionRefusedError: ErrorCode.UNAVAILABLE,
    ConnectionResetError: ErrorCode.UNAVAILABLE,
    KeyError: ErrorCode.NOT_FOUND,
    ValueError: ErrorCode.INVALID_ARGUMENT,
}

def wrap(e: BaseException, *, code: ErrorCode | None = None, **fields: Any) -> AppError:
    """Classify a stdlib exception into an AppError; preserve cause chain."""
    if isinstance(e, AppError):
        return e if code is None else e.with_code(code)
    chosen = code or _CLASS_TO_CODE.get(type(e), ErrorCode.INTERNAL)
    return AppError(code=chosen, message=type(e).__name__, fields=fields, cause=e)
```

### RP-TEL idempotent `Telemetry.init/shutdown` (OB-02..OB-04)
```python
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Self
from opentelemetry import trace, metrics, propagate
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

@dataclass
class TelemetryConfig:
    service_name: str
    otlp_endpoint: str | None = None

class Telemetry:
    _instance: "Telemetry | None" = None
    _lock = asyncio.Lock()

    def __init__(self, cfg: TelemetryConfig, tracer_provider: TracerProvider, meter_provider: MeterProvider) -> None:
        self.cfg, self.tracer_provider, self.meter_provider = cfg, tracer_provider, meter_provider

    @classmethod
    async def init(cls, cfg: TelemetryConfig) -> Self:
        async with cls._lock:
            if cls._instance is not None:
                return cls._instance  # type: ignore[return-value]
            tp = TracerProvider()
            exporter = OTLPSpanExporter(endpoint=cfg.otlp_endpoint) if cfg.otlp_endpoint else ConsoleSpanExporter()
            tp.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(tp)
            mp = MeterProvider()
            metrics.set_meter_provider(mp)
            propagate.set_global_textmap(CompositePropagator([
                TraceContextTextMapPropagator(), W3CBaggagePropagator()
            ]))
            cls._instance = cls(cfg, tp, mp)
            return cls._instance  # type: ignore[return-value]

    async def shutdown(self) -> None:
        self.tracer_provider.shutdown()
        self.meter_provider.shutdown()
        type(self)._instance = None
```

### RP-RESULT `AppResult[T]` (ER-03 sibling, type-safe error returns)
```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, TypeVar
from .app_error import AppError

T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T

@dataclass(frozen=True, slots=True)
class Err:
    error: AppError

AppResult = Ok[T] | Err

def ok(v: T) -> Ok[T]: return Ok(v)
def err(e: AppError) -> Err: return Err(e)
```

### RP-CLOCK Deterministic `Clock` Protocol (TS-05, PF-01)
```python
from __future__ import annotations
import time
from datetime import UTC, datetime
from typing import Protocol

class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...

class SystemClock:
    def now(self) -> datetime: return datetime.now(UTC)
    def monotonic(self) -> float: return time.monotonic()

class FakeClock:
    def __init__(self, start: datetime, mono: float = 0.0) -> None:
        self._t, self._m = start, mono
    def now(self) -> datetime: return self._t
    def monotonic(self) -> float: return self._m
    def advance(self, seconds: float) -> None:
        self._m += seconds
        from datetime import timedelta
        self._t += timedelta(seconds=seconds)
```

### RP-BENCH pytest-benchmark microbench harness (PF-01)
```python
# tests/bench/test_container_resolve.py
import pytest
from pykit_container import Container

class A: pass
class B:
    def __init__(self, a: A) -> None: self.a = a

@pytest.fixture
def c() -> Container:
    c = Container()
    c.register(A, lambda: A())
    c.register(B, lambda c: B(c.resolve(A)))
    return c

def test_resolve_b(benchmark, c):
    benchmark(lambda: c.resolve(B))
```

---

## § 5 CI/CD blueprint — drop-in YAML

All paths assume monorepo root. Pin every action to a SHA in real adoption (omitted here for readability — use `dependabot.yml` to keep them updated).

### 5.1 `.github/workflows/ci.yml` (replacement)
```yaml
name: ci
on:
  push: { branches: [main] }
  pull_request:
permissions: { contents: read }
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with: { enable-cache: true }
      - run: uv sync --all-packages --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run lint-imports
  type:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with: { enable-cache: true }
      - run: uv sync --all-packages --frozen
      - run: uv run mypy --strict .
  test:
    needs: [lint, type]
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ["3.13"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python }} }
      - uses: astral-sh/setup-uv@v4
        with: { enable-cache: true }
      - run: uv sync --all-packages --frozen
      - run: uv run pytest -n auto --cov --cov-report=xml --cov-fail-under=80
      - uses: codecov/codecov-action@v4
        with: { files: ./coverage.xml, fail_ci_if_error: true }
  lock:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv lock --check
  bench:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-packages --frozen
      - run: uv run pytest tests/bench/ --benchmark-only --benchmark-json=bench.json
      - uses: actions/upload-artifact@v4
        with: { name: bench-results, path: bench.json }
```

### 5.2 `.github/workflows/security.yml`
```yaml
name: security
on:
  push: { branches: [main] }
  pull_request:
  schedule: [{ cron: "23 4 * * *" }]
permissions: { contents: read, security-events: write }
jobs:
  pip-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-packages --frozen
      - run: uv pip install pip-audit
      - run: uv run pip-audit --strict --ignore-vuln GHSA-XXXX  # narrow exceptions only
  bandit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install bandit[toml]
      - run: bandit -r packages/ -c pyproject.toml -f sarif -o bandit.sarif
      - uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: bandit.sarif }
  semgrep:
    runs-on: ubuntu-latest
    container: returntocorp/semgrep
    steps:
      - uses: actions/checkout@v4
      - run: semgrep ci --sarif --output=semgrep.sarif
      - uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: semgrep.sarif }
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
        env: { GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }} }
```

### 5.3 `.github/workflows/fuzz.yml`
```yaml
name: fuzz
on:
  schedule: [{ cron: "0 6 * * *" }]
  workflow_dispatch:
permissions: { contents: read }
jobs:
  atheris:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }  # atheris not yet 3.13-clean
      - run: pip install atheris
      - run: |
          for f in tests/fuzz/fuzz_*.py; do
            timeout 300 python "$f" -atheris_runs=200000 || exit 1
          done
```

### 5.4 `.github/workflows/release.yml`
```yaml
name: release
on:
  push:
    tags: ["v*", "*-v*"]  # supports unified and per-package tags
permissions: { contents: write, id-token: write }  # OIDC for PyPI Trusted Publishing
jobs:
  build:
    runs-on: ubuntu-latest
    outputs: { package: ${{ steps.id.outputs.package }} }
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - id: id
        run: |
          tag="${GITHUB_REF_NAME}"
          if [[ "$tag" == v* ]]; then echo "package=all" >> "$GITHUB_OUTPUT"
          else echo "package=${tag%-v*}" >> "$GITHUB_OUTPUT"
          fi
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-packages --frozen
      - run: |
          if [[ "${{ steps.id.outputs.package }}" == "all" ]]; then
            uv build --all-packages --out-dir dist/
          else
            uv build --package "${{ steps.id.outputs.package }}" --out-dir dist/
          fi
      - uses: actions/upload-artifact@v4
        with: { name: dist, path: dist/ }
  attest:
    needs: build
    runs-on: ubuntu-latest
    permissions: { id-token: write, attestations: write, contents: read }
    steps:
      - uses: actions/download-artifact@v4
        with: { name: dist, path: dist/ }
      - uses: actions/attest-build-provenance@v1
        with: { subject-path: "dist/*" }
  publish:
    needs: [build, attest]
    runs-on: ubuntu-latest
    environment: pypi
    permissions: { id-token: write }
    steps:
      - uses: actions/download-artifact@v4
        with: { name: dist, path: dist/ }
      - uses: pypa/gh-action-pypi-publish@release/v1
  github-release:
    needs: publish
    runs-on: ubuntu-latest
    permissions: { contents: write }
    steps:
      - uses: actions/checkout@v4
      - uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
          files: dist/*
```

### 5.5 `.github/dependabot.yml`
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule: { interval: "weekly" }
    groups:
      runtime: { patterns: ["*"], exclude-patterns: ["pytest*", "ruff", "mypy", "hatch*"] }
      dev: { patterns: ["pytest*", "ruff", "mypy", "hatch*"] }
    open-pull-requests-limit: 10
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "weekly" }
```

### 5.6 GitHub community-health files (one-shot batch)
- `SECURITY.md` — disclosure address + supported-version table.
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1.
- `CONTRIBUTING.md` — local-dev, branching, conventional commits, signed-off-by.
- `CODEOWNERS` — `* @org/pykit-maintainers`.
- `MAINTAINERS.md` + `GOVERNANCE.md`.
- `.github/ISSUE_TEMPLATE/{bug,feature,security}.yml` (issue *forms*, not legacy md).
- `.github/PULL_REQUEST_TEMPLATE.md` — checklist + breaking-change radio.
- `.github/labeler.yml` + `.github/workflows/labeler.yml`.
- `.github/FUNDING.yml`.
- `.gitleaks.toml`.

---

## § 6 Lint blueprint

### 6.1 `pyproject.toml — [tool.ruff.lint]` (full replacement)
```toml
[tool.ruff]
line-length = 100
target-version = "py313"
extend-exclude = [".venv", "build", "dist"]

[tool.ruff.lint]
select = [
  "E", "W", "F", "I", "B", "UP", "SIM", "C90",
  "S",     # bandit-equivalents
  "TRY",   # exception anti-patterns (raise-from, broad-except)
  "PT",    # pytest style
  "LOG",   # logging f-string forbidden
  "G",     # logging extra discipline
  "DTZ",   # naive datetime forbidden
  "PERF",  # perf anti-patterns
  "C4",    # comprehensions
  "PIE",   # idiom corrections
  "RET",   # return discipline
  "T20",   # no print
  "N",     # PEP 8 naming
  "FURB",  # modern stdlib
  "ANN",   # require annotations
  "ASYNC", # async-correctness
  "TCH",   # TYPE_CHECKING discipline
  "PTH",   # pathlib over os.path
  "RUF",   # ruff-native checks
]
ignore = [
  "ANN101", "ANN102",  # self/cls
  "TRY003",            # long messages OK in this codebase
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "ANN", "PLR2004", "T20"]
"**/conftest.py" = ["ANN", "S101"]

[tool.ruff.lint.isort]
known-first-party = ["pykit_*"]
combine-as-imports = true
```

### 6.2 `pyproject.toml — [tool.mypy]` (replace per-package)
```toml
[tool.mypy]
python_version = "3.13"
strict = true
warn_unused_ignores = true
warn_redundant_casts = true
warn_unreachable = true
disallow_any_explicit = true
disallow_any_generics = true
no_implicit_reexport = true
explicit_package_bases = true
mypy_path = "packages"
files = "packages"
plugins = ["pydantic.mypy"]
exclude = ["build/", "dist/", "\\.venv/"]

# Per-package overrides (one block per package; keep tight)
[[tool.mypy.overrides]]
module = ["tests.*"]
disallow_any_explicit = false
disallow_untyped_defs = false
```

### 6.3 `pyproject.toml — [tool.pytest.ini_options]` (replacement)
```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests", "packages"]
python_files = ["test_*.py"]
addopts = [
  "--strict-markers",
  "--strict-config",
  "-ra",
  "--import-mode=importlib",
  "--cov-report=term-missing:skip-covered",
  "--cov-report=xml",
  "--cov-fail-under=80",
  "-n", "auto",
]
filterwarnings = [
  "error",
  "ignore::DeprecationWarning:google.*",
]
markers = [
  "slow: tests that take >1s",
  "integration: requires external services",
  "fuzz: atheris fuzz harness",
]
asyncio_mode = "auto"
```

### 6.4 `.importlinter` / `[tool.importlinter]` (full enumeration)
```toml
[tool.importlinter]
root_packages = [
  # Tier 0 — foundation
  "pykit_errors", "pykit_config", "pykit_logging",
  # Tier 1 — primitives (alphabetised; keep enumeration exhaustive)
  "pykit_async_utils", "pykit_clock", "pykit_collections", "pykit_strings", "pykit_uuid",
  # Tier 2 — IO & infra
  "pykit_db_core", "pykit_db_postgres", "pykit_db_sqlite", "pykit_http", "pykit_grpc",
  # Tier 3 — composition
  "pykit_container", "pykit_lifecycle", "pykit_discovery",
  # Tier 4 — apps
  "pykit_app", "pykit_cli", "pykit_dataset",
  # ... ENUMERATE ALL 55 — placeholder; do not ship partial list
]

[[tool.importlinter.contracts]]
name = "Foundation must not import upward"
type = "forbidden"
source_modules = ["pykit_errors", "pykit_config", "pykit_logging"]
forbidden_modules = ["pykit_*"]
ignore_imports = ["pykit_logging -> pykit_errors", "pykit_config -> pykit_errors"]

[[tool.importlinter.contracts]]
name = "Each package independent of every other (except declared deps)"
type = "independence"
modules = ["pykit_*"]
```

### 6.5 `.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks: [{ id: ruff, args: [--fix] }, { id: ruff-format }]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.2
    hooks: [{ id: mypy, additional_dependencies: ["pydantic", "types-requests"] }]
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.10
    hooks: [{ id: bandit, args: ["-c", "pyproject.toml"] }]
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.1
    hooks: [{ id: gitleaks }]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-merge-conflict
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
        args: ["--maxkb=500"]
```

### 6.6 `.editorconfig`
```ini
root = true
[*]
charset = utf-8
end_of_line = lf
indent_style = space
insert_final_newline = true
trim_trailing_whitespace = true
[*.py]
indent_size = 4
max_line_length = 100
[*.{yml,yaml,toml,md}]
indent_size = 2
[Makefile]
indent_style = tab
```

### 6.7 `.gitattributes`
```gitattributes
* text=auto eol=lf
*.py text diff=python
*.toml text
*.yaml text
*.md text
*.lock text -diff
*.png binary
*.jpg binary
*.ico binary
```

---

## § 7 Roadmap by milestone

### v0.x — Cleanup (target: 4 weeks)
**Goal:** turn the build green; stop shipping false signal.

1. **Tooling triage (week 1).**
   - PY-CR-01 mypy: delete duplicate `test_edge_cases.py`; raise mypy adoption to all 55 packages by adding `[[tool.mypy.overrides]]` exemptions for legacy ones.
   - PY-CR-02 import-linter: enumerate all 55 packages in `[tool.importlinter]`; switch foundation contract to `forbidden`-type as in § 6.4.
   - PY-CR-08 tests: fix `DiscoveryComponent` ctor drift in 10 failing tests (rename `provider=` → `config=` or vice versa, decide one).
   - PY-CR-10 add `pip-audit` to CI; bump cryptography 46.0.7 / pip 26.0.2 / pygments 2.20.0 / pytest 9.0.3 / python-multipart 0.0.26.
2. **Repo hygiene (week 2).**
   - PY-CR-09 commit `uv.lock`; remove from `.gitignore`; add `uv lock --check` job.
   - PY-CR-07 land `security.yml` from § 5.2.
   - PY-CR-06 land `release.yml` from § 5.4 (do not yet *use* it for v0.x; gates only).
   - Add `dependabot.yml` from § 5.5.
3. **HTTP framework decision (week 3).**
   - Spike: FastAPI vs Starlette adoption (or document explicit non-decision and ship `pykit-asgi-starter`).
   - Either path: implement `HealthRegistry` (RP-HEALTH) and wire `/healthz` + `/readyz`. Resolves PY-CR-05.
4. **Cleanup remainder (week 4).**
   - Land community-health files (SECURITY.md, CODE_OF_CONDUCT.md, CONTRIBUTING.md, CODEOWNERS).
   - Eliminate all `print()` from lib code (PY-HI tier).
   - Replace 117 `raise X` → `raise X from e` in one PR per package.

**Exit criteria:** CI green on three OS × Python 3.13; coverage gate raised to 80%; mypy strict on all 55 pkgs; import-linter contracts enforced; zero CVEs in pip-audit; `uv.lock` committed.

### v0.y — Redesigns (target: 8 weeks following v0.x)
**Goal:** replace the architectural debt; close the High tier.

1. **Lifecycle + DI (weeks 1-2).** Land RP-1 (`Registry[K, V]`), RP-2 (TaskGroup `start_all`/`stop_all`), RP-3 (ContextVar resolve stack). Migrate `pykit-component`, `pykit-container`, `pykit-discovery`. Resolves AR-02, AR-03, AR-07, CC-01, CC-08.
2. **Auth perimeter (weeks 3-4).** Land RP-OIDC (`Verifier` + `JWKSCache`), RP-AUTH (`Mode` + `AuthMiddleware`). Plumb into chosen ASGI framework. Resolves PY-CR-03, PY-CR-04, SC-09, SC-10.
3. **Observability (weeks 5-6).** Land RP-TEL (idempotent `Telemetry.init/shutdown` + propagators), RP-WRAP (`wrap()` classifier), RP-RESULT (`AppResult[T]`). Wire OTLP exporter env-driven. Add bound-cardinality Prometheus labels. Resolves OB-02..OB-04, ER-03, SC-15.
4. **Concurrency cleanup (weeks 7-8).** Replace `gather` w/o `return_exceptions=True`, audit `_cleanup_task` refs, replace `threading.Lock` with `asyncio.Lock` in async hot paths. Add task-cancellation tests. Resolves CC-02..CC-09.

**Exit criteria:** All 60 PY-HI items closed (or downgraded with rationale); RP sketches landed; mypy still strict; new APIs documented in per-pkg READMEs.

### v1.0 — Stabilisation (target: 4 weeks following v0.y)
**Goal:** earn the v1.0 SemVer commitment.

1. **Performance baseline.** Land `pytest-benchmark` harness (RP-BENCH) + bench job (§ 5.1). Capture baseline in `bench/baseline.json`. Resolves PF-01.
2. **Fuzz adoption.** Land `fuzz.yml` (§ 5.3) + 1 fuzz target per parser/auth surface. Resolves SC-12 follow-ups.
3. **Docs site.** mkdocs-material scaffold; per-pkg README from template; ARCHITECTURE.md; release-process doc. Resolves DOC tier.
4. **PyPI Trusted Publishing.** Configure environment + first release of all 55 packages (or a single `pykit` umbrella, per § 8 decision). Resolves REL-02, REL-03.
5. **All 53 Med + 19 Low + 1 Nit** triaged, fixed, or explicitly deferred with issue links.

**Exit criteria:** v1.0 tag on every published package; signed releases; SBOM attached; cross-OS CI matrix green for 14 consecutive days; perf baseline established and CI-gated within ±10%.

---

## § 8 Open questions

1. **Monorepo release strategy.** Per-package SemVer tags (`pykit-http-v1.2.0`) — independent versioning, painful for users juggling 55 versions — *or* unified umbrella version (`v1.0.0` ships all 55) — simple but couples release cadence. Recommend: **per-package** tags + a thin `pykit` meta-package that pins compatible-set ranges (à la `aws-cdk-lib`).
2. **Python floor.** Floor at 3.13 (current) excludes Debian stable / Ubuntu 24.04 LTS shipping 3.12 — would users accept that at v1.0? Recommend: **floor at 3.12** for v1.0; gain `match` + `Self` + tagged unions, lose only PEP 695 generic-syntax-only sugar.
3. **HTTP framework.** FastAPI (batteries) vs Starlette (lean) vs framework-agnostic ASGI helpers. Recommend: **Starlette** + `pykit-asgi` middleware bundle; FastAPI adds an opinion that fights pykit's own validation/DI layers.
4. **gRPC TLS path.** Current `add_insecure_port` only — what's the v1.0 secure default? Recommend: **mTLS-by-default** with `add_insecure_port` requiring explicit `allow_insecure=True`.
5. **Deprecation timeline.** How many minor versions of warning before removal? Recommend: **2 minor versions or 6 months**, whichever is longer; document in `DEPRECATIONS.md`.
6. **gokit / pykit / rskit shared discipline.** Should there be a top-level meta-repo (`kit-policy`) that owns SECURITY.md, dependabot.yml, release-please config templates? Recommend: **yes**, single source of truth for the three perimeters.

---

## § 9 Final verdict

### **NOT READY for v1.0.**

**Severity counts:** 11 Critical · 60 High · 53 Medium · 19 Low · 1 Nit (**144 total**).

**Top-5 blockers — all must be resolved before any v1.0 candidate tag:**

1. **PY-CR-02 — Architecture contract is broken at HEAD.** `import-linter` is configured but only enumerates 39/55 packages; the layered contract has no actual force. Until the contract is exhaustive *and* CI-enforced, the architecture is documentation-theatre.
2. **PY-CR-01 — Type discipline is broken.** `mypy --strict` runs on 5/55 packages and crashes on a duplicated test file in the remainder. The type annotations across the library cannot be trusted because they have never been globally checked.
3. **PY-CR-08 — Tests are red.** 10 failures in `pykit-discovery` (`DiscoveryComponent` ctor drift). A library that ships failing tests against its own HEAD does not ship.
4. **PY-CR-03/04/05 — No auth, no health, no HTTP perimeter.** No OIDC verifier; no `AuthMiddleware`; no `/healthz`. Every consumer has to roll their own — which means there is no shared *kit* to speak of for HTTP services.
5. **PY-CR-09 / PY-CR-06 / PY-CR-07 / PY-CR-10 — Supply chain is unmanaged.** `uv.lock` is gitignored; nothing has ever been released; no security CI gate; 5 live CVEs sit in the resolved tree. None of those four are individually fatal — collectively they are.

**Wins worth preserving** as redesigns land:
- Tooling *choices* are correct: uv + hatch + ruff + mypy + import-linter is the modern stack.
- Crypto choices are correct: `hmac.compare_digest`, AES-GCM with random nonce, bcrypt 5, no pickle/yaml.load/shell=True in core.
- Async-first I/O posture is consistent (with localised exceptions to clean up).
- 88/88 `# type: ignore` are scoped — not blanket — which means tightening mypy will surface real issues, not false positives.
- 90.81% global coverage is the highest of the three sibling kits; the gate just needs to follow the reality.

**Path to v1.0** is well-defined: ship § 7's v0.x cleanup (4 wks) + v0.y redesigns (8 wks) + v1.0 stabilisation (4 wks) = **16-week roadmap from a competent dedicated maintainer**. None of the blockers requires research or invention — every redesign sketch in § 4 is compileable Python today.

— end of review —
