"""Git-specific error helpers."""

from __future__ import annotations

from pykit_errors import AppError


def repo_not_found(path: str) -> AppError:
    """Repository not found at path."""
    return AppError.not_found("repository", path)


def ref_not_found(refname: str) -> AppError:
    """Git reference not found."""
    return AppError.not_found("ref", refname)


def remote_not_found(name: str) -> AppError:
    """Git remote not found."""
    return AppError.not_found("remote", name)


def config_not_found(key: str) -> AppError:
    """Git config key not found."""
    return AppError.not_found("config", key)


def path_not_found(path: str) -> AppError:
    """Repository path not found."""
    return AppError.not_found("path", path)


def ambiguous_ref(refname: str) -> AppError:
    """Ambiguous git reference."""
    return AppError.invalid_input("ref", f"ambiguous ref: {refname}")


def merge_conflict(path: str) -> AppError:
    """Merge conflict in a file."""
    return AppError.conflict(f"merge conflict in {path}")


def checked_out_branch(name: str) -> AppError:
    """Branch cannot be deleted because it is checked out."""
    return AppError.conflict(f"cannot delete checked out branch: {name}")


def already_exists(kind: str, name: str) -> AppError:
    """Named git resource already exists."""
    return AppError.conflict(f"{kind} already exists: {name}")


def detached_head() -> AppError:
    """HEAD is detached."""
    return AppError.invalid_input("HEAD", "detached HEAD")


def invalid_line_range(start: int, end: int) -> AppError:
    """Invalid blame line range."""
    return AppError.invalid_input("lineRange", f"invalid line range: start={start} end={end}")


def invalid_path(path: str) -> AppError:
    """Invalid repository-relative path."""
    return AppError.invalid_input("path", f"invalid path: {path}")


def invalid_config_key(key: str) -> AppError:
    """Invalid git config key."""
    return AppError.invalid_input("key", f"invalid config key: {key}")


def authentication_failed(reason: str) -> AppError:
    """Authentication failed for a git transport."""
    return AppError.unauthorized(reason or "authentication failed")


def signing_not_supported() -> AppError:
    """Commit signing is not supported by the selected backend."""
    return AppError.invalid_input("sign", "commit signing is not supported by the selected backend")


def invalid_transport(kind: str) -> AppError:
    """Unsupported transport configuration."""
    return AppError.invalid_input("transport", f"unsupported transport auth: {kind}")


def operation_not_supported(operation: str, backend: str) -> AppError:
    """Operation is not implemented by the selected backend."""
    return AppError.invalid_input("operation", f"{operation} is not supported by the {backend} backend")


def cli_not_implemented() -> AppError:
    """Git CLI backend is not implemented."""
    return AppError.invalid_input("backend", "git CLI backend is not implemented")


def network_error(cause: Exception) -> AppError:
    """Network error during remote operations."""
    return AppError.external_service("git", cause)


def internal_error(cause: Exception) -> AppError:
    """Internal git error."""
    return AppError.internal(cause)
