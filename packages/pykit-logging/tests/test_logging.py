"""Tests for pykit.logging."""

from __future__ import annotations

from pykit_logging.setup import (
    correlation_id_var,
    get_logger,
    new_correlation_id,
    set_correlation_id,
    setup_logging,
)


class TestLogging:
    def test_setup_logging_console(self) -> None:
        setup_logging(level="DEBUG", log_format="console", service_name="test")
        logger = get_logger("test")
        assert logger is not None

    def test_setup_logging_json(self) -> None:
        setup_logging(level="INFO", log_format="json", service_name="test")
        logger = get_logger("test")
        assert logger is not None

    def test_setup_logging_auto(self) -> None:
        setup_logging(level="INFO", log_format="auto")
        logger = get_logger("test")
        assert logger is not None

    def test_correlation_id(self) -> None:
        cid = set_correlation_id("test-123")
        assert cid == "test-123"
        assert correlation_id_var.get() == "test-123"

    def test_correlation_id_auto(self) -> None:
        cid = set_correlation_id()
        assert len(cid) > 0
        assert correlation_id_var.get() == cid

    def test_new_correlation_id(self) -> None:
        cid1 = new_correlation_id()
        cid2 = new_correlation_id()
        assert cid1 != cid2
