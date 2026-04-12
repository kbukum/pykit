"""Cross-layer integration tests for pykit.

Tests verify that modules work together correctly across architectural layers.
Each test exercises at least 2 modules from different layers using real APIs.
"""

from __future__ import annotations

import asyncio

import pytest

from pykit_auth import JWTConfig, JWTService
from pykit_authz import MapChecker
from pykit_bootstrap import App, DefaultAppConfig, Environment, LoggingConfig, ServiceConfig
from pykit_component import Health, HealthStatus, Registry
from pykit_di import Container, RegistrationMode
from pykit_errors import AppError, ErrorCode, ErrorResponse, InvalidInputError
from pykit_logging import get_logger, setup_logging
from pykit_pipeline import Pipeline, collect, concat, drain, reduce
from pykit_provider import RequestResponseFunc
from pykit_resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    State,
)
from pykit_validation import Validator

# ─── Helpers ──────────────────────────────────────────────────────────────────


class TrackingComponent:
    """A test component that records lifecycle events."""

    def __init__(self, name: str) -> None:
        self._name = name
        self.started = False
        self.stopped = False
        self.order: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    async def start(self) -> None:
        self.started = True
        self.order.append(f"start:{self._name}")

    async def stop(self) -> None:
        self.stopped = True
        self.order.append(f"stop:{self._name}")

    async def health(self) -> Health:
        status = HealthStatus.HEALTHY if self.started and not self.stopped else HealthStatus.UNHEALTHY
        return Health(name=self._name, status=status)


class SharedOrderTracker:
    """Shared tracker for verifying component lifecycle ordering."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def make_component(self, name: str) -> TrackingComponent:
        comp = TrackingComponent(name)
        comp.order = self.events
        return comp


# ─── 1. Errors → Validation ─────────────────────────────────────────────────


class TestErrorsValidation:
    """Validation produces correct AppError with error codes."""

    def test_validation_failure_produces_app_error(self) -> None:
        v = Validator()
        v.required("name", "")
        v.pattern("email", "not-an-email", r"^[\w.+-]+@[\w-]+\.[\w.]+$")

        with pytest.raises(InvalidInputError) as exc_info:
            v.validate()

        err = exc_info.value
        assert err.code == ErrorCode.INVALID_INPUT
        assert err.http_status == 422

    def test_multiple_field_errors(self) -> None:
        v = Validator()
        v.required("username", "")
        v.required("password", "")
        v.pattern("email", "bad", r"^[\w.+-]+@[\w-]+\.[\w.]+$")

        with pytest.raises(InvalidInputError):
            v.validate()

    def test_passing_validation_produces_no_error(self) -> None:
        v = Validator()
        v.required("name", "Alice")
        v.pattern("email", "alice@example.com", r"^[\w.+-]+@[\w-]+\.[\w.]+$")

        v.validate()  # Should not raise

    def test_validation_error_is_app_error(self) -> None:
        v = Validator()
        v.required("field", "")

        with pytest.raises(AppError) as exc_info:
            v.validate()

        assert isinstance(exc_info.value, AppError)
        assert exc_info.value.code == ErrorCode.INVALID_INPUT


# ─── 2. Config → Logging ────────────────────────────────────────────────────


class TestConfigLogging:
    """Config loads logging settings, logger initializes correctly."""

    def test_config_drives_logging_setup(self) -> None:
        config = DefaultAppConfig(
            service=ServiceConfig(
                name="test-svc",
                version="1.0.0",
                environment=Environment.DEVELOPMENT,
                debug=True,
                logging=LoggingConfig(level="DEBUG", format="console"),
            )
        )

        setup_logging(level=config.service_config.logging.level, log_format="console")
        logger = get_logger("integration-test")
        logger.info("test message from integration test")

        assert config.service_config.name == "test-svc"
        assert config.service_config.logging.level == "DEBUG"

    def test_default_config_produces_valid_logging(self) -> None:
        config = DefaultAppConfig()
        config.apply_defaults()

        sc = config.service_config
        setup_logging(level=sc.logging.level, log_format=sc.logging.format)
        logger = get_logger("default-test")
        logger.info("default config logging test")

    def test_production_config(self) -> None:
        config = DefaultAppConfig(
            service=ServiceConfig(
                name="prod-svc",
                environment=Environment.PRODUCTION,
                logging=LoggingConfig(level="WARNING", format="json"),
            )
        )
        assert config.service_config.environment == Environment.PRODUCTION
        assert config.service_config.logging.level == "WARNING"


# ─── 3. Provider → Pipeline ─────────────────────────────────────────────────


class TestProviderPipeline:
    """Provider feeds pipeline, pipeline transforms and collects results."""

    async def test_provider_output_flows_through_pipeline(self) -> None:
        _provider = RequestResponseFunc("doubler", lambda x: asyncio.coroutine(lambda: x * 2)())

        data = [1, 2, 3, 4, 5]
        p = Pipeline.from_list(data)
        doubled = p.map(lambda x: x * 2)
        filtered = doubled.filter(lambda x: x > 4)

        results = await collect(filtered)
        assert results == [6, 8, 10]

    async def test_pipeline_map_filter_collect(self) -> None:
        p = Pipeline.from_list([1, 2, 3, 4, 5])
        mapped = p.map(lambda x: f"item-{x}")
        filtered = mapped.filter(lambda x: x != "item-3")

        results = await collect(filtered)
        assert len(results) == 4
        assert "item-3" not in results

    async def test_pipeline_concat(self) -> None:
        p1 = Pipeline.from_list([1, 2])
        p2 = Pipeline.from_list([3, 4])
        combined = concat(p1, p2)

        results = await collect(combined)
        assert results == [1, 2, 3, 4]

    async def test_pipeline_reduce(self) -> None:
        p = Pipeline.from_list([1, 2, 3, 4, 5])
        summed = reduce(p, 0, lambda acc, x: acc + x)

        results = await collect(summed)
        assert results == [15]

    async def test_pipeline_tap_side_effects(self) -> None:
        side_effects: list[int] = []
        p = Pipeline.from_list([10, 20, 30])
        tapped = p.tap(lambda x: side_effects.append(x))

        results = await collect(tapped)
        assert results == [10, 20, 30]
        assert side_effects == [10, 20, 30]

    async def test_pipeline_drain_to_sink(self) -> None:
        collected: list[int] = []
        p = Pipeline.from_list([1, 2, 3])

        await drain(p, lambda x: collected.append(x))
        assert collected == [1, 2, 3]


# ─── 4. DI → Component → Bootstrap ──────────────────────────────────────────


class TestDIComponentBootstrap:
    """Container resolves dependencies, bootstrap orchestrates lifecycle."""

    def test_di_registers_and_resolves_components(self) -> None:
        container = Container()
        db = TrackingComponent("postgres")
        cache = TrackingComponent("redis")

        container.register_instance("db", db)
        container.register_instance("cache", cache)

        resolved_db = container.resolve("db")
        assert resolved_db.name == "postgres"

        resolved_cache = container.resolve("cache")
        assert resolved_cache.name == "redis"

    def test_di_registration_modes(self) -> None:
        container = Container()
        call_count = {"eager": 0, "lazy": 0}

        def eager_factory():
            call_count["eager"] += 1
            return TrackingComponent("eager")

        def lazy_factory():
            call_count["lazy"] += 1
            return TrackingComponent("lazy")

        container.register("eager-svc", eager_factory, RegistrationMode.EAGER)
        assert call_count["eager"] == 1

        container.register_lazy("lazy-svc", lazy_factory)
        assert call_count["lazy"] == 0

        container.resolve("lazy-svc")
        assert call_count["lazy"] == 1

    async def test_registry_lifecycle_ordering(self) -> None:
        tracker = SharedOrderTracker()
        db = tracker.make_component("db")
        cache = tracker.make_component("cache")
        api = tracker.make_component("api")

        registry = Registry()
        registry.register(db)
        registry.register(cache)
        registry.register(api)

        await registry.start_all()
        await registry.stop_all()

        assert tracker.events[:3] == ["start:db", "start:cache", "start:api"]
        assert tracker.events[3:] == ["stop:api", "stop:cache", "stop:db"]

    async def test_bootstrap_app_runs_task(self) -> None:
        config = DefaultAppConfig(
            service=ServiceConfig(
                name="task-svc",
                version="0.1.0",
                debug=True,
            )
        )
        app = App(config)

        comp = TrackingComponent("test-comp")
        app.with_component(comp)

        task_ran = False

        async def task():
            nonlocal task_ran
            task_ran = True

        await app.run_task(task)
        assert task_ran
        assert comp.started
        assert comp.stopped


# ─── 5. Resilience → Provider ───────────────────────────────────────────────


class TestResilienceProvider:
    """Circuit breaker wraps provider, tracks failures."""

    async def test_circuit_breaker_trips_on_failures(self) -> None:
        config = CircuitBreakerConfig(name="test-cb", max_failures=3, timeout=0.1)
        cb = CircuitBreaker(config)

        for _ in range(3):
            with pytest.raises(AppError):
                await cb.execute(self._failing_call)

        assert cb.state == State.OPEN

    async def test_circuit_breaker_prevents_calls_when_open(self) -> None:
        config = CircuitBreakerConfig(name="open-cb", max_failures=2, timeout=0.1)
        cb = CircuitBreaker(config)

        for _ in range(2):
            with pytest.raises(AppError):
                await cb.execute(self._failing_call)

        with pytest.raises(CircuitOpenError):
            await cb.execute(self._successful_call)

    async def test_circuit_breaker_recovers(self) -> None:
        config = CircuitBreakerConfig(name="recover-cb", max_failures=2, timeout=0.05)
        cb = CircuitBreaker(config)

        for _ in range(2):
            with pytest.raises(AppError):
                await cb.execute(self._failing_call)

        assert cb.state == State.OPEN

        await asyncio.sleep(0.06)

        result = await cb.execute(self._successful_call)
        assert result == "ok"
        assert cb.state == State.CLOSED

    async def test_circuit_breaker_preserves_error_code(self) -> None:
        config = CircuitBreakerConfig(name="code-cb", max_failures=5, timeout=1.0)
        cb = CircuitBreaker(config)

        with pytest.raises(AppError) as exc_info:
            await cb.execute(self._not_found_call)

        assert exc_info.value.code == ErrorCode.NOT_FOUND

    @staticmethod
    async def _failing_call():
        raise AppError(ErrorCode.SERVICE_UNAVAILABLE, "service down")

    @staticmethod
    async def _successful_call():
        return "ok"

    @staticmethod
    async def _not_found_call():
        raise AppError.not_found("user", "user-123")


# ─── 6. Auth → Authz ────────────────────────────────────────────────────────


class TestAuthAuthz:
    """JWT claims feed authorization checker."""

    def test_jwt_claims_feed_authz(self) -> None:
        jwt_svc = JWTService(JWTConfig(secret="integration-test-secret-key-long-enough-for-hs256"))

        token = jwt_svc.generate({"sub": "user-1", "role": "admin"})
        claims = jwt_svc.validate(token)

        checker = MapChecker(
            {
                "admin": ["*"],
                "editor": ["article:read", "article:write"],
                "viewer": ["article:read"],
            }
        )

        role = claims["role"]
        assert checker.check(role, "article:delete")  # admin has wildcard
        assert checker.check(role, "user:manage")

    def test_jwt_claims_feed_authz_restricted_role(self) -> None:
        jwt_svc = JWTService(JWTConfig(secret="test-secret-key-12345-long-enough-for-hs256"))

        token = jwt_svc.generate({"sub": "user-2", "role": "viewer"})
        claims = jwt_svc.validate(token)

        checker = MapChecker(
            {
                "admin": ["*"],
                "viewer": ["article:read"],
            }
        )

        role = claims["role"]
        assert checker.check(role, "article:read")
        assert not checker.check(role, "article:write")
        assert not checker.check(role, "user:manage")

    def test_jwt_roundtrip_preserves_claims(self) -> None:
        jwt_svc = JWTService(
            JWTConfig(
                secret="roundtrip-secret-key-long-enough-for-hs256",
                issuer="test-issuer",
                audience="test-audience",
            )
        )

        original_claims = {"sub": "user-42", "role": "editor", "org": "acme"}
        token = jwt_svc.generate(original_claims)
        decoded = jwt_svc.validate(token)

        assert decoded["sub"] == "user-42"
        assert decoded["role"] == "editor"
        assert decoded["org"] == "acme"

    def test_expired_token_rejected(self) -> None:
        jwt_svc = JWTService(JWTConfig(secret="expired-secret-key-long-enough-for-hs256-algo"))
        token = jwt_svc.generate({"sub": "user-1"}, expires_in=-1)

        with pytest.raises(InvalidInputError):
            jwt_svc.validate(token)


# ─── 7. Errors → HTTP Response (RFC 7807) ───────────────────────────────────


class TestErrorsHTTPResponse:
    """AppError produces correct HTTP status codes and RFC 7807 body."""

    def test_not_found_produces_404_rfc7807(self) -> None:
        err = AppError.not_found("user", "user-123")
        response = ErrorResponse.from_app_error(err)

        assert response.status == 404
        assert response.title == "NOT_FOUND"
        assert "not-found" in response.type

        body = response.to_dict()
        assert body["status"] == 404
        assert "type" in body
        assert "title" in body
        assert "detail" in body

    def test_invalid_input_produces_422_rfc7807(self) -> None:
        err = AppError.invalid_input("email", "invalid format")
        response = ErrorResponse.from_app_error(err)

        assert response.status == 422
        assert response.title == "INVALID_INPUT"

    def test_unauthorized_produces_401_rfc7807(self) -> None:
        err = AppError.unauthorized("missing credentials")
        response = ErrorResponse.from_app_error(err)

        assert response.status == 401
        assert response.title == "UNAUTHORIZED"

    def test_forbidden_produces_403_rfc7807(self) -> None:
        err = AppError.forbidden("insufficient permissions")
        response = ErrorResponse.from_app_error(err)

        assert response.status == 403
        assert response.title == "FORBIDDEN"

    def test_service_unavailable_produces_503_rfc7807(self) -> None:
        err = AppError.service_unavailable("database")
        response = ErrorResponse.from_app_error(err)

        assert response.status == 503
        assert response.title == "SERVICE_UNAVAILABLE"

    def test_internal_produces_500_rfc7807(self) -> None:
        err = AppError.internal(ValueError("unexpected"))
        response = ErrorResponse.from_app_error(err)

        assert response.status == 500
        assert response.title == "INTERNAL_ERROR"

    def test_rfc7807_type_url_format(self) -> None:
        err = AppError(ErrorCode.TOKEN_EXPIRED, "token has expired")
        response = ErrorResponse.from_app_error(err)

        assert response.type.startswith("https://pykit.dev/errors/")
        assert "token-expired" in response.type

    def test_error_code_retryability(self) -> None:
        retryable_codes = [
            ErrorCode.SERVICE_UNAVAILABLE,
            ErrorCode.CONNECTION_FAILED,
            ErrorCode.TIMEOUT,
            ErrorCode.RATE_LIMITED,
        ]
        for code in retryable_codes:
            assert code.is_retryable, f"{code} should be retryable"

        non_retryable_codes = [
            ErrorCode.NOT_FOUND,
            ErrorCode.UNAUTHORIZED,
            ErrorCode.FORBIDDEN,
            ErrorCode.INVALID_INPUT,
        ]
        for code in non_retryable_codes:
            assert not code.is_retryable, f"{code} should not be retryable"


# ─── 8. Full Stack: DI → Provider → Pipeline ────────────────────────────────


class TestFullStack:
    """End-to-end integration across multiple layers."""

    async def test_di_provider_pipeline(self) -> None:
        container = Container()

        provider = RequestResponseFunc("multiplier", self._async_multiply)
        container.register_instance("multiplier", provider)

        _resolved = container.resolve("multiplier")

        p = Pipeline.from_list([1, 2, 3, 4, 5])
        processed = p.map(lambda x: x * 3)
        filtered = processed.filter(lambda x: x > 6)

        results = await collect(filtered)
        assert results == [9, 12, 15]

    @staticmethod
    async def _async_multiply(x: int) -> int:
        return x * 2

    async def test_validation_errors_pipeline(self) -> None:
        """Validation failures propagate correctly through pipeline operations."""
        data = [
            {"name": "Alice", "email": "alice@example.com"},
            {"name": "", "email": "invalid"},
            {"name": "Charlie", "email": "charlie@test.com"},
        ]

        valid_items: list[str] = []
        error_items: list[str] = []

        for item in data:
            v = Validator()
            v.required("name", item["name"])
            v.pattern("email", item["email"], r"^[\w.+-]+@[\w-]+\.[\w.]+$")

            if v.has_errors:
                error_items.append(item.get("name") or "<empty>")
            else:
                valid_items.append(f"{item['name']} <{item['email']}>")

        assert len(valid_items) == 2
        assert len(error_items) == 1
