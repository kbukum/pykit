"""Generic Triton Inference Server client wrapper."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np


class TritonClient:
    """Wrapper around Triton gRPC client for model inference.

    Provides a simplified interface for loading models and running inference
    on Triton Inference Server.
    """

    def __init__(
        self,
        *,
        url: str = "localhost:8001",
        verbose: bool = False,
    ) -> None:
        self.url = url
        self.verbose = verbose
        self._client: Any = None

    def connect(self) -> None:
        """Connect to the Triton server."""
        try:
            import tritonclient.grpc as grpcclient

            self._client = grpcclient.InferenceServerClient(url=self.url, verbose=self.verbose)
        except ImportError as exc:
            raise RuntimeError(
                "tritonclient[grpc] is required for Triton integration. "
                "Install with: pip install tritonclient[grpc]"
            ) from exc

    @property
    def is_connected(self) -> bool:
        """Check if the client is connected and server is alive."""
        if self._client is None:
            return False
        try:
            return bool(self._client.is_server_live())
        except Exception:
            return False

    def is_model_ready(self, model_name: str, model_version: str = "") -> bool:
        """Check if a model is loaded and ready for inference."""
        if self._client is None:
            return False
        try:
            return bool(self._client.is_model_ready(model_name, model_version))
        except Exception:
            return False

    async def infer(
        self,
        model_name: str,
        inputs: dict[str, np.ndarray[Any, Any]],
        output_names: list[str],
        model_version: str = "",
    ) -> dict[str, np.ndarray[Any, Any]]:
        """Run inference on a Triton model.

        Args:
            model_name: Name of the model on Triton.
            inputs: Dictionary of input name → numpy array.
            output_names: List of output tensor names to request.
            model_version: Model version (empty string = latest).

        Returns:
            Dictionary of output name → numpy array.
        """
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        import tritonclient.grpc as grpcclient

        triton_inputs = []
        for name, data in inputs.items():
            inp = grpcclient.InferInput(name, list(data.shape), _numpy_to_triton_dtype(data.dtype))
            inp.set_data_from_numpy(data)
            triton_inputs.append(inp)

        triton_outputs = [grpcclient.InferRequestedOutput(name) for name in output_names]

        result = self._client.infer(
            model_name=model_name,
            inputs=triton_inputs,
            outputs=triton_outputs,
            model_version=model_version,
        )

        return {name: result.as_numpy(name) for name in output_names}

    async def health_check(self) -> bool:
        """Check if Triton server is healthy."""
        return self.is_connected


def _numpy_to_triton_dtype(dtype: np.dtype[Any]) -> str:
    """Convert numpy dtype to Triton dtype string."""
    mapping: dict[str, str] = {
        "float32": "FP32",
        "float64": "FP64",
        "float16": "FP16",
        "int32": "INT32",
        "int64": "INT64",
        "int16": "INT16",
        "int8": "INT8",
        "uint8": "UINT8",
        "bool": "BOOL",
    }
    return mapping.get(str(dtype), "FP32")
