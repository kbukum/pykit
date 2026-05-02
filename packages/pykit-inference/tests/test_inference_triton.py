"""Tests for pykit_inference.TritonClient."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from pykit_inference import TritonClient
from pykit_inference.triton import _numpy_to_triton_dtype

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


# ---------------------------------------------------------------------------
# connect() — with mocked tritonclient
# ---------------------------------------------------------------------------


class TestConnectMocked:
    def test_connect_creates_client(self) -> None:
        """Cover client.py lines 30-33: successful connect."""
        mock_grpc = MagicMock()
        mock_client_instance = MagicMock()
        mock_grpc.InferenceServerClient.return_value = mock_client_instance

        # The connect() method does `import tritonclient.grpc as grpcclient`
        mock_tritonclient = MagicMock()
        mock_tritonclient.grpc = mock_grpc

        with patch.dict(sys.modules, {"tritonclient": mock_tritonclient, "tritonclient.grpc": mock_grpc}):
            client = TritonClient(url="triton:8001", verbose=True)
            client.connect()
            assert client._client is mock_client_instance
            mock_grpc.InferenceServerClient.assert_called_once_with(url="triton:8001", verbose=True)


# ---------------------------------------------------------------------------
# is_connected / is_model_ready with mocked client
# ---------------------------------------------------------------------------


class TestConnectedState:
    def test_is_connected_true(self) -> None:
        """Cover client.py lines 45-46."""
        client = TritonClient()
        client._client = MagicMock()
        client._client.is_server_live.return_value = True
        assert client.is_connected is True

    def test_is_connected_exception_returns_false(self) -> None:
        """Cover client.py lines 47-48."""
        client = TritonClient()
        client._client = MagicMock()
        client._client.is_server_live.side_effect = Exception("dead")
        assert client.is_connected is False

    def test_is_model_ready_true(self) -> None:
        """Cover client.py lines 54-55."""
        client = TritonClient()
        client._client = MagicMock()
        client._client.is_model_ready.return_value = True
        assert client.is_model_ready("my_model", "1") is True

    def test_is_model_ready_exception_returns_false(self) -> None:
        """Cover client.py lines 56-57."""
        client = TritonClient()
        client._client = MagicMock()
        client._client.is_model_ready.side_effect = Exception("nope")
        assert client.is_model_ready("model") is False


# ---------------------------------------------------------------------------
# infer — with mocked client and tritonclient
# ---------------------------------------------------------------------------


class TestInferMocked:
    @pytest.mark.asyncio
    async def test_infer_success(self) -> None:
        """Cover client.py lines 77-97: full infer path."""
        np = pytest.importorskip("numpy")

        mock_grpc = MagicMock()
        mock_inp = MagicMock()
        mock_grpc.InferInput.return_value = mock_inp
        mock_out = MagicMock()
        mock_grpc.InferRequestedOutput.return_value = mock_out

        mock_result = MagicMock()
        mock_result.as_numpy.return_value = np.array([1.0, 2.0])

        mock_internal_client = MagicMock()
        mock_internal_client.infer.return_value = mock_result

        mock_tritonclient = MagicMock()
        mock_tritonclient.grpc = mock_grpc

        with patch.dict(sys.modules, {"tritonclient": mock_tritonclient, "tritonclient.grpc": mock_grpc}):
            client = TritonClient()
            client._client = mock_internal_client

            inputs = {"input_0": np.array([[1.0, 2.0]], dtype=np.float32)}
            result = await client.infer("my_model", inputs, ["output_0"])
            assert "output_0" in result
            np.testing.assert_array_equal(result["output_0"], np.array([1.0, 2.0]))


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_connected(self) -> None:
        """Cover client.py lines 99-101."""
        client = TritonClient()
        client._client = MagicMock()
        client._client.is_server_live.return_value = True
        assert await client.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_disconnected(self) -> None:
        client = TritonClient()
        assert await client.health_check() is False
