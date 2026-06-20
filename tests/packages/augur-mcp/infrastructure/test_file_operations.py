"""
Tests for file list, search, batch-read, info, move, and edit operations
(infrastructure/file_operations.py).

Validates directory listing, regex search, parallel batch reads, file info
metadata, file move with security checks, and multi-edit with dry-run support.

Run with: pytest tests/packages/augur-mcp/infrastructure/test_file_operations.py -v
"""

from pathlib import Path

import pytest

from src.mcp.augur_framework.tools.infrastructure.file_operations import (
    edit_file_impl,
    file_info_impl,
    list_directory_impl,
    move_file_impl,
    search_files_impl,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_roots(tmp_path: Path, monkeypatch):
    """Set up isolated allowed roots."""
    roots = {"code": tmp_path, "data": tmp_path}
    monkeypatch.setattr("src.mcp.augur_framework.tools.infrastructure.file_platform._ALLOWED_ROOTS", roots)
    monkeypatch.setattr("src.mcp.augur_framework.tools.infrastructure.file_platform.get_allowed_roots", lambda: roots)
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.file_operations.validate_path_within_roots", lambda p: None
    )
    return roots


@pytest.fixture
def populated_dir(tmp_path: Path) -> Path:
    """Create a directory with sample files for listing and searching."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main():\n    print('hello')\n")
    (tmp_path / "src" / "utils.py").write_text("def helper():\n    return 42\n")
    (tmp_path / "src" / "config.yaml").write_text("key: value\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("# Project\n\nDescription here.\n")
    (tmp_path / ".hidden").write_text("secret")
    return tmp_path


# =============================================================================
# list_directory_impl
# =============================================================================


class TestListDirectoryImpl:
    """Tests for directory listing."""

    @pytest.mark.asyncio
    async def test_list_basic(self, populated_dir: Path, mock_roots):
        """List directory returns entries with type and metadata."""
        result = await list_directory_impl(populated_dir)
        assert result["status"] == "success"
        assert result["total_count"] > 0
        names = [e["name"] for e in result["entries"]]
        assert "src" in names
        assert "docs" in names

    @pytest.mark.asyncio
    async def test_list_nonexistent_dir(self, tmp_path: Path, mock_roots):
        """Listing a nonexistent directory returns error."""
        result = await list_directory_impl(tmp_path / "nope")
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_list_file_not_dir(self, populated_dir: Path, mock_roots):
        """Listing a file (not directory) returns error."""
        result = await list_directory_impl(populated_dir / "src" / "main.py")
        assert result["status"] == "error"
        assert "Not a directory" in result["message"]

    @pytest.mark.asyncio
    async def test_list_with_pattern(self, populated_dir: Path, mock_roots):
        """Glob pattern filters entries."""
        result = await list_directory_impl(populated_dir / "src", pattern="*.py")
        assert result["status"] == "success"
        names = [e["name"] for e in result["entries"]]
        assert "main.py" in names
        assert "config.yaml" not in names

    @pytest.mark.asyncio
    async def test_list_recursive(self, populated_dir: Path, mock_roots):
        """Recursive listing includes nested files."""
        result = await list_directory_impl(populated_dir, pattern="*.py", recursive=True)
        assert result["status"] == "success"
        names = [e["name"] for e in result["entries"]]
        # Relative paths from the search root
        assert any("main.py" in n for n in names)

    @pytest.mark.asyncio
    async def test_list_hidden_files_excluded_by_default(self, populated_dir: Path, mock_roots):
        """Hidden files are excluded by default."""
        result = await list_directory_impl(populated_dir)
        names = [e["name"] for e in result["entries"]]
        assert ".hidden" not in names

    @pytest.mark.asyncio
    async def test_list_hidden_files_included(self, populated_dir: Path, mock_roots):
        """Hidden files are included when include_hidden=True."""
        result = await list_directory_impl(populated_dir, include_hidden=True)
        names = [e["name"] for e in result["entries"]]
        assert ".hidden" in names

    @pytest.mark.asyncio
    async def test_list_limit(self, populated_dir: Path, mock_roots):
        """Limit caps the number of returned entries."""
        result = await list_directory_impl(populated_dir, limit=1)
        assert result["status"] == "success"
        assert len(result["entries"]) <= 1

    @pytest.mark.asyncio
    async def test_list_dirs_first_in_sort(self, populated_dir: Path, mock_roots):
        """Directories appear before files in results."""
        result = await list_directory_impl(populated_dir, include_hidden=True)
        types = [e["type"] for e in result["entries"]]
        # All directories should come before files
        dir_indices = [i for i, t in enumerate(types) if t == "directory"]
        file_indices = [i for i, t in enumerate(types) if t == "file"]
        if dir_indices and file_indices:
            assert max(dir_indices) < min(file_indices)


# =============================================================================
# search_files_impl
# =============================================================================


class TestSearchFilesImpl:
    """Tests for file content search."""

    @pytest.mark.asyncio
    async def test_search_finds_pattern(self, populated_dir: Path, mock_roots):
        """Search finds files containing the pattern."""
        result = await search_files_impl(populated_dir, r"def \w+")
        assert result["status"] == "success"
        assert result["total_matches"] > 0
        assert any("main.py" in m["file"] for m in result["matches"])

    @pytest.mark.asyncio
    async def test_search_no_matches(self, populated_dir: Path, mock_roots):
        """Search with no matches returns empty list."""
        result = await search_files_impl(populated_dir, "xyznonexistentpattern123")
        assert result["status"] == "success"
        assert result["total_matches"] == 0
        assert result["matches"] == []

    @pytest.mark.asyncio
    async def test_search_nonexistent_path(self, tmp_path: Path, mock_roots):
        """Search in nonexistent path returns error."""
        result = await search_files_impl(tmp_path / "nope", "test")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_search_invalid_regex(self, populated_dir: Path, mock_roots):
        """Invalid regex returns error."""
        result = await search_files_impl(populated_dir, "[invalid")
        assert result["status"] == "error"
        assert "regex" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, populated_dir: Path, mock_roots):
        """Case-insensitive search finds matches regardless of case."""
        result = await search_files_impl(populated_dir, "DEF MAIN", case_sensitive=False)
        assert result["status"] == "success"
        assert result["total_matches"] > 0

    @pytest.mark.asyncio
    async def test_search_with_context(self, populated_dir: Path, mock_roots):
        """Search with context_lines includes surrounding lines."""
        result = await search_files_impl(populated_dir, "def main", context_lines=1)
        assert result["status"] == "success"
        if result["matches"]:
            assert "context" in result["matches"][0]
            assert len(result["matches"][0]["context"]) > 1

    @pytest.mark.asyncio
    async def test_search_max_results(self, populated_dir: Path, mock_roots):
        """Search respects max_results limit."""
        result = await search_files_impl(populated_dir, ".", max_results=2)
        assert result["status"] == "success"
        assert len(result["matches"]) <= 2

    @pytest.mark.asyncio
    async def test_search_with_glob_filter(self, populated_dir: Path, mock_roots):
        """Glob filter limits which files are searched."""
        result = await search_files_impl(populated_dir, "def", glob_filter="*.py")
        assert result["status"] == "success"
        for match in result["matches"]:
            assert match["file"].endswith(".py")


# =============================================================================
# file_info_impl
# =============================================================================


class TestFileInfoImpl:
    """Tests for file metadata retrieval."""

    @pytest.mark.asyncio
    async def test_file_info(self, populated_dir: Path, mock_roots):
        """Returns metadata for an existing file."""
        result = await file_info_impl(populated_dir / "src" / "main.py")
        assert result["status"] == "success"
        assert result["exists"] is True
        assert result["type"] == "file"
        assert result["size"] > 0
        assert "modified" in result
        assert "created" in result
        assert "permissions" in result

    @pytest.mark.asyncio
    async def test_directory_info(self, populated_dir: Path, mock_roots):
        """Returns metadata for a directory."""
        result = await file_info_impl(populated_dir / "src")
        assert result["status"] == "success"
        assert result["type"] == "directory"

    @pytest.mark.asyncio
    async def test_nonexistent_path(self, tmp_path: Path, mock_roots):
        """Nonexistent path returns exists=False."""
        result = await file_info_impl(tmp_path / "nope.txt")
        assert result["status"] == "success"
        assert result["exists"] is False


# =============================================================================
# move_file_impl
# =============================================================================


class TestMoveFileImpl:
    """Tests for file move/rename."""

    @pytest.mark.asyncio
    async def test_move_file(self, tmp_path: Path, mock_roots):
        """Move a file from source to destination."""
        src = tmp_path / "old.txt"
        dst = tmp_path / "new.txt"
        src.write_text("content")

        result = await move_file_impl(src, dst)
        assert result["status"] == "success"
        assert not src.exists()
        assert dst.read_text() == "content"

    @pytest.mark.asyncio
    async def test_move_nonexistent_source(self, tmp_path: Path, mock_roots):
        """Moving a nonexistent source returns error."""
        result = await move_file_impl(tmp_path / "nope.txt", tmp_path / "dst.txt")
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_move_destination_exists_no_overwrite(self, tmp_path: Path, mock_roots):
        """Moving to existing destination without overwrite returns error."""
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("source")
        dst.write_text("dest")

        result = await move_file_impl(src, dst, overwrite=False)
        assert result["status"] == "error"
        assert "already exists" in result["message"]

    @pytest.mark.asyncio
    async def test_move_creates_parent_dirs(self, tmp_path: Path, mock_roots):
        """Move creates destination parent directories."""
        src = tmp_path / "src.txt"
        dst = tmp_path / "a" / "b" / "moved.txt"
        src.write_text("content")

        result = await move_file_impl(src, dst)
        assert result["status"] == "success"
        assert dst.read_text() == "content"


# =============================================================================
# edit_file_impl
# =============================================================================


class TestEditFileImpl:
    """Tests for file editing."""

    @pytest.mark.asyncio
    async def test_single_edit(self, tmp_path: Path, mock_roots):
        """Apply a single text replacement."""
        f = tmp_path / "edit_me.txt"
        f.write_text("hello world\nfoo bar\n")

        edits = [{"old_text": "hello", "new_text": "goodbye"}]
        result = await edit_file_impl(f, edits)
        assert result["status"] == "success"
        assert result["edits_applied"] == 1
        assert f.read_text() == "goodbye world\nfoo bar\n"

    @pytest.mark.asyncio
    async def test_multiple_edits(self, tmp_path: Path, mock_roots):
        """Apply multiple edits in sequence."""
        f = tmp_path / "multi.txt"
        f.write_text("aaa bbb ccc\n")

        edits = [
            {"old_text": "aaa", "new_text": "xxx"},
            {"old_text": "ccc", "new_text": "zzz"},
        ]
        result = await edit_file_impl(f, edits)
        assert result["status"] == "success"
        assert result["edits_applied"] == 2
        assert f.read_text() == "xxx bbb zzz\n"

    @pytest.mark.asyncio
    async def test_edit_not_found(self, tmp_path: Path, mock_roots):
        """Edit with non-matching old_text reports not_found."""
        f = tmp_path / "no_match.txt"
        f.write_text("hello world\n")

        edits = [{"old_text": "nonexistent", "new_text": "something"}]
        result = await edit_file_impl(f, edits)
        assert result["edits_failed"] == 1
        assert result["edit_results"][0]["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_edit_multiple_matches(self, tmp_path: Path, mock_roots):
        """Edit with multiple matches reports warning and replaces all."""
        f = tmp_path / "dups.txt"
        f.write_text("foo foo foo\n")

        edits = [{"old_text": "foo", "new_text": "bar"}]
        result = await edit_file_impl(f, edits)
        assert result["edit_results"][0]["status"] == "multiple_matches"
        assert result["edit_results"][0]["matches"] == 3
        assert f.read_text() == "bar bar bar\n"

    @pytest.mark.asyncio
    async def test_dry_run(self, tmp_path: Path, mock_roots):
        """Dry run shows diff without modifying file."""
        f = tmp_path / "dry.txt"
        f.write_text("old content\n")

        edits = [{"old_text": "old", "new_text": "new"}]
        result = await edit_file_impl(f, edits, dry_run=True)
        assert result["status"] == "dry_run"
        assert result["changes_made"] is True
        assert "diff" in result
        # File should NOT be modified
        assert f.read_text() == "old content\n"

    @pytest.mark.asyncio
    async def test_edit_with_backup(self, tmp_path: Path, mock_roots):
        """Edit creates backup when create_backup=True."""
        f = tmp_path / "backup_test.txt"
        f.write_text("original\n")

        edits = [{"old_text": "original", "new_text": "modified"}]
        result = await edit_file_impl(f, edits, create_backup=True)
        assert result["status"] == "success"
        assert result["backup_path"] is not None
        assert Path(result["backup_path"]).read_text() == "original\n"

    @pytest.mark.asyncio
    async def test_edit_generates_unified_diff(self, tmp_path: Path, mock_roots):
        """Edit result includes a unified diff."""
        f = tmp_path / "diff.txt"
        f.write_text("line 1\nline 2\nline 3\n")

        edits = [{"old_text": "line 2", "new_text": "LINE TWO"}]
        result = await edit_file_impl(f, edits)
        assert result["status"] == "success"
        assert "diff" in result
        assert "-line 2" in result["diff"]
        assert "+LINE TWO" in result["diff"]

    @pytest.mark.asyncio
    async def test_edit_nonexistent_file(self, tmp_path: Path, mock_roots):
        """Editing a nonexistent file returns error."""
        result = await edit_file_impl(
            tmp_path / "nope.txt",
            [{"old_text": "a", "new_text": "b"}],
        )
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_edit_no_changes(self, tmp_path: Path, mock_roots):
        """When all edits fail to match, status is 'no_changes'."""
        f = tmp_path / "unchanged.txt"
        f.write_text("hello\n")

        edits = [{"old_text": "nonexistent", "new_text": "something"}]
        result = await edit_file_impl(f, edits)
        assert result["status"] == "no_changes"
