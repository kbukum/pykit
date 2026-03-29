"""Tests for pykit_triton.TritonClient."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from pykit_triton import TritonClient
from pykit_triton.client import _numpy_to_triton_dtype

# ---------------------------------------------------------------------------
# TritonClient.__init__
# ---------------------------------------------------------------------------


class TestTritonClientInit:
    def test_defaults(self) -> None:
        client = TritonClient()
        assert client.url == "localhost:8001"
        assert client.verbose is False
        assert client._client is None

    def test_custom_url_and_verbose(self) -> None:
        client = TritonClient(url="triton.example.com:9001", verbose=True)
        assert client.url == "triton.example.com:9001"
        assert client.verbose is True


# ---------------------------------------------------------------------------
# is_connected / is_model_ready when not connected
# ---------------------------------------------------------------------------


class TestDisconnectedState:
    def test_is_connected_false_when_not_connected(self) -> None:
        client = TritonClient()
        assert client.is_connected is False

    def test_is_model_ready_false_when_not_connected(self) -> None:
        client = TritonClient()
        assert client.is_model_ready("my_model") is False
        assert client.is_model_ready("my_model", "1") is False


# ---------------------------------------------------------------------------
# connect() — tritonclient not installed
# ---------------------------------------------------------------------------


class TestConnectImportError:
    def test_raises_runtime_error_when_tritonclient_missing(self) -> None:
        client = TritonClient()

        # Make `import tritonclient.grpc` fail inside connect()
        with (
            patch.dict(sys.modules, {"tritonclient": None, "tritonclient.grpc": None}),
            pytest.raises(RuntimeError, match="tritonclient\\[grpc\\] is required"),
        ):
            client.connect()


# ---------------------------------------------------------------------------
# _numpy_to_triton_dtype
# ---------------------------------------------------------------------------


class TestNumpyToTritonDtype:
    @pytest.mark.parametrize(
        ("np_dtype_str", "expected"),
        [
            ("float32", "FP32"),
            ("float64", "FP64"),
            ("float16", "FP16"),
            ("int32", "INT32"),
            ("int64", "INT64"),
            ("int16", "INT16"),
            ("int8", "INT8"),
            ("uint8", "UINT8"),
            ("bool", "BOOL"),
        ],
    )
    def test_known_dtypes(self, np_dtype_str: str, expected: str) -> None:
        mock_dtype = MagicMock()
        mock_dtype.__str__ = MagicMock(return_value=np_dtype_str)
        assert _numpy_to_triton_dtype(mock_dtype) == expected

    def test_unknown_dtype_defaults_to_fp32(self) -> None:
        mock_dtype = MagicMock()
        mock_dtype.__str__ = MagicMock(return_value="complex128")
        assert _numpy_to_triton_dtype(mock_dtype) == "FP32"


# ---------------------------------------------------------------------------
# infer — not connected
# ---------------------------------------------------------------------------


class TestInferNotConnected:
    @pytest.mark.asyncio
    async def test_infer_raises_when_not_connected(self) -> None:
        client = TritonClient()
        with pytest.raises(RuntimeError, match="Client not connected"):
            await client.infer(
                model_name="test_model",
                inputs={},
                output_names=["output"],
            )
