"""Tests for media delegation types and GrpcMediaClient stub."""

from __future__ import annotations

import pytest

from pykit_media import (
    GrpcMediaClient,
    MediaOperationRequest,
    MediaOperationResult,
    MediaServiceClient,
)

# ---------------------------------------------------------------------------
# MediaOperationRequest
# ---------------------------------------------------------------------------


class TestMediaOperationRequest:
    def test_defaults(self) -> None:
        req = MediaOperationRequest(operation_id="transcode", input_url="s3://bucket/input.mp4")
        assert req.operation_id == "transcode"
        assert req.input_url == "s3://bucket/input.mp4"
        assert req.parameters == {}
        assert req.output_format is None

    def test_with_parameters(self) -> None:
        req = MediaOperationRequest(
            operation_id="resize",
            input_url="s3://bucket/img.png",
            parameters={"width": 800, "height": 600},
            output_format="webp",
        )
        assert req.parameters["width"] == 800
        assert req.output_format == "webp"


# ---------------------------------------------------------------------------
# MediaOperationResult
# ---------------------------------------------------------------------------


class TestMediaOperationResult:
    def test_defaults(self) -> None:
        result = MediaOperationResult(output_url="s3://bucket/out.mp4")
        assert result.output_url == "s3://bucket/out.mp4"
        assert result.metadata == {}
        assert result.duration_seconds == 0.0

    def test_with_metadata(self) -> None:
        result = MediaOperationResult(
            output_url="s3://bucket/out.webm",
            metadata={"codec": "vp9"},
            duration_seconds=12.5,
        )
        assert result.metadata["codec"] == "vp9"
        assert result.duration_seconds == 12.5


# ---------------------------------------------------------------------------
# GrpcMediaClient stub
# ---------------------------------------------------------------------------


class TestGrpcMediaClient:
    def test_endpoint(self) -> None:
        client = GrpcMediaClient(endpoint="localhost:50051")
        assert client.endpoint == "localhost:50051"

    async def test_execute_operation_raises_not_implemented(self) -> None:
        client = GrpcMediaClient(endpoint="localhost:50051")
        req = MediaOperationRequest(operation_id="op", input_url="s3://b/in.mp4")
        with pytest.raises(NotImplementedError, match="proto stubs"):
            await client.execute_operation(req)

    async def test_execute_pipeline_raises_not_implemented(self) -> None:
        client = GrpcMediaClient(endpoint="localhost:50051")
        req = MediaOperationRequest(operation_id="op", input_url="s3://b/in.mp4")
        with pytest.raises(NotImplementedError, match="proto stubs"):
            await client.execute_pipeline([req])


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestMediaServiceClientProtocol:
    def test_grpc_client_satisfies_protocol(self) -> None:
        """GrpcMediaClient should structurally satisfy MediaServiceClient."""
        client = GrpcMediaClient(endpoint="localhost:50051")
        assert isinstance(client, MediaServiceClient)
