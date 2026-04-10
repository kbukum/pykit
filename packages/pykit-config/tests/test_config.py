"""Tests for pykit.config.BaseSettings and load_config."""

from __future__ import annotations

import os
import tomllib

import pytest

from pykit_config import BaseSettings, load_config

# ---------------------------------------------------------------------------
# Original tests (preserved)
# ---------------------------------------------------------------------------


class TestBaseSettings:
    def test_defaults(self) -> None:
        settings = BaseSettings()
        assert settings.service_name == "pykit-service"
        assert settings.environment == "development"
        assert settings.host == "0.0.0.0"
        assert settings.port == 50051
        assert settings.log_level == "INFO"
        assert settings.metrics_port == 9090
        assert settings.metrics_enabled is True

    def test_is_development(self) -> None:
        settings = BaseSettings()
        assert settings.is_development is True
        assert settings.is_production is False

    def test_is_production(self) -> None:
        settings = BaseSettings(environment="production")
        assert settings.is_production is True
        assert settings.is_development is False

    def test_env_override(self, monkeypatch: object) -> None:
        os.environ["SERVICE_NAME"] = "test-service"
        os.environ["PORT"] = "8080"
        os.environ["ENVIRONMENT"] = "production"
        try:
            settings = BaseSettings()
            assert settings.service_name == "test-service"
            assert settings.port == 8080
            assert settings.is_production is True
        finally:
            del os.environ["SERVICE_NAME"]
            del os.environ["PORT"]
            del os.environ["ENVIRONMENT"]

    def test_subclass(self) -> None:
        class MySettings(BaseSettings):
            model_path: str = "/models/default"
            batch_size: int = 32

        settings = MySettings(service_name="my-service")
        assert settings.service_name == "my-service"
        assert settings.model_path == "/models/default"
        assert settings.batch_size == 32


# ---------------------------------------------------------------------------
# NEW — BaseSettings defaults (comprehensive)
# ---------------------------------------------------------------------------


class TestBaseSettingsDefaults:
    """Exhaustive verification of every default value and its type."""

    def test_all_default_values(self) -> None:
        settings = BaseSettings()
        assert settings.service_name == "pykit-service"
        assert settings.environment == "development"
        assert settings.host == "0.0.0.0"
        assert settings.port == 50051
        assert settings.log_level == "INFO"
        assert settings.log_format == "auto"
        assert settings.metrics_port == 9090
        assert settings.metrics_enabled is True

    def test_default_types(self) -> None:
        settings = BaseSettings()
        assert isinstance(settings.service_name, str)
        assert isinstance(settings.environment, str)
        assert isinstance(settings.host, str)
        assert isinstance(settings.port, int)
        assert isinstance(settings.log_level, str)
        assert isinstance(settings.log_format, str)
        assert isinstance(settings.metrics_port, int)
        assert isinstance(settings.metrics_enabled, bool)

    def test_is_production_default_false(self) -> None:
        assert BaseSettings().is_production is False

    def test_is_development_default_true(self) -> None:
        assert BaseSettings().is_development is True

    def test_staging_is_neither(self) -> None:
        settings = BaseSettings(environment="staging")
        assert settings.is_development is False
        assert settings.is_production is False

    def test_log_format_default(self) -> None:
        assert BaseSettings().log_format == "auto"


# ---------------------------------------------------------------------------
# NEW — env-var overrides (one test per field, using monkeypatch)
# ---------------------------------------------------------------------------


class TestBaseSettingsEnvOverride:
    """Each field can be overridden via env var (prefix='')."""

    def test_service_name(self, monkeypatch) -> None:
        monkeypatch.setenv("SERVICE_NAME", "overridden")
        assert BaseSettings().service_name == "overridden"

    def test_environment(self, monkeypatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "production")
        s = BaseSettings()
        assert s.environment == "production"
        assert s.is_production is True

    def test_host(self, monkeypatch) -> None:
        monkeypatch.setenv("HOST", "127.0.0.1")
        assert BaseSettings().host == "127.0.0.1"

    def test_port_string_to_int(self, monkeypatch) -> None:
        monkeypatch.setenv("PORT", "8080")
        s = BaseSettings()
        assert s.port == 8080
        assert isinstance(s.port, int)

    def test_log_level(self, monkeypatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        assert BaseSettings().log_level == "DEBUG"

    def test_log_format(self, monkeypatch) -> None:
        monkeypatch.setenv("LOG_FORMAT", "json")
        assert BaseSettings().log_format == "json"

    def test_metrics_port(self, monkeypatch) -> None:
        monkeypatch.setenv("METRICS_PORT", "9191")
        assert BaseSettings().metrics_port == 9191

    def test_metrics_enabled_false(self, monkeypatch) -> None:
        monkeypatch.setenv("METRICS_ENABLED", "false")
        assert BaseSettings().metrics_enabled is False

    def test_metrics_enabled_true(self, monkeypatch) -> None:
        monkeypatch.setenv("METRICS_ENABLED", "true")
        assert BaseSettings().metrics_enabled is True

    def test_metrics_enabled_zero(self, monkeypatch) -> None:
        monkeypatch.setenv("METRICS_ENABLED", "0")
        assert BaseSettings().metrics_enabled is False

    def test_metrics_enabled_one(self, monkeypatch) -> None:
        monkeypatch.setenv("METRICS_ENABLED", "1")
        assert BaseSettings().metrics_enabled is True

    def test_multiple_overrides_at_once(self, monkeypatch) -> None:
        monkeypatch.setenv("SERVICE_NAME", "multi")
        monkeypatch.setenv("PORT", "9999")
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        s = BaseSettings()
        assert s.service_name == "multi"
        assert s.port == 9999
        assert s.environment == "staging"
        assert s.log_level == "WARNING"


# ---------------------------------------------------------------------------
# NEW — load_config() tests (TOML loading, precedence, errors)
# ---------------------------------------------------------------------------


def _clean_app_env(monkeypatch):
    """Remove env vars that could interfere with load_config tests."""
    for key in list(os.environ):
        if key.startswith("APP_"):
            monkeypatch.delenv(key, raising=False)
    # Also clear bare env vars that pydantic-settings reads (prefix="")
    for bare in (
        "SERVICE_NAME",
        "ENVIRONMENT",
        "HOST",
        "PORT",
        "LOG_LEVEL",
        "LOG_FORMAT",
        "METRICS_PORT",
        "METRICS_ENABLED",
    ):
        monkeypatch.delenv(bare, raising=False)


class TestLoadConfigToml:
    """Tests for the load_config() loader."""

    def test_load_from_valid_toml(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text('service_name = "toml-service"\nport = 7070\n')
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "toml-service"
        assert s.port == 7070

    def test_load_from_custom_path(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        custom = tmp_path / "sub" / "app.toml"
        custom.parent.mkdir()
        custom.write_text('service_name = "custom-path"\n')
        s = load_config(BaseSettings, path=custom)
        assert s.service_name == "custom-path"

    def test_load_string_path(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text('service_name = "str-path"\n')
        s = load_config(BaseSettings, path=str(f))
        assert s.service_name == "str-path"

    def test_missing_toml_uses_defaults(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        s = load_config(BaseSettings, path=tmp_path / "nope.toml")
        assert s.service_name == "pykit-service"
        assert s.port == 50051

    def test_invalid_toml_raises_error(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "bad.toml"
        f.write_text("this is not [[[valid toml")
        with pytest.raises(tomllib.TOMLDecodeError):
            load_config(BaseSettings, path=f)

    def test_empty_toml_uses_defaults(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "empty.toml"
        f.write_text("")
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "pykit-service"
        assert s.port == 50051

    def test_toml_overrides_defaults(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text('environment = "production"\nlog_level = "ERROR"\nmetrics_enabled = false\n')
        s = load_config(BaseSettings, path=f)
        assert s.environment == "production"
        assert s.log_level == "ERROR"
        assert s.metrics_enabled is False
        # unset fields keep defaults
        assert s.service_name == "pykit-service"
        assert s.port == 50051

    def test_toml_all_fields(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text(
            'service_name = "full"\n'
            'environment = "staging"\n'
            'host = "10.0.0.1"\n'
            "port = 3000\n"
            'log_level = "WARNING"\n'
            'log_format = "json"\n'
            "metrics_port = 8888\n"
            "metrics_enabled = false\n"
        )
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "full"
        assert s.environment == "staging"
        assert s.host == "10.0.0.1"
        assert s.port == 3000
        assert s.log_level == "WARNING"
        assert s.log_format == "json"
        assert s.metrics_port == 8888
        assert s.metrics_enabled is False

    def test_app_env_overrides_toml(self, tmp_path, monkeypatch) -> None:
        """Precedence: defaults < TOML < APP_ env vars."""
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text('service_name = "toml-name"\nport = 7070\n')
        monkeypatch.setenv("APP_SERVICE_NAME", "env-name")
        monkeypatch.setenv("APP_PORT", "9999")
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "env-name"
        assert s.port == 9999

    def test_app_env_without_toml(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        monkeypatch.setenv("APP_SERVICE_NAME", "env-only")
        monkeypatch.setenv("APP_PORT", "1234")
        s = load_config(BaseSettings, path=tmp_path / "nope.toml")
        assert s.service_name == "env-only"
        assert s.port == 1234

    def test_default_path_is_config_toml(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.toml").write_text('service_name = "default-path"\n')
        s = load_config(BaseSettings)
        assert s.service_name == "default-path"

    def test_full_precedence(self, tmp_path, monkeypatch) -> None:
        """defaults < TOML < APP_ env vars — all three layers."""
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text('service_name = "toml"\nport = 7070\nlog_level = "WARNING"\n')
        # Override only service_name via APP_ env
        monkeypatch.setenv("APP_SERVICE_NAME", "env")
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "env"  # APP_ env > TOML
        assert s.port == 7070  # TOML > default
        assert s.log_level == "WARNING"  # TOML > default
        assert s.host == "0.0.0.0"  # default (nothing else set)


# ---------------------------------------------------------------------------
# NEW — Custom prefix (APP_CONFIG_PREFIX)
# ---------------------------------------------------------------------------


class TestLoadConfigCustomPrefix:
    """APP_CONFIG_PREFIX changes which env-var prefix load_config reads."""

    def test_custom_prefix(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        monkeypatch.setenv("APP_CONFIG_PREFIX", "MYAPP_")
        monkeypatch.setenv("MYAPP_SERVICE_NAME", "custom-prefix")
        s = load_config(BaseSettings, path=tmp_path / "nope.toml")
        assert s.service_name == "custom-prefix"

    def test_custom_prefix_ignores_default_prefix(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        monkeypatch.setenv("APP_CONFIG_PREFIX", "MYAPP_")
        monkeypatch.setenv("APP_SERVICE_NAME", "should-ignore")
        monkeypatch.setenv("MYAPP_SERVICE_NAME", "custom-wins")
        s = load_config(BaseSettings, path=tmp_path / "nope.toml")
        assert s.service_name == "custom-wins"

    def test_default_prefix_is_app(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        monkeypatch.setenv("APP_LOG_LEVEL", "TRACE")
        s = load_config(BaseSettings, path=tmp_path / "nope.toml")
        assert s.log_level == "TRACE"


# ---------------------------------------------------------------------------
# NEW — Nested configuration
# ---------------------------------------------------------------------------


class TestNestedConfiguration:
    """Double-underscore nesting and model_config flags."""

    def test_nested_delimiter_configured(self) -> None:
        assert BaseSettings.model_config.get("env_nested_delimiter") == "__"

    def test_extra_ignore_configured(self) -> None:
        assert BaseSettings.model_config.get("extra") == "ignore"

    def test_extra_fields_silently_dropped(self) -> None:
        s = BaseSettings(unknown_key="whatever")
        assert not hasattr(s, "unknown_key")

    def test_load_config_nested_env_var(self, tmp_path, monkeypatch) -> None:
        """APP_DB__HOST becomes {'db': {'host': value}} in the data dict."""
        _clean_app_env(monkeypatch)

        class DbSettings(BaseSettings):
            db: dict = {}

        monkeypatch.setenv("APP_DB__HOST", "pg.local")
        monkeypatch.setenv("APP_DB__PORT", "5432")
        s = load_config(DbSettings, path=tmp_path / "nope.toml")
        assert s.db["host"] == "pg.local"
        assert s.db["port"] == "5432"


# ---------------------------------------------------------------------------
# NEW — Subclassing BaseSettings
# ---------------------------------------------------------------------------


class TestSubclassing:
    """Custom settings classes that extend BaseSettings."""

    def test_custom_fields_with_defaults(self) -> None:
        class AppSettings(BaseSettings):
            db_host: str = "localhost"
            db_port: int = 5432
            debug: bool = False

        s = AppSettings()
        assert s.db_host == "localhost"
        assert s.db_port == 5432
        assert s.debug is False
        assert s.service_name == "pykit-service"  # inherited default

    def test_custom_fields_env_override(self, monkeypatch) -> None:
        class AppSettings(BaseSettings):
            db_host: str = "localhost"
            db_port: int = 5432

        monkeypatch.setenv("DB_HOST", "prod-db.example.com")
        monkeypatch.setenv("DB_PORT", "3306")
        s = AppSettings()
        assert s.db_host == "prod-db.example.com"
        assert s.db_port == 3306

    def test_subclass_with_load_config(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)

        class AppSettings(BaseSettings):
            db_host: str = "localhost"
            max_retries: int = 3

        f = tmp_path / "config.toml"
        f.write_text('service_name = "sub-svc"\ndb_host = "toml-db"\nmax_retries = 5\n')
        s = load_config(AppSettings, path=f)
        assert s.service_name == "sub-svc"
        assert s.db_host == "toml-db"
        assert s.max_retries == 5

    def test_subclass_app_env_overrides_toml(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)

        class AppSettings(BaseSettings):
            db_host: str = "localhost"

        f = tmp_path / "config.toml"
        f.write_text('db_host = "toml-db"\n')
        monkeypatch.setenv("APP_DB_HOST", "env-db")
        s = load_config(AppSettings, path=f)
        assert s.db_host == "env-db"

    def test_subclass_inherits_properties(self) -> None:
        class AppSettings(BaseSettings):
            custom: str = "val"

        s = AppSettings(environment="production")
        assert s.is_production is True
        assert s.is_development is False


# ---------------------------------------------------------------------------
# NEW — apply_defaults() and validate() hooks
# ---------------------------------------------------------------------------


class TestHooks:
    """Tests for apply_defaults / validate lifecycle hooks in load_config."""

    def test_apply_defaults_called(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        tracker = {"called": False}

        class HookSettings(BaseSettings):
            def apply_defaults(self) -> None:
                tracker["called"] = True

        load_config(HookSettings, path=tmp_path / "nope.toml")
        assert tracker["called"] is True

    def test_validate_hook_called(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        tracker = {"called": False}

        class ValidSettings(BaseSettings):
            def validate(self) -> None:
                tracker["called"] = True

        load_config(ValidSettings, path=tmp_path / "nope.toml")
        assert tracker["called"] is True

    def test_validate_error_propagates(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)

        class StrictSettings(BaseSettings):
            port: int = 50051

            def validate(self) -> None:
                if self.port <= 0:
                    raise ValueError("Port must be positive")

        f = tmp_path / "config.toml"
        f.write_text("port = -1\n")
        with pytest.raises(ValueError, match="Port must be positive"):
            load_config(StrictSettings, path=f)

    def test_apply_defaults_before_validate(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        order: list[str] = []

        class OrderSettings(BaseSettings):
            def apply_defaults(self) -> None:
                order.append("apply_defaults")

            def validate(self) -> None:
                order.append("validate")

        load_config(OrderSettings, path=tmp_path / "nope.toml")
        assert order == ["apply_defaults", "validate"]

    def test_no_hooks_no_error(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        s = load_config(BaseSettings, path=tmp_path / "nope.toml")
        assert s.service_name == "pykit-service"

    def test_apply_defaults_can_mutate(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)

        class MutSettings(BaseSettings):
            tag: str = ""

            def apply_defaults(self) -> None:
                if not self.tag:
                    object.__setattr__(self, "tag", f"{self.service_name}-default")

        s = load_config(MutSettings, path=tmp_path / "nope.toml")
        assert s.tag == "pykit-service-default"


# ---------------------------------------------------------------------------
# NEW — Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Boundary conditions, type coercion, and unusual inputs."""

    def test_empty_string_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("SERVICE_NAME", "")
        assert BaseSettings().service_name == ""

    def test_env_var_empty_vs_unset(self, monkeypatch) -> None:
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        assert BaseSettings().log_level == "INFO"

        monkeypatch.setenv("LOG_LEVEL", "")
        assert BaseSettings().log_level == ""

    def test_unicode_in_toml(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text('service_name = "서비스-名前-сервис"\n')
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "서비스-名前-сервис"

    def test_unicode_in_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("SERVICE_NAME", "日本語サービス")
        assert BaseSettings().service_name == "日本語サービス"

    def test_port_zero(self) -> None:
        assert BaseSettings(port=0).port == 0

    def test_port_zero_env(self, monkeypatch) -> None:
        monkeypatch.setenv("PORT", "0")
        assert BaseSettings().port == 0

    def test_negative_port_in_toml(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text("port = -1\n")
        s = load_config(BaseSettings, path=f)
        assert s.port == -1

    def test_boolean_true_variants(self, monkeypatch) -> None:
        for val in ("true", "True", "TRUE", "1", "yes", "on"):
            monkeypatch.setenv("METRICS_ENABLED", val)
            assert BaseSettings().metrics_enabled is True, f"Failed for '{val}'"

    def test_boolean_false_variants(self, monkeypatch) -> None:
        for val in ("false", "False", "FALSE", "0", "no", "off"):
            monkeypatch.setenv("METRICS_ENABLED", val)
            assert BaseSettings().metrics_enabled is False, f"Failed for '{val}'"

    def test_large_toml_file(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        lines = ['service_name = "large"\n'] + [f"# comment {i}\n" for i in range(1000)]
        f.write_text("".join(lines))
        assert load_config(BaseSettings, path=f).service_name == "large"

    def test_constructor_override(self) -> None:
        s = BaseSettings(service_name="ctor", port=1234, environment="staging")
        assert s.service_name == "ctor"
        assert s.port == 1234
        assert s.environment == "staging"

    def test_extra_fields_ignored_in_constructor(self) -> None:
        s = BaseSettings(service_name="test", unknown_key="nope")
        assert s.service_name == "test"
        assert not hasattr(s, "unknown_key")

    def test_extra_fields_ignored_in_toml(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text('service_name = "extra"\nunknown_field = "drop me"\n')
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "extra"
        assert not hasattr(s, "unknown_field")

    def test_int_parsing_from_env(self, monkeypatch) -> None:
        monkeypatch.setenv("PORT", "65535")
        assert BaseSettings().port == 65535

    def test_toml_with_comments_and_whitespace(self, tmp_path, monkeypatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text(
            "# Top-level comment\n\n"
            '  service_name = "commented"  # inline\n\n'
            "# Another comment\n"
            "port = 4040\n"
        )
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "commented"
        assert s.port == 4040
