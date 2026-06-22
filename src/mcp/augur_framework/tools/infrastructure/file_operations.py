"""Implementation functions for file list, search, batch-read, info, move, and edit.

This module contains the async implementation functions for listing, searching,
batch-reading, inspecting, moving, and editing files. Read and write operations
are in file_rw.py.

These are called by the MCP tool handlers in files.py.
"""

import asyncio
import difflib
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from src.mcp.augur_shared.logging import get_entity_logger

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

# Re-export read/write functions for backward compatibility
from .file_rw import (  # noqa: F401
    read_file_impl,
    write_binary_file_impl,
    write_file_impl,
)

logger = get_entity_logger("mcp.files")


async def list_directory_impl(
    path: Path,
    pattern: str = "*",
    recursive: bool = False,
    include_hidden: bool = False,
    limit: int = 500,
) -> dict[str, Any]:
    """
    List directory contents with glob support.
    """

    def _list_sync() -> dict[str, Any]:
        if not path.exists():
            return {"status": "error", "message": f"Directory not found: {path}"}

        if not path.is_dir():
            return {"status": "error", "message": f"Not a directory: {path}"}

        try:
            entries = []
            glob_method = path.rglob if recursive else path.glob

            for item in glob_method(pattern):
                # Skip hidden files if not requested
                if not include_hidden and item.name.startswith("."):
                    continue

                try:
                    stat = item.stat()
                    entries.append(
                        {
                            "name": item.relative_to(path).as_posix(),
                            "type": "directory" if item.is_dir() else "file",
                            "size": stat.st_size if item.is_file() else None,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        }
                    )
                except (OSError, PermissionError):
                    continue

                if len(entries) >= limit:
                    break

            # Sort: directories first, then by name
            entries.sort(key=lambda x: (x["type"] != "directory", str(x["name"]).lower()))

            return {
                "status": "success",
                "entries": entries[:limit],
                "total_count": len(entries),
                "path": str(path),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return await asyncio.to_thread(_list_sync)


async def search_files_impl(
    path: Path,
    pattern: str,
    glob_filter: str = "*",
    case_sensitive: bool = True,
    context_lines: int = 0,
    max_results: int = 100,
) -> dict[str, Any]:
    """
    Search file contents using regex.

    Uses native Python regex for portability and no subprocess overhead.
    """

    def _search_sync() -> dict[str, Any]:
        if not path.exists():
            return {"status": "error", "message": f"Path not found: {path}"}

        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
        except re.error as e:
            return {"status": "error", "message": f"Invalid regex: {e}"}

        matches = []
        files_searched = 0

        try:
            search_path = path if path.is_dir() else path.parent
            search_pattern = glob_filter if path.is_dir() else path.name

            for file_path in search_path.rglob(search_pattern):
                if not file_path.is_file():
                    continue

                # Skip binary files
                if file_path.suffix.lower() in {".pyc", ".exe", ".dll", ".so", ".dylib", ".bin", ".dat"}:
                    continue

                files_searched += 1

                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()

                    for i, line in enumerate(lines):
                        if regex.search(line):
                            match_entry = {
                                "file": file_path.relative_to(search_path).as_posix(),
                                "line": i + 1,
                                "content": line.rstrip(),
                            }

                            if context_lines > 0:
                                start = max(0, i - context_lines)
                                end = min(len(lines), i + context_lines + 1)
                                match_entry["context"] = [ln.rstrip() for ln in lines[start:end]]

                            matches.append(match_entry)

                            if len(matches) >= max_results:
                                return {
                                    "status": "success",
                                    "matches": matches,
                                    "total_matches": len(matches),
                                    "files_searched": files_searched,
                                    "truncated": True,
                                }
                except (OSError, UnicodeDecodeError):
                    continue

            return {
                "status": "success",
                "matches": matches,
                "total_matches": len(matches),
                "files_searched": files_searched,
                "truncated": False,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return await asyncio.to_thread(_search_sync)


async def read_files_batch_impl(
    files: list[dict],
    default_repo: str,
    fail_fast: bool = False,
) -> dict[str, Any]:
    """
    Read multiple files in parallel.
    """
    from .file_platform import resolve_secure_path

    async def read_one(spec: dict) -> dict[str, Any]:
        try:
            resolved_path, detected_repo = resolve_secure_path(
                spec["path"],
                spec.get("repo", default_repo),
            )
            result = await read_file_impl(
                resolved_path,
                offset=spec.get("offset", 0),
                limit=spec.get("limit", 2000),
            )
            result["requested_path"] = spec["path"]
            result["repo"] = detected_repo
            return result
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "requested_path": spec["path"],
            }

    if fail_fast:
        results = []
        for spec in files:
            result = await read_one(spec)
            results.append(result)
            if result["status"] == "error":
                break
    else:
        results = await asyncio.gather(*[read_one(spec) for spec in files])

    success_count = sum(1 for r in results if r.get("status") == "success")

    return {
        "status": "success" if success_count == len(files) else "partial",
        "results": list(results),
        "success_count": success_count,
        "error_count": len(results) - success_count,
    }


async def file_info_impl(path: Path) -> dict[str, Any]:
    """Get file or directory metadata."""

    def _info_sync() -> dict[str, Any]:
        if not path.exists():
            return {
                "status": "success",
                "exists": False,
                "path": str(path),
            }

        try:
            stat = path.stat()
            file_type = "directory" if path.is_dir() else "file"
            return {
                "status": "success",
                "exists": True,
                "path": str(path),
                "type": file_type,
                "isFile": file_type == "file",
                "isDirectory": file_type == "directory",
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "permissions": oct(stat.st_mode)[-3:],
                "is_symlink": path.is_symlink(),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return await asyncio.to_thread(_info_sync)


async def move_file_impl(
    source: Path,
    destination: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Move or rename a file/directory.

    Includes Windows support with retry logic for locked files.
    """

    def _move_sync() -> dict[str, Any]:
        # Normalize paths for Windows long path support
        src_normalized = normalize_path(source)
        dst_normalized = normalize_path(destination)

        if not src_normalized.exists():
            return {"status": "error", "message": f"Source not found: {source}"}

        # Security: Validate BOTH source AND destination are within allowed roots
        try:
            validate_path_within_roots(src_normalized)
        except PermissionError as e:
            return {"status": "error", "message": f"Source {e}"}

        try:
            validate_path_within_roots(dst_normalized)
        except PermissionError as e:
            return {"status": "error", "message": f"Destination {e}"}

        if dst_normalized.exists() and not overwrite:
            return {"status": "error", "message": f"Destination already exists: {destination}"}

        try:
            # Create destination parent directories if needed
            dst_normalized.parent.mkdir(parents=True, exist_ok=True)

            # Use safe_rename which handles Windows retry and cross-device moves
            safe_rename(src_normalized, dst_normalized)

            return {
                "status": "success",
                "ok": True,
                "source": str(source),
                "destination": str(destination),
                "oldPath": str(source),
                "newPath": str(destination),
                "platform": "windows" if IS_WINDOWS else "unix",
            }

        except PermissionError as e:
            return {
                "status": "error",
                "message": f"Permission denied (file may be locked): {e}",
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
            return {"status": "error", "message": f"OS error{error_detail}: {e}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return await asyncio.to_thread(_move_sync)


async def delete_file_impl(path: Path) -> dict[str, Any]:
    """
    Delete a single file.

    Only files are allowed — directories are rejected.
    Uses safe_delete for Windows retry support.

    Args:
        path: Resolved path to the file to delete

    Returns:
        dict with status and deleted path
    """

    def _delete_sync() -> dict[str, Any]:
        normalized_path = normalize_path(path)

        if not normalized_path.exists():
            return {"status": "error", "message": f"File not found: {path}"}

        if normalized_path.is_dir():
            return {"status": "error", "message": f"Cannot delete directory (only files allowed): {path}"}

        if not normalized_path.is_file():
            return {"status": "error", "message": f"Not a regular file: {path}"}

        try:
            size = normalized_path.stat().st_size
            safe_delete(normalized_path)
            return {
                "status": "success",
                "path": str(path),
                "size": size,
                "platform": "windows" if IS_WINDOWS else "unix",
            }
        except PermissionError as e:
            return {
                "status": "error",
                "message": f"Permission denied (file may be locked): {e}",
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
            return {"status": "error", "message": f"OS error{error_detail}: {e}", "path": str(path)}
        except Exception as e:
            return {"status": "error", "message": str(e), "path": str(path)}

    return await asyncio.to_thread(_delete_sync)


async def edit_file_impl(
    path: Path,
    edits: list[dict],
    dry_run: bool = False,
    create_backup: bool = True,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    """
    Edit file with pattern matching and optional dry-run preview.

    Features:
    - Multiple edits in a single operation
    - Dry-run mode for previewing changes
    - Git-style unified diff output
    - Automatic backup before changes
    - Windows-safe file operations

    Args:
        path: File to edit
        edits: List of {old_text, new_text} operations
        dry_run: If True, preview changes without applying
        create_backup: Create .bak backup before editing
        encoding: File encoding

    Returns:
        dict with status, diff, and match information
    """

    def _edit_sync() -> dict[str, Any]:
        # Normalize path for Windows long path support
        normalized_path = normalize_path(path)
        safe_encoding = get_safe_encoding(encoding)

        if not normalized_path.exists():
            return {"status": "error", "message": f"File not found: {path}"}

        if not normalized_path.is_file():
            return {"status": "error", "message": f"Not a file: {path}"}

        # Read original content
        def _read_file():
            with open(normalized_path, encoding=safe_encoding, errors="replace") as f:
                return f.read()

        try:
            if IS_WINDOWS:
                original_content = retry_on_windows_error(_read_file, max_retries=3)
            else:
                original_content = _read_file()
        except Exception as e:
            return {"status": "error", "message": f"Failed to read file: {e}"}

        # Apply edits
        modified_content = original_content
        edit_results = []

        for i, edit in enumerate(edits):
            old_text = edit["old_text"]
            new_text = edit["new_text"]

            # Count occurrences
            count = modified_content.count(old_text)

            if count == 0:
                edit_results.append(
                    {
                        "edit_index": i,
                        "old_text_preview": old_text[:50] + "..." if len(old_text) > 50 else old_text,
                        "status": "not_found",
                        "matches": 0,
                    }
                )
            elif count > 1:
                edit_results.append(
                    {
                        "edit_index": i,
                        "old_text_preview": old_text[:50] + "..." if len(old_text) > 50 else old_text,
                        "status": "multiple_matches",
                        "matches": count,
                        "warning": "Use more specific text to avoid ambiguity",
                    }
                )
                # Still apply the edit (replace all occurrences)
                modified_content = modified_content.replace(old_text, new_text)
            else:
                modified_content = modified_content.replace(old_text, new_text, 1)
                edit_results.append(
                    {
                        "edit_index": i,
                        "old_text_preview": old_text[:50] + "..." if len(old_text) > 50 else old_text,
                        "status": "applied",
                        "matches": 1,
                    }
                )

        # Generate unified diff
        original_lines = original_content.splitlines(keepends=True)
        modified_lines = modified_content.splitlines(keepends=True)

        diff = list(
            difflib.unified_diff(
                original_lines,
                modified_lines,
                fromfile=f"a/{path.name}",
                tofile=f"b/{path.name}",
                lineterm="",
            )
        )
        diff_text = "".join(diff)

        # Check if any changes were made
        changes_made = original_content != modified_content
        edits_applied = sum(1 for r in edit_results if r["status"] == "applied")
        edits_failed = sum(1 for r in edit_results if r["status"] == "not_found")

        if dry_run:
            return {
                "status": "dry_run",
                "changes_made": changes_made,
                "edits_applied": edits_applied,
                "edits_failed": edits_failed,
                "edit_results": edit_results,
                "diff": diff_text,
                "path": str(path),
                "platform": "windows" if IS_WINDOWS else "unix",
            }

        if not changes_made:
            return {
                "status": "no_changes",
                "message": "No edits were applied (patterns not found or no changes needed)",
                "edits_applied": edits_applied,
                "edits_failed": edits_failed,
                "edit_results": edit_results,
                "path": str(path),
            }

        # Apply changes
        backup_path = None
        try:
            # Create backup if requested
            if create_backup:
                backup_path = normalized_path.with_suffix(normalized_path.suffix + ".bak")
                safe_copy(normalized_path, backup_path)

            # Write modified content using atomic write
            temp_path = normalized_path.with_suffix(normalized_path.suffix + f".tmp.{os.getpid()}.{time.time_ns()}")

            def _do_write():
                with open(temp_path, "w", encoding=encoding, newline="") as f:
                    f.write(modified_content)
                    f.flush()
                    if IS_WINDOWS:
                        os.fsync(f.fileno())

            try:
                if IS_WINDOWS:
                    retry_on_windows_error(_do_write, max_retries=3)
                else:
                    _do_write()

                safe_rename(temp_path, normalized_path)

            finally:
                # Clean up temp file if it exists
                if temp_path.exists():
                    try:
                        safe_delete(temp_path)
                    except Exception as e:
                        logger.debug(f"Failed to clean up temp file {temp_path}: {e}")

            return {
                "status": "success",
                "changes_made": True,
                "edits_applied": edits_applied,
                "edits_failed": edits_failed,
                "edit_results": edit_results,
                "diff": diff_text,
                "backup_path": str(backup_path) if backup_path else None,
                "path": str(path),
                "platform": "windows" if IS_WINDOWS else "unix",
            }

        except PermissionError as e:
            return {
                "status": "error",
                "message": f"Permission denied (file may be locked): {e}",
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

    return await asyncio.to_thread(_edit_sync)
