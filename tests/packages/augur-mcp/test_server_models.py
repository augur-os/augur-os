"""
Tests for server-level Pydantic models (server_models.py).

Validates input schemas, field defaults, validation constraints,
and extra field handling for all server-level MCP tool input models.

Run with: pytest tests/packages/augur-mcp/test_server_models.py -v
"""

import pytest
from pydantic import ValidationError

from src.mcp.augur_shared.server_models import (
    AnalyzeImportInput,
    ApplyImportInput,
    ExecuteFastActionInput,
    GetSprintInfoInput,
    IndexDocumentsInput,
    ListServicesInput,
    RecordVoiceInput,
    SearchDocumentsInput,
    SendIDEPromptInput,
    SyncBugsInput,
)

# =============================================================================
# ExecuteFastActionInput
# =============================================================================


class TestExecuteFastActionInput:
    """Validate ExecuteFastActionInput schema."""

    def test_valid_minimal(self):
        """Minimal valid input with just action_id."""
        inp = ExecuteFastActionInput(action_id="deploy-prod")
        assert inp.action_id == "deploy-prod"
        assert inp.args == []
        assert inp.context is None

    def test_valid_full(self):
        """Full input with all fields populated."""
        inp = ExecuteFastActionInput(
            action_id="run-tests",
            args=["--verbose", "--coverage"],
            context={"page": "career", "sprint": "S1"},
        )
        assert inp.action_id == "run-tests"
        assert inp.args == ["--verbose", "--coverage"]
        assert inp.context == {"page": "career", "sprint": "S1"}

    def test_action_id_required(self):
        """action_id is required and cannot be empty."""
        with pytest.raises(ValidationError):
            ExecuteFastActionInput(action_id="")

    def test_action_id_missing(self):
        """Omitting action_id entirely raises ValidationError."""
        with pytest.raises(ValidationError):
            ExecuteFastActionInput()

    def test_strips_whitespace(self):
        """Whitespace is stripped from action_id."""
        inp = ExecuteFastActionInput(action_id="  deploy  ")
        assert inp.action_id == "deploy"

    def test_extra_fields_allowed(self):
        """Extra fields are allowed (model_config extra='allow')."""
        inp = ExecuteFastActionInput(action_id="test", custom_field="value")
        assert inp.model_extra.get("custom_field") == "value"


# =============================================================================
# SyncBugsInput
# =============================================================================


class TestSyncBugsInput:
    """Validate SyncBugsInput schema."""

    def test_defaults(self):
        """Default force is False."""
        inp = SyncBugsInput()
        assert inp.force is False

    def test_force_true(self):
        """Can set force to True."""
        inp = SyncBugsInput(force=True)
        assert inp.force is True


# =============================================================================
# IndexDocumentsInput
# =============================================================================


class TestIndexDocumentsInput:
    """Validate IndexDocumentsInput schema."""

    def test_defaults(self):
        """Default paths is empty, force_rebuild is False."""
        inp = IndexDocumentsInput()
        assert inp.paths == []
        assert inp.force_rebuild is False

    def test_with_paths(self):
        """Can specify paths and force_rebuild."""
        inp = IndexDocumentsInput(paths=["/docs/a.md", "/docs/b.pdf"], force_rebuild=True)
        assert inp.paths == ["/docs/a.md", "/docs/b.pdf"]
        assert inp.force_rebuild is True


# =============================================================================
# SearchDocumentsInput
# =============================================================================


class TestSearchDocumentsInput:
    """Validate SearchDocumentsInput schema."""

    def test_valid_query(self):
        """Valid search with defaults."""
        inp = SearchDocumentsInput(query="architecture patterns")
        assert inp.query == "architecture patterns"
        assert inp.limit == 10
        assert inp.filters is None

    def test_query_required(self):
        """query is required."""
        with pytest.raises(ValidationError):
            SearchDocumentsInput()

    def test_query_empty_string(self):
        """Empty query string is rejected (min_length=1)."""
        with pytest.raises(ValidationError):
            SearchDocumentsInput(query="")

    def test_limit_bounds(self):
        """Limit must be between 1 and 100."""
        inp = SearchDocumentsInput(query="test", limit=1)
        assert inp.limit == 1

        inp = SearchDocumentsInput(query="test", limit=100)
        assert inp.limit == 100

        with pytest.raises(ValidationError):
            SearchDocumentsInput(query="test", limit=0)

        with pytest.raises(ValidationError):
            SearchDocumentsInput(query="test", limit=101)

    def test_with_filters(self):
        """Can provide search filters."""
        inp = SearchDocumentsInput(query="ADR", filters={"hub": "dev", "status": "active"})
        assert inp.filters == {"hub": "dev", "status": "active"}


# =============================================================================
# SendIDEPromptInput
# =============================================================================


class TestSendIDEPromptInput:
    """Validate SendIDEPromptInput schema."""

    def test_valid(self):
        """Valid prompt with context."""
        inp = SendIDEPromptInput(prompt="Implement feature X", context={"file": "main.py"})
        assert inp.prompt == "Implement feature X"
        assert inp.context == {"file": "main.py"}

    def test_prompt_required(self):
        """prompt is required and non-empty."""
        with pytest.raises(ValidationError):
            SendIDEPromptInput(prompt="")


# =============================================================================
# GetSprintInfoInput
# =============================================================================


class TestGetSprintInfoInput:
    """Validate GetSprintInfoInput schema."""

    def test_defaults(self):
        """Default sprint_id is None (active sprint)."""
        inp = GetSprintInfoInput()
        assert inp.sprint_id is None

    def test_specific_sprint(self):
        """Can specify a sprint_id."""
        inp = GetSprintInfoInput(sprint_id="sprint-42")
        assert inp.sprint_id == "sprint-42"


# =============================================================================
# ListServicesInput
# =============================================================================


class TestListServicesInput:
    """Validate ListServicesInput schema."""

    def test_defaults(self):
        """Default status_filter is None (all services)."""
        inp = ListServicesInput()
        assert inp.status_filter is None

    def test_with_filter(self):
        """Can filter by status."""
        inp = ListServicesInput(status_filter="running")
        assert inp.status_filter == "running"


# =============================================================================
# RecordVoiceInput
# =============================================================================


class TestRecordVoiceInput:
    """Validate RecordVoiceInput schema."""

    def test_defaults(self):
        """Default duration is None, transcribe is True."""
        inp = RecordVoiceInput()
        assert inp.duration is None
        assert inp.transcribe is True

    def test_with_duration(self):
        """Can specify duration and disable transcription."""
        inp = RecordVoiceInput(duration=30, transcribe=False)
        assert inp.duration == 30
        assert inp.transcribe is False


# =============================================================================
# AnalyzeImportInput
# =============================================================================


class TestAnalyzeImportInput:
    """Validate AnalyzeImportInput schema."""

    def test_valid(self):
        """Valid import analysis request."""
        inp = AnalyzeImportInput(file_path="/tmp/data.csv")
        assert inp.file_path == "/tmp/data.csv"
        assert inp.import_type is None

    def test_file_path_required(self):
        """file_path is required and non-empty."""
        with pytest.raises(ValidationError):
            AnalyzeImportInput(file_path="")

    def test_with_import_type(self):
        """Can specify import_type."""
        inp = AnalyzeImportInput(file_path="/tmp/data.csv", import_type="notion")
        assert inp.import_type == "notion"


# =============================================================================
# ApplyImportInput
# =============================================================================


class TestApplyImportInput:
    """Validate ApplyImportInput schema."""

    def test_valid(self):
        """Valid import apply request."""
        inp = ApplyImportInput(file_path="/tmp/export.zip", destination="career/data")
        assert inp.file_path == "/tmp/export.zip"
        assert inp.destination == "career/data"
        assert inp.metadata is None

    def test_both_paths_required(self):
        """Both file_path and destination are required."""
        with pytest.raises(ValidationError):
            ApplyImportInput(file_path="/tmp/export.zip")

        with pytest.raises(ValidationError):
            ApplyImportInput(destination="career/data")

    def test_empty_paths_rejected(self):
        """Empty strings for required paths are rejected (min_length=1)."""
        with pytest.raises(ValidationError):
            ApplyImportInput(file_path="", destination="career/data")

    def test_with_metadata(self):
        """Can provide import metadata."""
        inp = ApplyImportInput(
            file_path="/tmp/data.json",
            destination="finance/data",
            metadata={"source": "notion", "imported_at": "2026-01-01"},
        )
        assert inp.metadata["source"] == "notion"
