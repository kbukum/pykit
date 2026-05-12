.PHONY: all build test test-coverage test-affected test-unit lint typecheck fmt fmt-check sync update check check-fast \
       check-core check-patterns check-crosscutting check-composition check-transport check-auth check-data check-ai \
       check-media check-infra clean help ci ci-test ci-lint ensure-act

_W = $(or $(W),both)
_T = $(if $(T),-k $(T))

all: check

build:
	@echo "==> Building..."; \
	set -e; \
	if [ -n "$(P)" ]; then \
		if [ -d "core/packages/$(P)" ]; then \
			cd "core/packages/$(P)" && uv build; \
		elif [ -d "contrib/$(P)" ]; then \
			cd "contrib/$(P)" && uv build; \
		else \
			echo "Package $(P) not found in core/packages/ or contrib/" >&2; exit 1; \
		fi; \
	else \
		if [ "$(_W)" = "core" ] || [ "$(_W)" = "both" ]; then \
			for pkg in core/packages/*/; do \
				echo "==> Building $${pkg}..."; \
				(cd "$${pkg}" && uv build) || exit 1; \
			done; \
		fi; \
		if [ "$(_W)" = "contrib" ] || [ "$(_W)" = "both" ]; then \
			for pkg in contrib/pykit-*/; do \
				echo "==> Building $${pkg}..."; \
				(cd "$${pkg}" && uv build) || exit 1; \
			done; \
		fi; \
	fi; \
	echo "✓ Build succeeded"

test:
	@echo "==> Testing..."; \
	set -e; \
	if [ -n "$(P)" ]; then \
		if [ -d "core/packages/$(P)" ]; then \
			cd core && uv run python -m pytest "packages/$(P)/tests/" $(_T); \
		elif [ -d "contrib/$(P)" ]; then \
			cd contrib && uv run python -m pytest "$(P)/tests/" $(_T); \
		else \
			echo "Package $(P) not found in core/packages/ or contrib/" >&2; exit 1; \
		fi; \
	else \
		if [ "$(_W)" = "core" ] || [ "$(_W)" = "both" ]; then (cd core && uv run python -m pytest $(_T)); fi; \
		if [ "$(_W)" = "contrib" ] || [ "$(_W)" = "both" ]; then (cd contrib && uv run python -m pytest $(_T)); fi; \
	fi; \
	echo "✓ Tests passed"

test-coverage:
	@echo "==> Testing with coverage..."; \
	set -e; \
	if [ -n "$(P)" ]; then \
		if [ -d "core/packages/$(P)" ]; then \
			cd core && uv run python -m pytest --cov --cov-report=term-missing "packages/$(P)/tests/" $(_T); \
		elif [ -d "contrib/$(P)" ]; then \
			cd contrib && uv run python -m pytest --cov --cov-report=term-missing "$(P)/tests/" $(_T); \
		else \
			echo "Package $(P) not found in core/packages/ or contrib/" >&2; exit 1; \
		fi; \
	else \
		if [ "$(_W)" = "core" ] || [ "$(_W)" = "both" ]; then (cd core && uv run python -m pytest --cov --cov-report=term-missing $(_T)); fi; \
		if [ "$(_W)" = "contrib" ] || [ "$(_W)" = "both" ]; then (cd contrib && uv run python -m pytest --cov --cov-report=term-missing $(_T)); fi; \
	fi; \
	echo "✓ Coverage report generated"

lint:
	@echo "==> Linting..."; \
	set -e; \
	if [ -n "$(P)" ]; then \
		if [ -d "core/packages/$(P)" ]; then \
			cd core && uv run ruff check "packages/$(P)/"; \
		elif [ -d "contrib/$(P)" ]; then \
			cd contrib && uv run ruff check "$(P)/"; \
		else \
			echo "Package $(P) not found in core/packages/ or contrib/" >&2; exit 1; \
		fi; \
	else \
		if [ "$(_W)" = "core" ] || [ "$(_W)" = "both" ]; then (cd core && uv run ruff check .); fi; \
		if [ "$(_W)" = "contrib" ] || [ "$(_W)" = "both" ]; then (cd contrib && uv run ruff check .); fi; \
	fi; \
	echo "✓ Lint passed"

typecheck:
	@echo "==> Type checking..."; \
	set -e; \
	if [ -n "$(P)" ]; then \
		if [ -d "core/packages/$(P)" ]; then \
			cd core && uv run mypy "packages/$(P)/src/"; \
		elif [ -d "contrib/$(P)" ]; then \
			cd contrib && uv run mypy "$(P)/src/"; \
		else \
			echo "Package $(P) not found in core/packages/ or contrib/" >&2; exit 1; \
		fi; \
	else \
		if [ "$(_W)" = "core" ] || [ "$(_W)" = "both" ]; then (cd core && uv run mypy); fi; \
		if [ "$(_W)" = "contrib" ] || [ "$(_W)" = "both" ]; then (cd contrib && uv run mypy); fi; \
	fi; \
	echo "✓ Type check passed"

fmt:
	@echo "==> Formatting..."; \
	set -e; \
	if [ -n "$(P)" ]; then \
		if [ -d "core/packages/$(P)" ]; then \
			cd core && uv run ruff format "packages/$(P)/" && uv run ruff check --fix "packages/$(P)/"; \
		elif [ -d "contrib/$(P)" ]; then \
			cd contrib && uv run ruff format "$(P)/" && uv run ruff check --fix "$(P)/"; \
		else \
			echo "Package $(P) not found in core/packages/ or contrib/" >&2; exit 1; \
		fi; \
	else \
		if [ "$(_W)" = "core" ] || [ "$(_W)" = "both" ]; then (cd core && uv run ruff format . && uv run ruff check --fix .); fi; \
		if [ "$(_W)" = "contrib" ] || [ "$(_W)" = "both" ]; then (cd contrib && uv run ruff format . && uv run ruff check --fix .); fi; \
	fi; \
	echo "✓ Formatted"

fmt-check:
	@echo "==> Checking format..."; \
	set -e; \
	if [ -n "$(P)" ]; then \
		if [ -d "core/packages/$(P)" ]; then \
			cd core && uv run ruff format --check "packages/$(P)/"; \
		elif [ -d "contrib/$(P)" ]; then \
			cd contrib && uv run ruff format --check "$(P)/"; \
		else \
			echo "Package $(P) not found in core/packages/ or contrib/" >&2; exit 1; \
		fi; \
	else \
		if [ "$(_W)" = "core" ] || [ "$(_W)" = "both" ]; then (cd core && uv run ruff format --check .); fi; \
		if [ "$(_W)" = "contrib" ] || [ "$(_W)" = "both" ]; then (cd contrib && uv run ruff format --check .); fi; \
	fi; \
	echo "✓ Format OK"

sync:
	@echo "==> Syncing dependencies..."; \
	set -e; \
	if [ "$(_W)" = "core" ] || [ "$(_W)" = "both" ]; then (cd core && uv sync); fi; \
	if [ "$(_W)" = "contrib" ] || [ "$(_W)" = "both" ]; then (cd contrib && uv sync); fi; \
	echo "✓ Dependencies synced"

update:
	@echo "==> Updating lockfile..."; \
	set -e; \
	if [ "$(_W)" = "core" ] || [ "$(_W)" = "both" ]; then (cd core && uv lock --upgrade); fi; \
	if [ "$(_W)" = "contrib" ] || [ "$(_W)" = "both" ]; then (cd contrib && uv lock --upgrade); fi; \
	echo "✓ Lockfile updated"

check: fmt-check lint typecheck test
check-core:
	@./scripts/check-domain.sh core
check-patterns:
	@./scripts/check-domain.sh patterns
check-crosscutting:
	@./scripts/check-domain.sh crosscutting
check-composition:
	@./scripts/check-domain.sh composition
check-transport:
	@./scripts/check-domain.sh transport
check-auth:
	@./scripts/check-domain.sh auth
check-data:
	@./scripts/check-domain.sh data
check-ai:
	@./scripts/check-domain.sh ai
check-media:
	@./scripts/check-domain.sh media
check-infra:
	@./scripts/check-domain.sh infra
check-fast: fmt-check lint typecheck

test-affected:
	@echo "==> Detecting affected packages..."; \
	set -e; \
	CHANGED=$$(git diff --name-only origin/main...HEAD 2>/dev/null || git diff --name-only HEAD~1); \
	if [ -z "$$CHANGED" ]; then \
		echo "No changes detected, running all tests"; \
		(cd core && uv run pytest); \
		(cd contrib && uv run pytest); \
	elif echo "$$CHANGED" | grep -qvE '^(core/packages/|contrib/)'; then \
		echo "Workspace/config files changed, running all tests"; \
		(cd core && uv run pytest); \
		(cd contrib && uv run pytest); \
	else \
		CORE_PKGS=$$(echo "$$CHANGED" | grep -E '^core/packages/' | cut -d/ -f3 | sort -u); \
		CONTRIB_PKGS=$$(echo "$$CHANGED" | grep -E '^contrib/' | cut -d/ -f2 | sort -u); \
		if [ -n "$$CORE_PKGS" ]; then \
			echo "Affected core packages: $$CORE_PKGS"; \
			PATHS=$$(echo "$$CORE_PKGS" | sed 's|^|packages/|' | tr '\n' ' '); \
			(cd core && uv run pytest $$PATHS); \
		fi; \
		if [ -n "$$CONTRIB_PKGS" ]; then \
			echo "Affected contrib packages: $$CONTRIB_PKGS"; \
			(cd contrib && uv run pytest $$CONTRIB_PKGS); \
		fi; \
		if [ -z "$$CORE_PKGS" ] && [ -z "$$CONTRIB_PKGS" ]; then \
			echo "No package changes detected"; \
		fi; \
	fi

test-unit:
	@cd core && uv run pytest -m "not integration and not e2e and not benchmark" -n auto --dist worksteal

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

ensure-act:
	@command -v act >/dev/null 2>&1 || { echo "==> act not found. Install from https://github.com/nektos/act"; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo "Error: Docker is required but not installed." && exit 1; }

ci: ensure-act
	@act --secret GITHUB_TOKEN=$$(gh auth token 2>/dev/null) $(ACT_ARGS)
ci-test: ensure-act
	@act -j test --secret GITHUB_TOKEN=$$(gh auth token 2>/dev/null) $(ACT_ARGS)
ci-lint: ensure-act
	@act -j lint --secret GITHUB_TOKEN=$$(gh auth token 2>/dev/null) $(ACT_ARGS)

help:
	@echo "Usage: make <target> [P=<package>] [T=<test>] [W=core|contrib|both]"
	@echo ""
	@echo "Development:"
	@echo "  make help                             Show this help"
	@echo "  make build                [P=] [W=]  Build packages"
	@echo "  make test                 [P=] [T=]  Run tests"
	@echo "  make test-coverage        [P=] [T=]  Run tests with coverage"
	@echo "  make test-affected                    Run tests for changed packages"
	@echo "  make test-unit                        Run fast tests (core workspace)"
	@echo "  make lint                 [P=] [W=]  Run ruff check"
	@echo "  make typecheck            [P=] [W=]  Run mypy"
	@echo "  make fmt                  [P=] [W=]  Format code"
	@echo "  make fmt-check            [P=] [W=]  Check formatting"
	@echo "  make sync                      [W=]  Sync dependencies"
	@echo "  make update                    [W=]  Update lockfile"
	@echo "  make check-fast                       fmt-check + lint + typecheck"
	@echo "  make check                [P=] [W=]  fmt-check + lint + typecheck + test"
	@echo "  make clean                           Remove build artifacts"
	@echo ""
	@echo "Workspace targeting (W=):"
	@echo "  W=core                               Target only core workspace"
	@echo "  W=contrib                            Target only contrib workspace"
	@echo "  W=both                               Target both workspaces (default)"
	@echo ""
	@echo "Package targeting (P=):"
	@echo "  P=pykit                              Target core facade package"
	@echo "  P=pykit-auth                         Target core auth package"
	@echo "  P=pykit-database                     Target core database package"
	@echo "  P=pykit-messaging-kafka              Target contrib Kafka adapter"
	@echo "  P=pykit-storage-s3                   Target contrib S3 adapter"
	@echo ""
	@echo "Examples:"
	@echo "  make test                             Test both workspaces"
	@echo "  make test W=core                      Test core workspace only"
	@echo "  make test P=pykit-auth T=test_jwt     Test matching tests in core auth"
	@echo "  make lint P=pykit-storage-s3          Lint contrib storage adapter"
	@echo "  make check P=pykit-messaging-kafka    Full check on contrib Kafka adapter"
	@echo "  make sync W=contrib                   Sync contrib dependencies"
	@echo "  make typecheck P=pykit                Type check core facade package"
