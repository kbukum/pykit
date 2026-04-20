"""Media operation delegation — delegate processing to the Rust media service via gRPC."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class MediaOperationRequest:
    """Request to delegate a media operation to the Rust media service.

    Attributes:
        operation_id: Unique identifier for the media operation.
        input_url: S3/MinIO URL of the input media.
        parameters: Operation-specific parameters.
        output_format: Desired output format, or ``None`` to keep the original.
    """

    operation_id: str
    input_url: str
    parameters: dict[str, object] = field(default_factory=dict)
    output_format: str | None = None


@dataclass
class MediaOperationResult:
    """Result from a delegated media operation.

    Attributes:
        output_url: S3/MinIO URL of the output media.
        metadata: Operation-specific result metadata.
        duration_seconds: Wall-clock time the operation took.
    """

    output_url: str
    metadata: dict[str, object] = field(default_factory=dict)
    duration_seconds: float = 0.0


@runtime_checkable
class MediaServiceClient(Protocol):
    """Protocol for calling the Rust media processing service."""

    async def execute_operation(self, request: MediaOperationRequest) -> MediaOperationResult:
        """Execute a single media operation.

        Args:
            request: The operation request.

        Returns:
            The operation result.
        """
        ...

    async def execute_pipeline(self, operations: list[MediaOperationRequest]) -> list[MediaOperationResult]:
        """Execute a sequence of media operations as a pipeline.

        Args:
            operations: Ordered list of operation requests.

        Returns:
            Results for each operation in the same order.
        """
        ...


@dataclass
class GrpcMediaClient:
    """gRPC client stub for the Rust media processor service.

    Implementation will be completed when the proto stubs are generated.
    This provides the interface contract.

    Attributes:
        endpoint: The gRPC endpoint address (e.g. ``localhost:50051``).
    """

    endpoint: str

    async def execute_operation(self, request: MediaOperationRequest) -> MediaOperationResult:
        """Execute a single media operation via gRPC.

        Raises:
            NotImplementedError: Always — requires generated proto stubs.
        """
        raise NotImplementedError("Requires generated proto stubs — implement after `make proto`")

    async def execute_pipeline(self, operations: list[MediaOperationRequest]) -> list[MediaOperationResult]:
        """Execute a pipeline of media operations via gRPC.

        Raises:
            NotImplementedError: Always — requires generated proto stubs.
        """
        raise NotImplementedError("Requires generated proto stubs — implement after `make proto`")
