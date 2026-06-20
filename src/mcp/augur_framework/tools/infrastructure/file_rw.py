"""Read and write implementation functions for file access operations.

This module contains the async implementation functions for reading and writing
files (text and binary). These are called by the MCP tool handlers in files.py.
"""

import asyncio
import base64
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from src.mcp.augur_shared.logging import get_entity_logger

from .file_assets import _guess_mime_type, _validate_asset_magic_bytes
from .file_models import MAX_BINARY_SIZE
from .file_platform import (
    IS_WINDOWS,
    get_safe_encoding,
    normalize_path,
    retry_on_windows_error,
    safe_copy,
    safe_delete,
    safe_rename,
    validate_path_within_roots,
)

logger = get_entity_logger("mcp.files")


async def read_file_impl(
    path: Path,
    offset: int = 0,
    limit: int = 2000,
    encoding: str = "utf-8",
    binary: bool = False,
) -> dict[str, Any]:
    """
    Read file with pagination support.

    Uses synchronous I/O wrapped in to_thread for non-blocking.
    Includes Windows support with retry logic and proper encoding handling.
    When binary=True, returns base64-encoded content instead of text lines.
    """

    def _read_sync() -> dict[str, Any]:
        # Normalize path for Windows long path support
        normalized_path = normalize_path(path)

        if not normalized_path.exists():
            return {"status": "error", "message": f"File not found: {path}"}

        if not normalized_path.is_file():
            return {"status": "error", "message": f"Not a file: {path}"}

        # Security: Validate resolved path (after following symlinks) is within allowed roots
        try:
            validate_path_within_roots(normalized_path)
        except PermissionError as e:
            return {"status": "error", "message": str(e)}

        # Binary mode: read raw bytes and return as base64
        if binary:
            try:
                file_size = normalized_path.stat().st_size
                if file_size > MAX_BINARY_SIZE:
                    return {
                        "status": "error",
                        "message": f"File too large for binary read: {file_size} bytes "
                        f"(limit: {MAX_BINARY_SIZE} bytes / {MAX_BINARY_SIZE // (1024 * 1024)}MB)",
                        "path": str(path),
                    }

                def _do_binary_read() -> dict[str, Any]:
                    with open(normalized_path, "rb") as f:
                        data = f.read()
                    return {
                        "status": "success",
                        "content_base64": base64.b64encode(data).decode("ascii"),
                        "size_bytes": len(data),
                        "mime_type": _guess_mime_type(normalized_path),
                        "path": str(path),
                        "platform": "windows" if IS_WINDOWS else "unix",
                    }

                if IS_WINDOWS:
                    return retry_on_windows_error(_do_binary_read, max_retries=3)
                return _do_binary_read()
            except PermissionError as e:
                return {"status": "error", "message": f"Permission denied (file may be locked): {e}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        # Use safe encoding for Windows (handles BOM)
        safe_encoding = get_safe_encoding(encoding)

        def _do_read() -> dict[str, Any]:
            with open(normalized_path, encoding=safe_encoding, errors="replace") as f:
                # Count total lines efficiently
                total_lines = sum(1 for _ in f)
                f.seek(0)

                # Skip to offset
                for _ in range(offset):
                    if not f.readline():
                        break

                # Read limited lines
                lines = []
                for _ in range(limit):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line.rstrip("\n\r"))

                # Gather file metadata for dashboard
                stat = normalized_path.stat()
                suffix = normalized_path.suffix.lstrip(".")
                lang_map = {
                    "py": "python",
                    "ts": "typescript",
                    "tsx": "typescriptreact",
                    "js": "javascript",
                    "jsx": "javascriptreact",
                    "json": "json",
                    "yaml": "yaml",
                    "yml": "yaml",
                    "md": "markdown",
                    "css": "css",
                    "html": "html",
                    "sh": "shellscript",
                    "bash": "shellscript",
                    "rs": "rust",
                    "go": "go",
                    "rb": "ruby",
                    "toml": "toml",
                }

                return {
                    "status": "success",
                    "content": "\n".join(lines),
                    "total_lines": total_lines,
                    "offset": offset,
                    "limit": limit,
                    "lines_returned": len(lines),
                    "path": str(path),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "language": lang_map.get(suffix, "plaintext"),
                    "platform": "windows" if IS_WINDOWS else "unix",
                }

        try:
            # Use retry logic on Windows for locked files
            if IS_WINDOWS:
                return retry_on_windows_error(_do_read, max_retries=3)
            return _do_read()
        except UnicodeDecodeError as e:
            return {"status": "error", "message": f"Encoding error ({encoding}): {e}"}
        except PermissionError as e:
            return {"status": "error", "message": f"Permission denied (file may be locked): {e}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return await asyncio.to_thread(_read_sync)


async def write_file_impl(
    path: Path,
    content: str,
    create_backup: bool = True,
    create_dirs: bool = True,
    append: bool = False,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    """
    Write file with atomic write pattern and optional backup.

    Includes comprehensive Windows support:
    - Retry logic for locked files with exponential backoff
    - Safe atomic writes using temp file + rename
    - Proper cleanup of temp files on failure
    - Long path support (> 260 characters)
    """

    def _write_sync() -> dict[str, Any]:
        # Normalize path for Windows long path support
        normalized_path = normalize_path(path)
        temp_path = None
        backup_path = None

        # Security: Validate target path is within allowed roots before any write
        try:
            validate_path_within_roots(normalized_path)
        except PermissionError as e:
            return {"status": "error", "message": str(e), "path": str(path)}

        try:
            # Create parent directories if needed
            if create_dirs:
                normalized_path.parent.mkdir(parents=True, exist_ok=True)

            final_content = content
            if append and normalized_path.exists():
                final_content = normalized_path.read_text(encoding=encoding) + content

            # Create backup if file exists
            if create_backup and normalized_path.exists():
                backup_path = normalized_path.with_suffix(normalized_path.suffix + ".bak")
                safe_copy(normalized_path, backup_path)

            # Generate unique temp file name to avoid conflicts
            temp_path = normalized_path.with_suffix(normalized_path.suffix + f".tmp.{os.getpid()}.{time.time_ns()}")

            # Write to temp file
            def _do_write():
                assert temp_path is not None
                with open(temp_path, "w", encoding=encoding, newline="") as f:
                    f.write(final_content)
                    f.flush()
                    # Ensure data is written to disk on Windows
                    if IS_WINDOWS:
                        os.fsync(f.fileno())

            if IS_WINDOWS:
                retry_on_windows_error(_do_write, max_retries=3)
            else:
                _do_write()

            # Atomic rename (with retry on Windows)
            safe_rename(temp_path, normalized_path)
            temp_path = None  # Successfully renamed, don't clean up

            return {
                "status": "success",
                "ok": True,
                "path": str(path),
                "bytes_written": len(final_content.encode(encoding)),
                "appended": append,
                "backup_path": str(backup_path) if backup_path else None,
                "platform": "windows" if IS_WINDOWS else "unix",
            }

        except PermissionError as e:
            return {
                "status": "error",
                "message": f"Permission denied (file may be locked by another process): {e}",
                "path": str(path),
            }
        except OSError as e:
            error_detail = ""
            if IS_WINDOWS and hasattr(e, "winerror"):
                error_codes = {
                    5: "Access denied",
                    32: "File is being used by another process",
                    123: "Invalid filename or path",
                    206: "Path too long",
                }
                error_detail = f" ({error_codes.get(e.winerror, f'Windows error {e.winerror}')})"
            return {
                "status": "error",
                "message": f"OS error{error_detail}: {e}",
                "path": str(path),
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "path": str(path)}
        finally:
            # Clean up temp file if it still exists (write failed before rename)
            if temp_path and temp_path.exists():
                try:
                    safe_delete(temp_path)
                except Exception:
                    logger.warning(f"Failed to clean up temp file: {temp_path}")

    return await asyncio.to_thread(_write_sync)


async def write_binary_file_impl(
    path: Path,
    content_base64: str,
    create_backup: bool = True,
    create_dirs: bool = True,
) -> dict[str, Any]:
    """
    Write binary file from base64-encoded content with atomic write pattern.

    Decodes base64 content, validates size, checks magic bytes for known
    extensions, and writes via binary mode with temp file + atomic rename.
    """

    def _write_binary_sync() -> dict[str, Any]:
        normalized_path = normalize_path(path)
        temp_path = None
        backup_path = None

        # Security: Validate target path is within allowed roots before any write
        try:
            validate_path_within_roots(normalized_path)
        except PermissionError as e:
            return {"status": "error", "message": str(e), "path": str(path)}

        # Decode base64 content
        try:
            data = base64.b64decode(content_base64, validate=True)
        except Exception as e:
            return {
                "status": "error",
                "message": f"Invalid base64 content: {e}",
                "path": str(path),
            }

        # Enforce size limit
        if len(data) > MAX_BINARY_SIZE:
            return {
                "status": "error",
                "message": (
                    f"Content too large: {len(data)} bytes "
                    f"(limit: {MAX_BINARY_SIZE} bytes / {MAX_BINARY_SIZE // (1024 * 1024)}MB)"
                ),
                "path": str(path),
            }

        # Validate magic bytes for known extensions (advisory warning only)
        extension = normalized_path.suffix
        valid, warning_msg = _validate_asset_magic_bytes(data, extension)
        if not valid:
            logger.warning(f"Asset magic bytes warning for {path}: {warning_msg}")

        try:
            # Create parent directories if needed
            if create_dirs:
                normalized_path.parent.mkdir(parents=True, exist_ok=True)

            # Create backup if file exists
            if create_backup and normalized_path.exists():
                backup_path = normalized_path.with_suffix(normalized_path.suffix + ".bak")
                safe_copy(normalized_path, backup_path)

            # Generate unique temp file name to avoid conflicts
            temp_path = normalized_path.with_suffix(normalized_path.suffix + f".tmp.{os.getpid()}.{time.time_ns()}")

            # Write to temp file in binary mode
            def _do_write():
                assert temp_path is not None
                with open(temp_path, "wb") as f:
                    f.write(data)
                    f.flush()
                    if IS_WINDOWS:
                        os.fsync(f.fileno())

            if IS_WINDOWS:
                retry_on_windows_error(_do_write, max_retries=3)
            else:
                _do_write()

            # Atomic rename (with retry on Windows)
            safe_rename(temp_path, normalized_path)
            temp_path = None  # Successfully renamed, don't clean up

            result: dict[str, Any] = {
                "status": "success",
                "path": str(path),
                "bytes_written": len(data),
                "mime_type": _guess_mime_type(normalized_path),
                "backup_path": str(backup_path) if backup_path else None,
                "platform": "windows" if IS_WINDOWS else "unix",
            }
            if not valid:
                result["warning"] = warning_msg
            return result

        except PermissionError as e:
            return {
                "status": "error",
                "message": f"Permission denied (file may be locked by another process): {e}",
                "path": str(path),
            }
        except OSError as e:
            error_detail = ""
            if IS_WINDOWS and hasattr(e, "winerror"):
                error_codes = {
                    5: "Access denied",
                    32: "File is being used by another process",
                    123: "Invalid filename or path",
                    206: "Path too long",
                }
                error_detail = f" ({error_codes.get(e.winerror, f'Windows error {e.winerror}')})"
            return {
                "status": "error",
                "message": f"OS error{error_detail}: {e}",
                "path": str(path),
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "path": str(path)}
        finally:
            # Clean up temp file if it still exists (write failed before rename)
            if temp_path and temp_path.exists():
                try:
                    safe_delete(temp_path)
                except Exception:
                    logger.warning(f"Failed to clean up temp file: {temp_path}")

    return await asyncio.to_thread(_write_binary_sync)
