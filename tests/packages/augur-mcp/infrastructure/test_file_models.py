"""
Tests for file operation Pydantic models (infrastructure/file_models.py).

Validates input schemas, field validators (path traversal rejection),
enum values, and nested model structures for all file-related MCP tools.

Run with: pytest tests/packages/augur-mcp/infrastructure/test_file_models.py -v
"""

import pytest
from pydantic import ValidationError

from src.mcp.augur_framework.tools.infrastructure.file_models import (
    EditOperation,
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
    MAX_BINARY_SIZE,
    RepoTarget,
    ResolveAssetPathInput,
)

# =============================================================================
# RepoTarget Enum
# =============================================================================


class TestRepoTarget:
    """Validate RepoTarget enum values."""

    def test_values(self):
        """All expected enum values exist."""
        assert RepoTarget.CODE == "code"
        assert RepoTarget.DATA == "data"
        assert RepoTarget.RUNTIME == "runtime"
        assert RepoTarget.AUTO == "auto"

    def test_string_enum(self):
        """RepoTarget is a string enum."""
        assert isinstance(RepoTarget.CODE, str)
        assert RepoTarget.CODE == "code"


# =============================================================================
# FileReadInput
# =============================================================================


class TestFileReadInput:
    """Validate FileReadInput schema."""

    def test_minimal_valid(self):
        """Minimal valid input with just path."""
        inp = FileReadInput(path="main.py")
        assert inp.path == "main.py"
        assert inp.repo == RepoTarget.AUTO
        assert inp.offset == 0
        assert inp.limit == 2000
        assert inp.encoding == "utf-8"
        assert inp.binary is False

    def test_path_required(self):
        """path is required."""
        with pytest.raises(ValidationError):
            FileReadInput()

    def test_path_empty_rejected(self):
        """Empty path is rejected (min_length=1)."""
        with pytest.raises(ValidationError):
            FileReadInput(path="")

    def test_offset_non_negative(self):
        """Offset must be >= 0."""
        with pytest.raises(ValidationError):
            FileReadInput(path="f.py", offset=-1)

    def test_limit_bounds(self):
        """Limit must be between 1 and 50000."""
        FileReadInput(path="f.py", limit=1)
        FileReadInput(path="f.py", limit=50000)

        with pytest.raises(ValidationError):
            FileReadInput(path="f.py", limit=0)

        with pytest.raises(ValidationError):
            FileReadInput(path="f.py", limit=50001)

    def test_extra_fields_forbidden(self):
        """Extra fields are rejected (extra='forbid')."""
        with pytest.raises(ValidationError):
            FileReadInput(path="f.py", unknown_field="value")


# =============================================================================
# FileWriteInput
# =============================================================================


class TestFileWriteInput:
    """Validate FileWriteInput schema with path traversal protection."""

    def test_valid(self):
        """Valid write input."""
        inp = FileWriteInput(path="output.txt", content="hello world")
        assert inp.path == "output.txt"
        assert inp.content == "hello world"
        assert inp.create_backup is True
        assert inp.create_dirs is True
        assert inp.append is False

    def test_append_supported(self):
        """Append flag is accepted for runtime log/chat writers."""
        inp = FileWriteInput(path="output.txt", content="hello world", append=True)
        assert inp.append is True

    def test_path_traversal_rejected(self):
        """Paths containing '..' are rejected."""
        with pytest.raises(ValidationError, match="cannot contain"):
            FileWriteInput(path="../../../etc/passwd", content="hack")

    def test_path_traversal_embedded(self):
        """Embedded '..' anywhere in path is rejected."""
        with pytest.raises(ValidationError, match="cannot contain"):
            FileWriteInput(path="a/b/../c/d.txt", content="test")

    def test_content_required(self):
        """content is required."""
        with pytest.raises(ValidationError):
            FileWriteInput(path="f.txt")


# =============================================================================
# FileWriteBinaryInput
# =============================================================================


class TestFileWriteBinaryInput:
    """Validate FileWriteBinaryInput schema."""

    def test_valid(self):
        """Valid binary write input."""
        inp = FileWriteBinaryInput(path="image.png", content_base64="aGVsbG8=")
        assert inp.path == "image.png"
        assert inp.content_base64 == "aGVsbG8="

    def test_path_traversal_rejected(self):
        """Paths containing '..' are rejected."""
        with pytest.raises(ValidationError, match="cannot contain"):
            FileWriteBinaryInput(path="../../bad.bin", content_base64="aGVsbG8=")


# =============================================================================
# MAX_BINARY_SIZE constant
# =============================================================================


class TestMaxBinarySize:
    """Validate MAX_BINARY_SIZE constant."""

    def test_value(self):
        """MAX_BINARY_SIZE is 50MB."""
        assert MAX_BINARY_SIZE == 50 * 1024 * 1024


# =============================================================================
# ResolveAssetPathInput
# =============================================================================


class TestResolveAssetPathInput:
    """Validate ResolveAssetPathInput schema."""

    def test_valid_minimal(self):
        """Minimal valid input with just skill_name."""
        inp = ResolveAssetPathInput(skill_name="venture")
        assert inp.skill_name == "venture"
        assert inp.filename is None

    def test_with_filename(self):
        """With optional filename."""
        inp = ResolveAssetPathInput(skill_name="career", filename="banner.png")
        assert inp.filename == "banner.png"

    def test_skill_name_required(self):
        """skill_name is required and non-empty."""
        with pytest.raises(ValidationError):
            ResolveAssetPathInput(skill_name="")


# MatchContentToSkillInput retired in Track 3a PR 2 (along with the
# match-content-to-skill MCP tool).


# =============================================================================
# FileListInput
# =============================================================================


class TestFileListInput:
    """Validate FileListInput schema."""

    def test_defaults(self):
        """All fields have sensible defaults."""
        inp = FileListInput()
        assert inp.path == "."
        assert inp.repo == RepoTarget.AUTO
        assert inp.pattern == "*"
        assert inp.recursive is False
        assert inp.include_hidden is False
        assert inp.limit == 500


# =============================================================================
# FileSearchInput
# =============================================================================


class TestFileSearchInput:
    """Validate FileSearchInput schema."""

    def test_valid(self):
        """Valid search input."""
        inp = FileSearchInput(pattern="def test_")
        assert inp.pattern == "def test_"
        assert inp.case_sensitive is True
        assert inp.context_lines == 0
        assert inp.max_results == 100

    def test_pattern_required(self):
        """pattern is required."""
        with pytest.raises(ValidationError):
            FileSearchInput()

    def test_context_lines_bounds(self):
        """context_lines must be between 0 and 10."""
        FileSearchInput(pattern="x", context_lines=0)
        FileSearchInput(pattern="x", context_lines=10)

        with pytest.raises(ValidationError):
            FileSearchInput(pattern="x", context_lines=11)


# =============================================================================
# FileSpec and FileReadMultiInput
# =============================================================================


class TestFileSpec:
    """Validate FileSpec schema."""

    def test_valid(self):
        """Valid file spec."""
        spec = FileSpec(path="main.py")
        assert spec.path == "main.py"
        assert spec.offset == 0
        assert spec.limit == 2000

    def test_path_required(self):
        """path is required."""
        with pytest.raises(ValidationError):
            FileSpec()


class TestFileReadMultiInput:
    """Validate FileReadMultiInput schema."""

    def test_valid(self):
        """Valid multi-read input."""
        inp = FileReadMultiInput(files=[FileSpec(path="a.py"), FileSpec(path="b.py")])
        assert len(inp.files) == 2
        assert inp.fail_fast is False

    def test_files_required_and_nonempty(self):
        """files list must have at least 1 entry."""
        with pytest.raises(ValidationError):
            FileReadMultiInput(files=[])

    def test_files_max_length(self):
        """files list has max_length=20."""
        specs = [FileSpec(path=f"file_{i}.py") for i in range(21)]
        with pytest.raises(ValidationError):
            FileReadMultiInput(files=specs)


# =============================================================================
# FileInfoInput
# =============================================================================


class TestFileInfoInput:
    """Validate FileInfoInput schema."""

    def test_valid(self):
        """Valid file info input."""
        inp = FileInfoInput(path="src/main.py")
        assert inp.path == "src/main.py"
        assert inp.repo == RepoTarget.AUTO


# =============================================================================
# FileMoveInput
# =============================================================================


class TestFileMoveInput:
    """Validate FileMoveInput schema with path traversal protection."""

    def test_valid(self):
        """Valid move input."""
        inp = FileMoveInput(source="old.txt", destination="new.txt")
        assert inp.source == "old.txt"
        assert inp.destination == "new.txt"
        assert inp.overwrite is False

    def test_source_traversal_rejected(self):
        """Source paths with '..' are rejected."""
        with pytest.raises(ValidationError, match="cannot contain"):
            FileMoveInput(source="../bad.txt", destination="new.txt")

    def test_destination_traversal_rejected(self):
        """Destination paths with '..' are rejected."""
        with pytest.raises(ValidationError, match="cannot contain"):
            FileMoveInput(source="old.txt", destination="../../bad.txt")


# =============================================================================
# EditOperation and FileEditInput
# =============================================================================


class TestEditOperation:
    """Validate EditOperation schema."""

    def test_valid(self):
        """Valid edit operation."""
        op = EditOperation(old_text="foo", new_text="bar")
        assert op.old_text == "foo"
        assert op.new_text == "bar"

    def test_old_text_required(self):
        """old_text has min_length=1."""
        with pytest.raises(ValidationError):
            EditOperation(old_text="", new_text="bar")

    def test_new_text_can_be_empty(self):
        """new_text can be empty (deletion)."""
        op = EditOperation(old_text="remove-this", new_text="")
        assert op.new_text == ""


class TestFileEditInput:
    """Validate FileEditInput schema."""

    def test_valid(self):
        """Valid edit input."""
        inp = FileEditInput(
            path="main.py",
            edits=[EditOperation(old_text="old", new_text="new")],
        )
        assert inp.path == "main.py"
        assert len(inp.edits) == 1
        assert inp.dry_run is False
        assert inp.create_backup is True

    def test_path_traversal_rejected(self):
        """Path traversal is rejected."""
        with pytest.raises(ValidationError, match="cannot contain"):
            FileEditInput(
                path="../../../etc/shadow",
                edits=[EditOperation(old_text="a", new_text="b")],
            )

    def test_edits_required_nonempty(self):
        """At least one edit is required."""
        with pytest.raises(ValidationError):
            FileEditInput(path="f.py", edits=[])

    def test_edits_max_length(self):
        """Maximum 50 edits per request."""
        edits = [EditOperation(old_text=f"old{i}", new_text=f"new{i}") for i in range(51)]
        with pytest.raises(ValidationError):
            FileEditInput(path="f.py", edits=edits)
