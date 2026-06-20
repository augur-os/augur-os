"""Platform detection, Windows support utilities, and security layer for file operations.

This module handles:
- Platform detection (Windows vs Unix)
- Windows-specific utilities (long paths, retry logic, safe file operations)
- Allowed root directory management
- Path security validation and resolution
"""

import gc
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.mcp.augur_shared.config import (
    get_documents_dir,
    get_logs_dir,
    get_project_root,
    get_runtime_dir,
    get_vault_dir,
)
from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp.files")

# =============================================================================
# Platform Detection
# =============================================================================

IS_WINDOWS = sys.platform == "win32"

# Windows-specific constants
WINDOWS_MAX_PATH = 260
WINDOWS_LONG_PATH_PREFIX = "\\\\?\\"

# =============================================================================
# Allowed Roots (computed once)
# =============================================================================

_ALLOWED_ROOTS: dict[str, Path] = {}


def _init_allowed_roots() -> None:
    """Initialize allowed root directories."""
    global _ALLOWED_ROOTS
    if not _ALLOWED_ROOTS:
        roots = {}
        if project_root := get_project_root():
            roots["code"] = project_root
            roots["data"] = project_root
        roots["vault"] = get_vault_dir()
        roots["documents"] = get_documents_dir()
        roots["runtime"] = get_runtime_dir()
        roots["logs"] = get_logs_dir()
        # Browse indexes additional document-source folders (Desktop, Downloads)
        # via default_document_sources. They must be allowed roots too, or
        # file-info/open/reveal reject every indexed file from those folders as
        # "outside allowed repositories". setdefault keeps the canonical
        # "documents" entry when a source resolves to the same path.
        from src.lib.index.document_sources import default_document_sources

        for source in default_document_sources(documents_dir=roots["documents"]):
            roots.setdefault(source.id, source.resolved_path)
        _ALLOWED_ROOTS = roots


def get_allowed_roots() -> dict[str, Path]:
    """Get allowed root directories."""
    _init_allowed_roots()
    return _ALLOWED_ROOTS


# =============================================================================
# Windows Support Utilities
# =============================================================================


def normalize_path(path: Path) -> Path:
    """
    Normalize path for cross-platform compatibility.

    On Windows:
    - Converts forward slashes to backslashes
    - Adds long path prefix for paths > 260 characters
    - Resolves . and .. components
    """
    if not IS_WINDOWS:
        return path

    path_str = str(path.resolve())

    # Add long path prefix if needed and not already present
    if len(path_str) > WINDOWS_MAX_PATH and not path_str.startswith(WINDOWS_LONG_PATH_PREFIX):
        path_str = WINDOWS_LONG_PATH_PREFIX + path_str

    return Path(path_str)


def get_safe_encoding(encoding: str = "utf-8") -> str:
    """
    Get safe encoding for the platform.

    On Windows, prefer utf-8-sig for reading to handle BOM automatically.
    """
    if IS_WINDOWS and encoding == "utf-8":
        return "utf-8-sig"
    return encoding


def retry_on_windows_error(
    func: Callable,
    max_retries: int = 5,
    initial_delay: float = 0.1,
    max_delay: float = 2.0,
    retry_errors: tuple | None = None,
) -> Any:
    """
    Retry a function on Windows-specific errors with exponential backoff.

    Handles common Windows I/O issues:
    - PermissionError: File locked by another process
    - OSError with errno 32: Sharing violation
    - OSError with errno 5: Access denied (temporary)

    Args:
        func: Function to call
        max_retries: Maximum retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        retry_errors: Tuple of error types to retry on

    Returns:
        Result of the function call

    Raises:
        The last exception if all retries fail
    """
    if retry_errors is None:
        retry_errors = (PermissionError, OSError)

    last_error = None
    delay = initial_delay

    for attempt in range(max_retries):
        try:
            return func()
        except retry_errors as e:
            last_error = e

            # Check if this is a retryable Windows error
            is_retryable = False
            if isinstance(e, PermissionError):
                is_retryable = True
            elif isinstance(e, OSError):
                # errno 32 = sharing violation, errno 5 = access denied
                if hasattr(e, "winerror") and e.winerror in (32, 5):
                    is_retryable = True
                elif e.errno in (5, 13, 32):  # EACCES, permission errors
                    is_retryable = True

            if not is_retryable or attempt == max_retries - 1:
                raise

            logger.debug(f"Retry {attempt + 1}/{max_retries} after {delay:.2f}s due to: {e}")

            # Force garbage collection to release file handles
            gc.collect()
            time.sleep(delay)

            # Exponential backoff with jitter
            delay = min(delay * 2, max_delay)

    raise last_error  # type: ignore


def safe_delete(path: Path, max_retries: int = 5) -> bool:
    """
    Safely delete a file with retry logic for Windows.

    Args:
        path: Path to delete
        max_retries: Maximum retry attempts

    Returns:
        True if deleted, False if didn't exist
    """
    if not path.exists():
        return False

    def _delete():
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()

    if IS_WINDOWS:
        retry_on_windows_error(_delete, max_retries=max_retries)
    else:
        _delete()

    return True


def safe_rename(src: Path, dst: Path, max_retries: int = 5) -> None:
    """
    Safely rename/move a file with retry logic for Windows.

    On Windows, handles:
    - Locked files with retry
    - Cross-device moves (falls back to copy+delete)
    - Destination already exists (removes first)

    Args:
        src: Source path
        dst: Destination path
        max_retries: Maximum retry attempts
    """

    def _rename():
        # On Windows, replace() can fail if destination exists and is locked
        if IS_WINDOWS and dst.exists():
            safe_delete(dst, max_retries=max_retries)
        src.replace(dst)

    try:
        if IS_WINDOWS:
            retry_on_windows_error(_rename, max_retries=max_retries)
        else:
            _rename()
    except OSError as e:
        # Handle cross-device link error (errno 18 on Unix, various on Windows)
        if e.errno == 18 or (IS_WINDOWS and hasattr(e, "winerror")):
            # Fall back to copy + delete
            shutil.copy2(src, dst)
            safe_delete(src, max_retries=max_retries)
        else:
            raise


def safe_copy(src: Path, dst: Path, max_retries: int = 5) -> None:
    """
    Safely copy a file with retry logic for Windows.

    Args:
        src: Source path
        dst: Destination path
        max_retries: Maximum retry attempts
    """

    def _copy():
        shutil.copy2(src, dst)

    if IS_WINDOWS:
        retry_on_windows_error(_copy, max_retries=max_retries)
    else:
        _copy()


# =============================================================================
# Security Layer
# =============================================================================


def validate_path_within_roots(path: Path) -> None:
    """
    Validate that a resolved path is within allowed roots.

    This function should be called AFTER resolving symlinks to ensure
    the final target is still within allowed repositories.

    Args:
        path: Path to validate (should already be resolved via realpath/resolve)

    Raises:
        PermissionError: If path is outside allowed roots
    """
    roots = get_allowed_roots()
    resolved = path.resolve()  # Follow symlinks to get real path

    for root in roots.values():
        try:
            resolved.relative_to(root)
            return  # Path is within this root
        except ValueError:
            continue

    raise PermissionError(f"Access denied: path '{path}' resolves outside allowed repositories")


def resolve_secure_path(
    path: str,
    repo: str,
) -> tuple[Path, str]:
    """
    Resolve path securely within allowed repositories.

    Args:
        path: User-provided path (relative or absolute)
        repo: Target repository ("code", "data", or "auto")

    Returns:
        Tuple of (resolved_path, detected_repo)

    Raises:
        ValueError: If path is outside allowed roots
    """
    roots = get_allowed_roots()
    path_obj = Path(path)
    path_parts = path_obj.parts
    runtime_relative = bool(path_parts) and path_parts[0] == "runtime"

    # Determine which repos to check (only include repos that exist in roots)
    if repo == "auto":
        repos_to_check = []
        if runtime_relative and "runtime" in roots:
            repos_to_check.append("runtime")
        repos_to_check.extend(
            r for r in ["data", "code", "vault", "documents", "runtime"] if r in roots and r not in repos_to_check
        )
        # Include any remaining roots (logs and indexed document sources such as
        # Desktop/Downloads) last, so existing repo priority is preserved while
        # absolute paths under those roots still validate.
        repos_to_check.extend(r for r in roots if r not in repos_to_check)
    else:
        if repo not in roots:
            raise ValueError(f"Repository '{repo}' is not available (available: {list(roots.keys())})")
        repos_to_check = [repo]

    # If path is absolute, validate it's in allowed roots
    if path_obj.is_absolute():
        resolved = path_obj.resolve()
        for repo_name in repos_to_check:
            root = roots[repo_name]
            try:
                resolved.relative_to(root)
                return resolved, repo_name
            except ValueError:
                continue
        raise ValueError(f"Path '{path}' is outside allowed repositories ({', '.join(roots.keys())})")

    # Relative path - try each repo
    for repo_name in repos_to_check:
        root = roots[repo_name]
        candidate_path = path_obj
        if repo_name == "runtime" and runtime_relative:
            candidate_path = Path(*path_parts[1:]) if len(path_parts) > 1 else Path(".")
        candidate = (root / candidate_path).resolve()
        try:
            candidate.relative_to(root)
            return candidate, repo_name
        except ValueError:
            continue  # Path escapes this root (traversal attempt)

    raise ValueError(f"Path '{path}' cannot be resolved within allowed repositories")
