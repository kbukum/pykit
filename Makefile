.PHONY: all build test test-coverage lint typecheck fmt fmt-check sync update check clean help \
       ci ci-test ci-lint ensure-act

# Package flag: pass package name when P is set
_P = $(if $(P),packages/$(P))

# Test filter: pass -k $(T) when T is set
_T = $(if $(T),-k $(T))

## Default target
all: check

## Build packages (P=<package> for specific)
build:
	@echo "==> Building..."
ifdef P
	@cd $(P) && uv build
else
	@for pkg in packages/*/; do \
		echo "==> Building $${pkg}..."; \
		cd "$${pkg}" && uv build || exit 1; \
		cd - > /dev/null; \
	done
endif
	@echo "✓ Build succeeded"

## Run tests (P=<package>, T=<test pattern>)
test:
	@echo "==> Testing..."
	@uv run python -m pytest $(if $(P),packages/$(P)/tests/) $(_T)
	@echo "✓ Tests passed"

## Run tests with coverage (P=<package>, T=<test pattern>)
test-coverage:
	@echo "==> Testing with coverage..."
	@uv run python -m pytest --cov --cov-report=term-missing $(if $(P),packages/$(P)/tests/) $(_T)
	@echo "✓ Coverage report generated"

## Run linter (P=<package>)
lint:
	@echo "==> Linting..."
	@uv run ruff check $(if $(P),packages/$(P)/,.)
	@echo "✓ Lint passed"

## Run type checker (P=<package>)
typecheck:
	@echo "==> Type checking..."
	@uv run mypy $(if $(P),packages/$(P)/src/,.)
	@echo "✓ Type check passed"

## Format code with ruff
fmt:
	@echo "==> Formatting..."
	@uv run ruff format .
	@uv run ruff check --fix .
	@echo "✓ Formatted"

## Check formatting without modifying files
fmt-check:
	@echo "==> Checking format..."
	@uv run ruff format --check .
	@uv run ruff check .
	@echo "✓ Format OK"

## Sync dependencies
sync:
	@echo "==> Syncing dependencies..."
	@uv sync
	@echo "✓ Dependencies synced"

## Update lockfile
update:
	@echo "==> Updating lockfile..."
	@uv lock --upgrade
	@echo "✓ Lockfile updated"

## Run all checks (fmt-check + lint + typecheck + test)
check: fmt-check lint typecheck test

## Clean build artifacts and caches
clean:
	@echo "==> Cleaning..."
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	@rm -f .coverage
	@echo "✓ Cleaned"

## Ensure act is installed (for local CI)
ensure-act:
	@command -v act >/dev/null 2>&1 || { \
		echo "==> act not found. Install from https://github.com/nektos/act"; \
		exit 1; \
	}
	@command -v docker >/dev/null 2>&1 || { echo "Error: Docker is required but not installed." && exit 1; }

## Run full CI pipeline locally (mirrors GitHub Actions)
ci: ensure-act
	@act --secret GITHUB_TOKEN=$$(gh auth token 2>/dev/null) $(ACT_ARGS)

## Run only the test job from CI
ci-test: ensure-act
	@act -j test --secret GITHUB_TOKEN=$$(gh auth token 2>/dev/null) $(ACT_ARGS)

## Run only the lint job from CI
ci-lint: ensure-act
	@act -j lint --secret GITHUB_TOKEN=$$(gh auth token 2>/dev/null) $(ACT_ARGS)

## Show help
help:
	@echo "Usage: make <target> [P=<package>] [T=<test>]"
	@echo ""
	@echo "Development:"
	@echo "  make build              [P=]       Build packages"
	@echo "  make test               [P=] [T=]  Run tests"
	@echo "  make test-coverage      [P=] [T=]  Run tests with coverage"
	@echo "  make lint               [P=]       Run ruff check"
	@echo "  make typecheck          [P=]       Run mypy"
	@echo "  make fmt                            Format code"
	@echo "  make fmt-check                      Check formatting"
	@echo "  make sync                           Sync dependencies"
	@echo "  make update                         Update lockfile"
	@echo "  make check              [P=]       fmt-check + lint + typecheck + test"
	@echo "  make clean                          Remove build artifacts"
	@echo ""
	@echo "Local CI (GitHub Actions via act + Docker):"
	@echo "  make ci                             Run full CI pipeline"
	@echo "  make ci-test                        Run only test job"
	@echo "  make ci-lint                        Run only lint job"
	@echo ""
	@echo "Package targeting (P=):"
	@echo "  P=pykit                 Target pykit package"
	@echo "  P=pykit-auth            Target pykit-auth package"
	@echo "  P=pykit-database        Target pykit-database package"
	@echo "  P=pykit-messaging       Target pykit-messaging package"
	@echo "  P=pykit-discovery       Target pykit-discovery package"
	@echo ""
	@echo "Examples:"
	@echo "  make test                           Test everything"
	@echo "  make test P=pykit-auth              Test auth package"
	@echo "  make test P=pykit-auth T=test_jwt   Test matching tests in auth"
	@echo "  make lint P=pykit-database          Lint database package"
	@echo "  make check P=pykit-messaging        Full check on messaging package"
	@echo "  make test-coverage                  Coverage report for all packages"
	@echo "  make fmt                            Format all code"
	@echo "  make typecheck P=pykit              Type check pykit package"
