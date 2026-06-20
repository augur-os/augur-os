"""
File Access tools - direct file operations within augur repos.

This module provides fast, secure file access for Claude Code to read/write
files directly within the augur and augur repositories.

## Tools

- `file-read`: Read file content with pagination
- `file-write`: Write file with atomic writes and backup
- `file-list`: List directory contents with glob patterns
- `file-search`: Search file contents with regex
- `file-read-multi`: Batch read multiple files in parallel
- `file-info`: Get file/directory metadata
- `file-move`: Move or rename files/directories
- `file-delete`: Delete a file within allowed repos
- `file-edit`: Edit file with pattern matching and dry-run preview
- `file-write-binary`: Write binary content (base64-encoded) with atomic writes

## Security

All paths are sandboxed to augur/ and augur/ repos only.
Directory traversal attacks are prevented via resolve() + relative_to().

## Module Structure

This module delegates to focused sub-modules:
- `file_models.py`: Pydantic input models
- `file_platform.py`: Platform detection, Windows utilities, security layer
- `file_assets.py`: Binary asset helpers, skill content matching
- `file_operations.py`: Async implementation functions (read, write, etc.)
"""

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from src.mcp.augur_shared.annotations import tool_annotations

# Re-export everything from sub-modules for backward compatibility
from .file_assets import (  # noqa: F401
    _ASSET_SUBFOLDER_MAP,
    _MAGIC_BYTES,
    _guess_mime_type,
    _suggest_asset_subfolder,
    _validate_asset_magic_bytes,
)
from .file_models import (  # noqa: F401
    MAX_BINARY_SIZE,
    EditOperation,
    FileDeleteInput,
    FileEditInput,
    FileInfoInput,
    FileListInput,
    FileMoveInput,
    FileReadInput,
    FileReadMultiInput,
    FileSearchInput,
    FileSpec,
    FileWriteBinaryInput,
    FileWriteInput,
    RepoTarget,
    ResolveAssetPathInput,
)
from .file_operations import (  # noqa: F401
    delete_file_impl,
    edit_file_impl,
    file_info_impl,
    list_directory_impl,
    move_file_impl,
    read_file_impl,
    read_files_batch_impl,
    search_files_impl,
    write_binary_file_impl,
    write_file_impl,
)
from .file_platform import (  # noqa: F401
    IS_WINDOWS,
    WINDOWS_LONG_PATH_PREFIX,
    WINDOWS_MAX_PATH,
    get_allowed_roots,
    get_safe_encoding,
    normalize_path,
    resolve_secure_path,
    retry_on_windows_error,
    safe_copy,
    safe_delete,
    safe_rename,
    validate_path_within_roots,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# =============================================================================
# Tool Registration
# =============================================================================


def register_file_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register File Access tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """

    @mcp.tool(
        name="file-read",
        annotations=tool_annotations(
            {
                "title": "Read File Content",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def file_read_tool(params: FileReadInput) -> str:
        """Read file content with optional pagination.

        Reads files from augur (code) or augur (data) repos.
        Supports line offset/limit for efficient large file handling.
        Set binary=True to read non-text files (images, PDFs, etc.) as base64.

        Args:
            params: FileReadInput with path, repo, offset, limit, encoding, binary

        Returns:
            str: JSON with file content and metadata
        """
        metrics.track_tool("file_read")

        try:
            resolved_path, detected_repo = resolve_secure_path(params.path, params.repo.value)
            result = await read_file_impl(
                resolved_path,
                offset=params.offset,
                limit=params.limit,
                encoding=params.encoding,
                binary=params.binary,
            )
            result["repo"] = detected_repo
            return json.dumps(result, indent=2)
        except (ValueError, PermissionError) as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool(
        name="file-write",
        annotations=tool_annotations(
            {
                "title": "Write File Content",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def file_write_tool(params: FileWriteInput) -> str:
        """Write content to file in allowed repos.

        Writes to augur or augur repos. Creates backup by default.

        Args:
            params: FileWriteInput with path, content, backup options

        Returns:
            str: JSON with write result and backup path
        """
        metrics.track_tool("file_write")

        try:
            resolved_path, detected_repo = resolve_secure_path(params.path, params.repo.value)
            result = await write_file_impl(
                resolved_path,
                params.content,
                create_backup=params.create_backup,
                create_dirs=params.create_dirs,
                append=params.append,
                encoding=params.encoding,
            )
            result["repo"] = detected_repo
            return json.dumps(result, indent=2)
        except (ValueError, PermissionError) as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool(
        name="file-write-binary",
        annotations=tool_annotations(
            {
                "title": "Write Binary File Content",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def file_write_binary_tool(params: FileWriteBinaryInput) -> str:
        """Write binary content (images, PDFs, archives) to file.

        Content must be base64-encoded. Use this for non-text files.
        For text files, use file-write instead.
        Validates magic bytes for known formats (PNG, JPG, PDF, ZIP, GIF, WEBP).
        Maximum file size: 50MB.

        Args:
            params: FileWriteBinaryInput with path, content_base64, backup options

        Returns:
            str: JSON with write result and backup path
        """
        metrics.track_tool("file_write_binary")

        try:
            resolved_path, detected_repo = resolve_secure_path(params.path, params.repo.value)
            result = await write_binary_file_impl(
                resolved_path,
                params.content_base64,
                create_backup=params.create_backup,
                create_dirs=params.create_dirs,
            )
            result["repo"] = detected_repo
            return json.dumps(result, indent=2)
        except (ValueError, PermissionError) as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool(
        name="file-list",
        annotations=tool_annotations(
            {
                "title": "List Directory Contents",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def file_list_tool(params: FileListInput) -> str:
        """List directory contents with glob patterns.

        Lists files in augur or augur directories.

        Args:
            params: FileListInput with path, pattern, recursive options

        Returns:
            str: JSON with directory entries and metadata
        """
        metrics.track_tool("file_list")

        try:
            resolved_path, detected_repo = resolve_secure_path(params.path, params.repo.value)
            result = await list_directory_impl(
                resolved_path,
                pattern=params.pattern,
                recursive=params.recursive,
                include_hidden=params.include_hidden,
                limit=params.limit,
            )
            result["repo"] = detected_repo
            return json.dumps(result, indent=2)
        except (ValueError, PermissionError) as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool(
        name="file-search",
        annotations=tool_annotations(
            {
                "title": "Search File Contents",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def file_search_tool(params: FileSearchInput) -> str:
        """Search file contents using regex pattern.

        Searches within augur or augur repos.

        Args:
            params: FileSearchInput with pattern, path, options

        Returns:
            str: JSON with search matches and metadata
        """
        metrics.track_tool("file_search")

        try:
            resolved_path, detected_repo = resolve_secure_path(params.path, params.repo.value)
            result = await search_files_impl(
                resolved_path,
                params.pattern,
                glob_filter=params.glob,
                case_sensitive=params.case_sensitive,
                context_lines=params.context_lines,
                max_results=params.max_results,
            )
            result["repo"] = detected_repo
            return json.dumps(result, indent=2)
        except (ValueError, PermissionError) as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool(
        name="file-read-multi",
        annotations=tool_annotations(
            {
                "title": "Batch Read Multiple Files",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def file_read_multi_tool(params: FileReadMultiInput) -> str:
        """Read multiple files in a single call.

        Executes reads in parallel for efficiency.

        Args:
            params: FileReadMultiInput with files list and options

        Returns:
            str: JSON with results for each file
        """
        metrics.track_tool("file_read_multi")

        try:
            file_specs = [f.model_dump() for f in params.files]
            result = await read_files_batch_impl(
                file_specs,
                default_repo=params.repo.value,
                fail_fast=params.fail_fast,
            )
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool(
        name="file-info",
        annotations=tool_annotations(
            {
                "title": "Get File Information",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def file_info_tool(params: FileInfoInput) -> str:
        """Get file or directory metadata.

        Returns detailed information without reading content.

        Args:
            params: FileInfoInput with path and repo

        Returns:
            str: JSON with file metadata
        """
        metrics.track_tool("file_info")

        try:
            resolved_path, detected_repo = resolve_secure_path(params.path, params.repo.value)
            result = await file_info_impl(resolved_path)
            result["repo"] = detected_repo
            return json.dumps(result, indent=2)
        except (ValueError, PermissionError) as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool(
        name="file-move",
        annotations=tool_annotations(
            {
                "title": "Move or Rename File",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def file_move_tool(params: FileMoveInput) -> str:
        """Move or rename a file/directory within allowed repos.

        Supports Windows with retry logic for locked files.
        Both source and destination must be within augur repos.

        Args:
            params: FileMoveInput with source, destination, repo, overwrite

        Returns:
            str: JSON with move result
        """
        metrics.track_tool("file_move")

        try:
            # Resolve both paths
            src_path, src_repo = resolve_secure_path(params.source, params.repo.value)
            dst_path, dst_repo = resolve_secure_path(params.destination, params.repo.value)

            result = await move_file_impl(
                src_path,
                dst_path,
                overwrite=params.overwrite,
            )
            result["source_repo"] = src_repo
            result["destination_repo"] = dst_repo
            return json.dumps(result, indent=2)
        except (ValueError, PermissionError) as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool(
        name="file-delete",
        annotations=tool_annotations(
            {
                "title": "Delete File",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def file_delete_tool(params: FileDeleteInput) -> str:
        """Delete a file within allowed repos.

        Only files can be deleted — directories are rejected.
        Path must be within the project root or vault.

        Args:
            params: FileDeleteInput with path and repo

        Returns:
            str: JSON with deletion result
        """
        metrics.track_tool("file_delete")

        try:
            resolved_path, detected_repo = resolve_secure_path(params.path, params.repo.value)
            result = await delete_file_impl(resolved_path)
            result["repo"] = detected_repo
            return json.dumps(result, indent=2)
        except (ValueError, PermissionError) as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool(
        name="file-edit",
        annotations=tool_annotations(
            {
                "title": "Edit File with Pattern Matching",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def file_edit_tool(params: FileEditInput) -> str:
        """Edit file using pattern matching with dry-run preview.

        Features:
        - Multiple edits in a single operation
        - Dry-run mode to preview changes without applying
        - Git-style unified diff output
        - Automatic backup before changes
        - Windows-safe with retry logic for locked files

        Args:
            params: FileEditInput with path, edits, dry_run, create_backup

        Returns:
            str: JSON with edit results, diff, and status
        """
        metrics.track_tool("file_edit")

        try:
            resolved_path, detected_repo = resolve_secure_path(params.path, params.repo.value)

            # Convert Pydantic models to dicts
            edits = [{"old_text": e.old_text, "new_text": e.new_text} for e in params.edits]

            result = await edit_file_impl(
                resolved_path,
                edits=edits,
                dry_run=params.dry_run,
                create_backup=params.create_backup,
            )
            result["repo"] = detected_repo
            return json.dumps(result, indent=2)
        except (ValueError, PermissionError) as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool(
        name="resolve-asset-path",
        annotations=tool_annotations(
            {
                "title": "Resolve Skill Asset Path",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def resolve_asset_path_tool(params: ResolveAssetPathInput) -> str:
        """Resolve the assets directory for a skill with subfolder suggestion.

        Given a skill name and optional filename, returns:
        - The absolute path to the skill's assets directory
        - Suggested subfolder based on file extension (images/, reports/, etc.)
        - Full target path if filename provided
        - Existing subdirectories in the assets folder

        Use this before file-write-binary to determine where to save an asset.

        Args:
            params: ResolveAssetPathInput with skill_name and optional filename

        Returns:
            str: JSON with assets_dir, suggested_subfolder, target_path, existing_subdirs
        """
        metrics.track_tool("resolve_asset_path")

        try:
            from src.config.paths import get_skill_assets_dir

            assets_dir = get_skill_assets_dir(params.skill_name)
        except (ImportError, ValueError) as e:
            return json.dumps({"status": "error", "message": str(e)})

        # List existing subdirectories
        existing_subdirs: list[str] = []
        if assets_dir.exists():
            existing_subdirs = sorted(d.name for d in assets_dir.iterdir() if d.is_dir() and not d.name.startswith("."))

        # Suggest subfolder based on filename
        suggested_subfolder = ""
        target_path = str(assets_dir)
        if params.filename:
            suggested_subfolder = _suggest_asset_subfolder(params.filename)
            if suggested_subfolder:
                target_path = str(assets_dir / suggested_subfolder / params.filename)
            else:
                target_path = str(assets_dir / params.filename)

        return json.dumps(
            {
                "status": "success",
                "skill_name": params.skill_name,
                "assets_dir": str(assets_dir),
                "exists": assets_dir.exists(),
                "existing_subdirs": existing_subdirs,
                "suggested_subfolder": suggested_subfolder,
                "target_path": target_path,
                "filename": params.filename,
            },
            indent=2,
        )


__all__ = ["register_file_tools"]
