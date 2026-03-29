"""Tests for pykit.config.BaseSettings."""

from __future__ import annotations

import os

from pykit_config import BaseSettings


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
