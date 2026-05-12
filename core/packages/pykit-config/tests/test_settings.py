"""Tests for pykit_config.settings — BaseSettings defaults, env detection, field access."""

from __future__ import annotations

import pytest

from pykit_config import BaseSettings


class TestDefaults:
    """Verify every default value and its type."""

    def test_service_name(self) -> None:
        assert BaseSettings().service_name == "pykit-service"

    def test_environment(self) -> None:
        assert BaseSettings().environment == "development"

    def test_service_address(self) -> None:
        assert BaseSettings().service_address == "0.0.0.0"

    def test_service_port(self) -> None:
        assert BaseSettings().service_port == 50051

    def test_log_level(self) -> None:
        assert BaseSettings().log_level == "INFO"

    def test_log_format(self) -> None:
        assert BaseSettings().log_format == "auto"

    def test_metrics_port(self) -> None:
        assert BaseSettings().metrics_port == 9090

    def test_metrics_enabled(self) -> None:
        assert BaseSettings().metrics_enabled is True

    def test_field_types(self) -> None:
        s = BaseSettings()
        assert isinstance(s.service_name, str)
        assert isinstance(s.environment, str)
        assert isinstance(s.service_address, str)
        assert isinstance(s.service_port, int)
        assert isinstance(s.log_level, str)
        assert isinstance(s.log_format, str)
        assert isinstance(s.metrics_port, int)
        assert isinstance(s.metrics_enabled, bool)


class TestEnvironmentDetection:
    """is_production / is_development properties."""

    def test_default_is_development(self) -> None:
        s = BaseSettings()
        assert s.is_development is True
        assert s.is_production is False

    def test_production(self) -> None:
        s = BaseSettings(environment="production")
        assert s.is_production is True
        assert s.is_development is False

    def test_staging_is_neither(self) -> None:
        s = BaseSettings(environment="staging")
        assert s.is_development is False
        assert s.is_production is False


class TestEnvOverride:
    """Each field can be overridden via env var."""

    def test_service_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SERVICE_NAME", "overridden")
        assert BaseSettings().service_name == "overridden"

    def test_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "production")
        s = BaseSettings()
        assert s.environment == "production"
        assert s.is_production is True

    def test_service_address(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SERVICE_ADDRESS", "127.0.0.1")
        assert BaseSettings().service_address == "127.0.0.1"

    def test_service_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SERVICE_PORT", "8080")
        s = BaseSettings()
        assert s.service_port == 8080
        assert isinstance(s.service_port, int)

    def test_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        assert BaseSettings().log_level == "DEBUG"

    def test_log_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_FORMAT", "json")
        assert BaseSettings().log_format == "json"

    def test_metrics_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("METRICS_PORT", "9191")
        assert BaseSettings().metrics_port == 9191

    def test_metrics_enabled_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("METRICS_ENABLED", "false")
        assert BaseSettings().metrics_enabled is False


class TestSubclassing:
    """Custom settings that extend BaseSettings."""

    def test_custom_fields_with_defaults(self) -> None:
        class AppSettings(BaseSettings):
            db_host: str = "localhost"
            db_port: int = 5432

        s = AppSettings()
        assert s.db_host == "localhost"
        assert s.db_port == 5432
        assert s.service_name == "pykit-service"

    def test_custom_fields_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class AppSettings(BaseSettings):
            db_host: str = "localhost"

        monkeypatch.setenv("DB_HOST", "prod-db.example.com")
        assert AppSettings().db_host == "prod-db.example.com"

    def test_inherits_properties(self) -> None:
        class AppSettings(BaseSettings):
            custom: str = "val"

        s = AppSettings(environment="production")
        assert s.is_production is True

    def test_extra_fields_ignored(self) -> None:
        s = BaseSettings(unknown_key="whatever")
        assert not hasattr(s, "unknown_key")


class TestWithProfile:
    """BaseSettings.with_profile() class method."""

    def test_returns_instance(self) -> None:
        s = BaseSettings.with_profile("development")
        assert isinstance(s, BaseSettings)

    def test_accepts_kwargs(self) -> None:
        s = BaseSettings.with_profile("development", service_name="profiled")
        assert s.service_name == "profiled"

    def test_none_reads_environment_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "staging")
        s = BaseSettings.with_profile(None)
        assert isinstance(s, BaseSettings)


class TestModelConfig:
    """Pydantic model configuration checks."""

    def test_nested_delimiter(self) -> None:
        assert BaseSettings.model_config.get("env_nested_delimiter") == "__"

    def test_extra_ignore(self) -> None:
        assert BaseSettings.model_config.get("extra") == "ignore"

    def test_constructor_override(self) -> None:
        s = BaseSettings(service_name="ctor", service_port=1234, environment="staging")
        assert s.service_name == "ctor"
        assert s.service_port == 1234
        assert s.environment == "staging"
