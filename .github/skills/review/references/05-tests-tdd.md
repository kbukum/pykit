# Pass 05 — Tests & TDD

Behavior is only real if a test proves it. Vibe-coded changes routinely ship without tests, or
with tests that assert implementation detail instead of behavior. This pass verifies the change
is covered, deterministic, and clean under the configured pytest gates.

> **Run in a separate, clean-context agent** — never inline in the session that wrote the code.
> An independent reviewer re-derives every judgment from the code and the principles instead of
> trusting prior reasoning. A plan/spec may be passed in as a scope checklist only; it never
> excuses a baseline violation.

**Scope note.** *Changes mode:* every behavioral change in the diff has a test in the same
change; every bug fix has a regression test. *Project mode:* assess coverage against the gates
and hunt for flaky/implementation-coupled tests across the suite.

## Checks

- **Tests ship with the change.** New/changed behavior has tests in the same change set; a bug fix
  has a regression test that fails without the fix. Behavior added with no test is a **blocker**.
- **Behavioral, not implementation-coupled.** Tests assert observable behavior and public
  contracts, not private field values or call sequences that would break on a harmless refactor.
- **Deterministic.** Clocks are **injected** (never `time.sleep` or arbitrary `asyncio.sleep` to
  "wait" for async work), RNG is **seeded**, no real network / filesystem in unit tests (use fakes,
  monkeypatching, `tmp_path`, and test utilities). A test that sleeps or hits the network is a
  should-fix.
- **Parallel/random-order clean.** Suite passes under configured pytest parallel/random-order
  tooling (`pytest -n auto` via xdist and `pytest-randomly` if configured). Tests are independent:
  no shared mutable module state, cwd dependence, or environment leakage.
- **Coverage gate.** pykit's minimum is **60%** via `uv run pytest --cov` / `make test-coverage`.
  A change that drops a package below the configured floor is a blocker.
- **Property/fuzz where it matters.** Parsers, validators, auth/JWT, codecs, and schema have
  property-based or fuzz-style tests where appropriate. A new parser/validator with no adversarial
  coverage is a should-fix.
- **Environment-independent.** Tests use `monkeypatch.setenv` / `monkeypatch.chdir` rather than
  mutating global env/cwd permanently; no ordering dependency between tests.

## Detection starters

```bash
# behavior touched vs tests touched (changes mode)
git diff --name-only | grep '\.py$' | grep -v '/tests/'       # source changed
git diff --name-only | grep '/tests/.*\.py$'                  # tests changed — should be non-empty
# non-deterministic / external-dependency smells in tests
rg -n 'time\.sleep|asyncio\.sleep|datetime\.now|date\.today|httpx\.|requests\.|socket\.|random\.' . -g '*test*.py'
# env/cwd mutation without monkeypatch
rg -n 'os\.environ\[|os\.putenv|os\.chdir|Path\.cwd\(' . -g '*test*.py'
# missing property/fuzz hints on parser/validator/codec/auth/schema packages
rg -L 'hypothesis|given\(|parametrize|fuzz' core/packages/pykit-{auth,validation,schema}/tests contrib/*/tests 2>/dev/null
```

## Validation gate

Run the scoped suite for the touched package/domain:

```bash
make test-affected                      # only affected packages (fast inner loop)
make test P=<package> T=<pattern>       # one package, optionally narrowed by pytest -k
make test-unit                          # fast core unit tests with xdist
make test-coverage P=<package>          # coverage report for the touched package
make check-<domain>                     # domain gate for the touched area
```

A behavioral change with a green scoped pytest run and coverage above the gate passes; anything
untested, sleeping, externally dependent, or below the coverage floor does not.
