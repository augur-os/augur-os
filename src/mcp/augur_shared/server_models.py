"""
Server-level Pydantic models for MCP tool inputs.

These models are used by infrastructure tools registered directly in server.py.
Core skill models (ListSkillsInput, etc.) live in augur_mcp.core.models.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecuteFastActionInput(BaseModel):
    """Input for executing fast action buttons."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    action_id: str = Field(..., description="Action button ID to execute", min_length=1)
    args: list[str] = Field(default=[], description="Additional arguments for the action")
    context: dict[str, Any] | None = Field(default=None, description="Request context (page, sprint, etc.)")


class SyncBugsInput(BaseModel):
    """Input for syncing bugs to GitHub."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    force: bool = Field(default=False, description="Force sync even if recently synced")


class IndexDocumentsInput(BaseModel):
    """Input for indexing documents."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    paths: list[str] = Field(default=[], description="Specific paths to index (empty = all)")
    force_rebuild: bool = Field(default=False, description="Force rebuild of index")


class SearchDocumentsInput(BaseModel):
    """Input for searching documents."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    query: str = Field(..., description="Search query", min_length=1)
    limit: int = Field(default=10, description="Maximum results", ge=1, le=100)
    filters: dict[str, Any] | None = Field(default=None, description="Search filters")


class SendIDEPromptInput(BaseModel):
    """Input for sending prompt to IDE."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    prompt: str = Field(..., description="Prompt to send to IDE", min_length=1)
    context: dict[str, Any] | None = Field(default=None, description="Additional context")


class GetSprintInfoInput(BaseModel):
    """Input for getting sprint information."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    sprint_id: str | None = Field(default=None, description="Specific sprint ID (None = active)")


class ListServicesInput(BaseModel):
    """Input for listing running services."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    status_filter: str | None = Field(default=None, description="Filter by status (running/stopped)")


class RecordVoiceInput(BaseModel):
    """Input for recording voice note."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    duration: int | None = Field(default=None, description="Recording duration in seconds")
    transcribe: bool = Field(default=True, description="Auto-transcribe recording")


class AnalyzeImportInput(BaseModel):
    """Input for analyzing document import."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    file_path: str = Field(..., description="Path to file to analyze", min_length=1)
    import_type: str | None = Field(default=None, description="Type of import (auto-detect if None)")


class ApplyImportInput(BaseModel):
    """Input for applying document import."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    file_path: str = Field(..., description="Path to file to import", min_length=1)
    destination: str = Field(..., description="Destination path in data repo", min_length=1)
    metadata: dict[str, Any] | None = Field(default=None, description="Import metadata")
