"""Tests for pykit_config.loader — TOML loading, env overrides, profiles, validation hooks."""

from __future__ import annotations

import os
import tomllib

import pytest

from pykit_config import BaseSettings, load_config


def _clean_app_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove env vars that could interfere with load_config tests."""
    for key in list(os.environ):
        if key.startswith("APP_"):
            monkeypatch.delenv(key, raising=False)
    for bare in (
        "SERVICE_NAME",
        "ENVIRONMENT",
        "SERVICE_ADDRESS",
        "SERVICE_PORT",
        "LOG_LEVEL",
        "LOG_FORMAT",
        "METRICS_PORT",
        "METRICS_ENABLED",
    ):
        monkeypatch.delenv(bare, raising=False)


class TestLoadFromToml:
    """Loading config from TOML files."""

    def test_valid_toml(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text('service_name = "toml-svc"\nservice_port = 7070\n')
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "toml-svc"
        assert s.service_port == 7070

    def test_missing_file_uses_defaults(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        s = load_config(BaseSettings, path=tmp_path / "missing.toml")
        assert s.service_name == "pykit-service"
        assert s.service_port == 50051

    def test_empty_file_uses_defaults(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "empty.toml"
        f.write_text("")
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "pykit-service"

    def test_invalid_toml_raises(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "bad.toml"
        f.write_text("this is not [[[valid toml")
        with pytest.raises(tomllib.TOMLDecodeError):
            load_config(BaseSettings, path=f)

    def test_string_path(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text('service_name = "str-path"\n')
        s = load_config(BaseSettings, path=str(f))
        assert s.service_name == "str-path"

    def test_default_path_is_config_toml(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.toml").write_text('service_name = "default-path"\n')
        s = load_config(BaseSettings)
        assert s.service_name == "default-path"

    def test_all_fields_from_toml(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text(
            'service_name = "full"\n'
            'environment = "staging"\n'
            'service_address = "10.0.0.1"\n'
            "service_port = 3000\n"
            'log_level = "WARNING"\n'
            'log_format = "json"\n'
            "metrics_port = 8888\n"
            "metrics_enabled = false\n"
        )
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "full"
        assert s.environment == "staging"
        assert s.service_address == "10.0.0.1"
        assert s.service_port == 3000
        assert s.log_level == "WARNING"
        assert s.log_format == "json"
        assert s.metrics_port == 8888
        assert s.metrics_enabled is False


class TestEnvVarOverrides:
    """APP_* env vars override TOML values."""

    def test_env_overrides_toml(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text('service_name = "toml"\nservice_port = 7070\n')
        monkeypatch.setenv("APP_SERVICE_NAME", "env-name")
        monkeypatch.setenv("APP_SERVICE_PORT", "9999")
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "env-name"
        assert s.service_port == 9999

    def test_env_without_toml(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        monkeypatch.setenv("APP_SERVICE_NAME", "env-only")
        s = load_config(BaseSettings, path=tmp_path / "missing.toml")
        assert s.service_name == "env-only"

    def test_nested_env_var(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)

        class DbSettings(BaseSettings):
            db: dict = {}  # noqa: RUF012

        monkeypatch.setenv("APP_DB__HOST", "pg.local")
        monkeypatch.setenv("APP_DB__PORT", "5432")
        s = load_config(DbSettings, path=tmp_path / "missing.toml")
        assert s.db["host"] == "pg.local"
        assert s.db["port"] == "5432"

    def test_custom_prefix(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        monkeypatch.setenv("APP_CONFIG_PREFIX", "MYAPP_")
        monkeypatch.setenv("MYAPP_SERVICE_NAME", "custom-prefix")
        s = load_config(BaseSettings, path=tmp_path / "missing.toml")
        assert s.service_name == "custom-prefix"

    def test_full_precedence_defaults_toml_env(
        self, tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """defaults < TOML < APP_ env vars — all three layers."""
        _clean_app_env(monkeypatch)
        f = tmp_path / "config.toml"
        f.write_text('service_name = "toml"\nservice_port = 7070\nlog_level = "WARNING"\n')
        monkeypatch.setenv("APP_SERVICE_NAME", "env")
        s = load_config(BaseSettings, path=f)
        assert s.service_name == "env"  # env > TOML
        assert s.service_port == 7070  # TOML > default
        assert s.log_level == "WARNING"  # TOML > default
        assert s.service_address == "0.0.0.0"  # default


class TestProfiles:
    """Profile-specific env file loading."""

    def test_profile_loads_env_file(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        monkeypatch.chdir(tmp_path)
        profiles_dir = tmp_path / "config" / "profiles"
        profiles_dir.mkdir(parents=True)
        (profiles_dir / "docker.env").write_text("APP_SERVICE_NAME=from-profile\n")
        s = load_config(BaseSettings, path=tmp_path / "missing.toml", profile="docker")
        assert s.service_name == "from-profile"

    def test_empty_profile_reads_environment_var(
        self, tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _clean_app_env(monkeypatch)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENVIRONMENT", "staging")
        profiles_dir = tmp_path / "config" / "profiles"
        profiles_dir.mkdir(parents=True)
        (profiles_dir / "staging.env").write_text("APP_LOG_LEVEL=DEBUG\n")
        s = load_config(BaseSettings, path=tmp_path / "missing.toml", profile="")
        assert s.log_level == "DEBUG"

    def test_none_profile_skips_profile_loading(
        self, tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _clean_app_env(monkeypatch)
        s = load_config(BaseSettings, path=tmp_path / "missing.toml", profile=None)
        assert s.service_name == "pykit-service"

    def test_missing_profile_file_is_ok(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        s = load_config(BaseSettings, path=tmp_path / "missing.toml", profile="nonexistent")
        assert s.service_name == "pykit-service"


class TestValidationHooks:
    """apply_defaults() and validate() lifecycle hooks."""

    def test_apply_defaults_called(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        tracker = {"called": False}

        class HookSettings(BaseSettings):
            def apply_defaults(self) -> None:
                tracker["called"] = True

        load_config(HookSettings, path=tmp_path / "missing.toml")
        assert tracker["called"] is True

    def test_validate_called(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        tracker = {"called": False}

        class ValidSettings(BaseSettings):
            def validate(self) -> None:
                tracker["called"] = True

        load_config(ValidSettings, path=tmp_path / "missing.toml")
        assert tracker["called"] is True

    def test_apply_defaults_before_validate(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        order: list[str] = []

        class OrderSettings(BaseSettings):
            def apply_defaults(self) -> None:
                order.append("apply_defaults")

            def validate(self) -> None:
                order.append("validate")

        load_config(OrderSettings, path=tmp_path / "missing.toml")
        assert order == ["apply_defaults", "validate"]

    def test_validate_error_propagates(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)

        class StrictSettings(BaseSettings):
            service_port: int = 50051

            def validate(self) -> None:
                if self.service_port <= 0:
                    raise ValueError("Port must be positive")

        f = tmp_path / "config.toml"
        f.write_text("service_port = -1\n")
        with pytest.raises(ValueError, match="Port must be positive"):
            load_config(StrictSettings, path=f)

    def test_apply_defaults_can_mutate(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)

        class MutSettings(BaseSettings):
            tag: str = ""

            def apply_defaults(self) -> None:
                if not self.tag:
                    object.__setattr__(self, "tag", f"{self.service_name}-default")

        s = load_config(MutSettings, path=tmp_path / "missing.toml")
        assert s.tag == "pykit-service-default"

    def test_no_hooks_no_error(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_app_env(monkeypatch)
        s = load_config(BaseSettings, path=tmp_path / "missing.toml")
        assert s.service_name == "pykit-service"
