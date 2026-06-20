"""Pydantic input models for file access MCP tools.

These models define the validated input schemas for all file-related
MCP tool endpoints (file-read, file-write, file-list, etc.).
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RepoTarget(str, Enum):
    """Target repository for file operations."""

    CODE = "code"
    DATA = "data"
    RUNTIME = "runtime"
    AUTO = "auto"


class FileReadInput(BaseModel):
    """Input for file-read tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to file (relative or absolute within allowed repos)", min_length=1)
    repo: RepoTarget = Field(default=RepoTarget.AUTO, description="Target repo: code, data, or auto")
    offset: int = Field(default=0, ge=0, description="Line offset to start reading from (0-indexed)")
    limit: int = Field(default=2000, ge=1, le=50000, description="Maximum lines to return")
    encoding: str = Field(default="utf-8", description="File encoding")
    binary: bool = Field(default=False, description="If True, read file as binary and return base64-encoded content")


class FileWriteInput(BaseModel):
    """Input for file-write tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to file (relative or absolute within allowed repos)", min_length=1)
    content: str = Field(..., description="Content to write")
    repo: RepoTarget = Field(default=RepoTarget.AUTO, description="Target repo: code, data, or auto")
    create_backup: bool = Field(default=True, description="Create .bak backup before overwrite")
    create_dirs: bool = Field(default=True, description="Create parent directories if missing")
    append: bool = Field(default=False, description="Append content to the existing file instead of replacing it")
    encoding: str = Field(default="utf-8", description="File encoding")

    @field_validator("path")
    @classmethod
    def validate_path_no_traversal(cls, v: str) -> str:
        """Reject obvious traversal attempts early."""
        if ".." in v:
            raise ValueError("Path cannot contain '..'")
        return v


# Maximum binary file size: 50MB
MAX_BINARY_SIZE = 50 * 1024 * 1024


class FileWriteBinaryInput(BaseModel):
    """Input for file-write-binary tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Target file path (within allowed repos)", min_length=1)
    content_base64: str = Field(..., description="Base64-encoded binary content")
    repo: RepoTarget = Field(default=RepoTarget.AUTO, description="Target repo: code, data, or auto")
    create_backup: bool = Field(default=True, description="Create .bak backup before overwrite")
    create_dirs: bool = Field(default=True, description="Create parent directories if missing")

    @field_validator("path")
    @classmethod
    def validate_path_no_traversal(cls, v: str) -> str:
        """Reject obvious traversal attempts early."""
        if ".." in v:
            raise ValueError("Path cannot contain '..'")
        return v


class ResolveAssetPathInput(BaseModel):
    """Input for resolve-asset-path tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    skill_name: str = Field(..., description="Skill name (e.g., 'venture', 'career', 'finance')", min_length=1)
    filename: str | None = Field(
        default=None,
        description="Optional filename to save (e.g., 'banner.png'). "
        "Used to auto-detect the asset subfolder (images/, reports/, etc.)",
    )


class FileListInput(BaseModel):
    """Input for file-list tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(default=".", description="Directory path")
    repo: RepoTarget = Field(default=RepoTarget.AUTO, description="Target repo: code, data, or auto")
    pattern: str = Field(default="*", description="Glob pattern to filter files")
    recursive: bool = Field(default=False, description="Recurse into subdirectories")
    include_hidden: bool = Field(default=False, description="Include hidden files (starting with .)")
    limit: int = Field(default=500, ge=1, le=5000, description="Maximum entries to return")


class FileSearchInput(BaseModel):
    """Input for file-search tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    pattern: str = Field(..., description="Regex pattern to search for", min_length=1)
    path: str = Field(default=".", description="Starting directory path")
    repo: RepoTarget = Field(default=RepoTarget.AUTO, description="Target repo: code, data, or auto")
    glob: str = Field(default="*", description="File glob pattern filter")
    case_sensitive: bool = Field(default=True, description="Case-sensitive search")
    context_lines: int = Field(default=0, ge=0, le=10, description="Lines of context around matches")
    max_results: int = Field(default=100, ge=1, le=1000, description="Maximum results to return")


class FileSpec(BaseModel):
    """Single file specification for multi-read."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="File path", min_length=1)
    offset: int = Field(default=0, ge=0, description="Line offset")
    limit: int = Field(default=2000, ge=1, le=50000, description="Max lines")


class FileReadMultiInput(BaseModel):
    """Input for file-read-multi tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    files: list[FileSpec] = Field(..., description="Files to read", min_length=1, max_length=20)
    repo: RepoTarget = Field(default=RepoTarget.AUTO, description="Default repo for relative paths")
    fail_fast: bool = Field(default=False, description="Stop on first error")


class FileInfoInput(BaseModel):
    """Input for file-info tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to file or directory", min_length=1)
    repo: RepoTarget = Field(default=RepoTarget.AUTO, description="Target repo: code, data, or auto")


class FileMoveInput(BaseModel):
    """Input for file-move tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    source: str = Field(default="", description="Source file or directory path")
    destination: str = Field(default="", description="Destination path")
    repo: RepoTarget = Field(default=RepoTarget.AUTO, description="Target repo: code, data, or auto")
    overwrite: bool = Field(default=False, description="Overwrite destination if exists")
    # Dashboard aliases
    oldPath: str | None = Field(default=None, description="Alias for source (dashboard param name)")
    newPath: str | None = Field(default=None, description="Alias for destination (dashboard param name)")

    @field_validator("source", "destination")
    @classmethod
    def validate_path_no_traversal(cls, v: str) -> str:
        """Reject obvious traversal attempts early."""
        if v and ".." in v:
            raise ValueError("Path cannot contain '..'")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Resolve dashboard aliases."""
        if not self.source and self.oldPath:
            self.source = self.oldPath
        if not self.destination and self.newPath:
            self.destination = self.newPath
        if not self.source:
            raise ValueError("source (or oldPath) is required")
        if not self.destination:
            raise ValueError("destination (or newPath) is required")


class EditOperation(BaseModel):
    """Single edit operation for file-edit tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    old_text: str = Field(..., description="Text to search for (exact match or substring)", min_length=1)
    new_text: str = Field(..., description="Text to replace with")


class FileDeleteInput(BaseModel):
    """Input for file-delete tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(
        ..., description="Path to file to delete (relative or absolute within allowed repos)", min_length=1
    )
    repo: RepoTarget = Field(default=RepoTarget.AUTO, description="Target repo: code, data, or auto")

    @field_validator("path")
    @classmethod
    def validate_path_no_traversal(cls, v: str) -> str:
        """Reject obvious traversal attempts early."""
        if ".." in v:
            raise ValueError("Path cannot contain '..'")
        return v


class FileEditInput(BaseModel):
    """Input for file-edit tool."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to file to edit", min_length=1)
    edits: list[EditOperation] = Field(..., description="List of edit operations", min_length=1, max_length=50)
    repo: RepoTarget = Field(default=RepoTarget.AUTO, description="Target repo: code, data, or auto")
    dry_run: bool = Field(default=False, description="Preview changes without applying")
    create_backup: bool = Field(default=True, description="Create .bak backup before editing")

    @field_validator("path")
    @classmethod
    def validate_path_no_traversal(cls, v: str) -> str:
        """Reject obvious traversal attempts early."""
        if ".." in v:
            raise ValueError("Path cannot contain '..'")
        return v
