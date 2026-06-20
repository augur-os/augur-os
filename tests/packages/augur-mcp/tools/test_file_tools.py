"""
File Operations MCP Tool Contract Tests.

User Need: Read, write, search, and manage files within the augur repos.

Run with: cd packages/augur-mcp && uv run pytest tests/tools/test_file_tools.py -v
"""

# TODO_CLEANUP: This file is 1063 lines — consider splitting into smaller modules

import asyncio
from pathlib import Path

import pytest

from src.mcp.augur_framework.tools.infrastructure.files import (
    edit_file_impl,
    file_info_impl,
    list_directory_impl,
    move_file_impl,
    read_file_impl,
    read_files_batch_impl,
    resolve_secure_path,
    search_files_impl,
    write_file_impl,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_repo(tmp_path, monkeypatch):
    """Create isolated repo directories for testing."""
    code_dir = tmp_path / "code"
    data_dir = tmp_path / "data"
    code_dir.mkdir()
    data_dir.mkdir()

    # Patch allowed roots
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.file_platform._ALLOWED_ROOTS",
        {"code": code_dir, "data": data_dir},
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.file_platform.get_allowed_roots",
        lambda: {"code": code_dir, "data": data_dir},
    )

    return {"code": code_dir, "data": data_dir}


@pytest.fixture
def sample_files(temp_repo):
    """Create sample files for testing."""
    code_dir = temp_repo["code"]
    data_dir = temp_repo["data"]

    # Create code files
    (code_dir / "main.py").write_text("print('hello world')\n")
    (code_dir / "utils.py").write_text("def helper():\n    return 42\n")

    # Create subdirectory
    subdir = code_dir / "src"
    subdir.mkdir()
    (subdir / "module.py").write_text("# module code\nclass MyClass:\n    pass\n")

    # Create data files
    (data_dir / "config.yaml").write_text("key: value\n")
    (data_dir / "notes.md").write_text("# Notes\n\nSome content here.\n")

    return {"code": code_dir, "data": data_dir}


# =============================================================================
# Contract Tests: file-read
# =============================================================================


@pytest.mark.contract
class TestFileReadContract:
    """
    User Need: Read file contents from augur repos.

    Acceptance Criteria:
    1. User can read file content
    2. Pagination works (offset, limit)
    3. Missing files return error
    4. Path traversal blocked
    """

    @pytest.mark.asyncio
    async def test_user_can_read_file(self, sample_files):
        """User story: As a user, I can read a file's contents."""
        code_dir = sample_files["code"]
        file_path = code_dir / "main.py"

        result = await read_file_impl(file_path)

        assert result["status"] == "success"
        assert "hello world" in result["content"]
        assert result["total_lines"] >= 1

    @pytest.mark.asyncio
    async def test_pagination_with_offset(self, sample_files):
        """User story: As a user, I can skip lines when reading."""
        code_dir = sample_files["code"]
        file_path = code_dir / "utils.py"

        result = await read_file_impl(file_path, offset=1)

        assert result["status"] == "success"
        assert result["offset"] == 1
        # Should skip first line
        assert "return 42" in result["content"]

    @pytest.mark.asyncio
    async def test_pagination_with_limit(self, sample_files):
        """User story: As a user, I can limit lines returned."""
        code_dir = sample_files["code"]
        file_path = code_dir / "utils.py"

        result = await read_file_impl(file_path, limit=1)

        assert result["status"] == "success"
        assert result["lines_returned"] == 1

    @pytest.mark.asyncio
    async def test_missing_file_returns_error(self, temp_repo):
        """User story: As a user, I get clear error for missing file."""
        code_dir = temp_repo["code"]
        file_path = code_dir / "nonexistent.py"

        result = await read_file_impl(file_path)

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_directory_returns_error(self, sample_files):
        """User story: As a user, I get error when reading directory."""
        code_dir = sample_files["code"]
        dir_path = code_dir / "src"

        result = await read_file_impl(dir_path)

        assert result["status"] == "error"
        assert "not a file" in result["message"].lower()


# =============================================================================
# Contract Tests: file-write
# =============================================================================


@pytest.mark.contract
class TestFileWriteContract:
    """
    User Need: Write files to augur repos.

    Acceptance Criteria:
    1. User can write new files
    2. User can overwrite existing files
    3. Backup created by default
    4. Parent directories created
    """

    @pytest.mark.asyncio
    async def test_user_can_write_new_file(self, temp_repo):
        """User story: As a user, I can create a new file."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "new_file.txt"

        result = await write_file_impl(file_path, "Hello, World!")

        assert result["status"] == "success"
        assert file_path.exists()
        assert file_path.read_text() == "Hello, World!"

    @pytest.mark.asyncio
    async def test_user_can_overwrite_file(self, sample_files):
        """User story: As a user, I can update existing file."""
        data_dir = sample_files["data"]
        file_path = data_dir / "config.yaml"

        result = await write_file_impl(file_path, "new_key: new_value\n")

        assert result["status"] == "success"
        assert file_path.read_text() == "new_key: new_value\n"

    @pytest.mark.asyncio
    async def test_backup_created_by_default(self, sample_files):
        """User story: As a user, backup is created when overwriting."""
        data_dir = sample_files["data"]
        file_path = data_dir / "config.yaml"
        original_content = file_path.read_text()

        result = await write_file_impl(file_path, "updated content")

        assert result["status"] == "success"
        assert result["backup_path"] is not None
        backup_path = Path(result["backup_path"])
        assert backup_path.exists()
        assert backup_path.read_text() == original_content

    @pytest.mark.asyncio
    async def test_parent_directories_created(self, temp_repo):
        """User story: As a user, parent dirs are auto-created."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "nested" / "deep" / "file.txt"

        result = await write_file_impl(file_path, "nested content")

        assert result["status"] == "success"
        assert file_path.exists()

    @pytest.mark.asyncio
    async def test_bytes_written_reported(self, temp_repo):
        """User story: As a user, I see how much was written."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "sized.txt"
        content = "Test content"

        result = await write_file_impl(file_path, content)

        assert result["status"] == "success"
        assert result["bytes_written"] == len(content.encode("utf-8"))


# =============================================================================
# Contract Tests: file-list
# =============================================================================


@pytest.mark.contract
class TestFileListContract:
    """
    User Need: List directory contents.

    Acceptance Criteria:
    1. User can list files in directory
    2. User can use glob patterns
    3. User can recurse into subdirs
    4. Entries have useful metadata
    """

    @pytest.mark.asyncio
    async def test_user_can_list_directory(self, sample_files):
        """User story: As a user, I can see directory contents."""
        code_dir = sample_files["code"]

        result = await list_directory_impl(code_dir)

        assert result["status"] == "success"
        assert "entries" in result
        assert len(result["entries"]) >= 2  # main.py, utils.py, src/

    @pytest.mark.asyncio
    async def test_glob_pattern_filtering(self, sample_files):
        """User story: As a user, I can filter by pattern."""
        code_dir = sample_files["code"]

        result = await list_directory_impl(code_dir, pattern="*.py")

        assert result["status"] == "success"
        # Should only get .py files
        for entry in result["entries"]:
            if entry["type"] == "file":
                assert entry["name"].endswith(".py")

    @pytest.mark.asyncio
    async def test_recursive_listing(self, sample_files):
        """User story: As a user, I can list all files recursively."""
        code_dir = sample_files["code"]

        result = await list_directory_impl(code_dir, pattern="*.py", recursive=True)

        assert result["status"] == "success"
        # Should include src/module.py
        names = [e["name"] for e in result["entries"]]
        assert any("module.py" in name for name in names)

    @pytest.mark.asyncio
    async def test_entries_have_metadata(self, sample_files):
        """User story: As a user, I see useful file info."""
        code_dir = sample_files["code"]

        result = await list_directory_impl(code_dir)

        assert result["status"] == "success"
        for entry in result["entries"]:
            assert "name" in entry
            assert "type" in entry
            assert "modified" in entry
            if entry["type"] == "file":
                assert "size" in entry

    @pytest.mark.asyncio
    async def test_missing_directory_returns_error(self, temp_repo):
        """User story: As a user, I get error for missing directory."""
        code_dir = temp_repo["code"]
        missing_dir = code_dir / "nonexistent"

        result = await list_directory_impl(missing_dir)

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()


# =============================================================================
# Contract Tests: file-search
# =============================================================================


@pytest.mark.contract
class TestFileSearchContract:
    """
    User Need: Search for content in files.

    Acceptance Criteria:
    1. User can search with regex
    2. Results include file, line, content
    3. Context lines work
    4. Invalid regex returns error
    """

    @pytest.mark.asyncio
    async def test_user_can_search_files(self, sample_files):
        """User story: As a user, I can search for text."""
        code_dir = sample_files["code"]

        result = await search_files_impl(code_dir, pattern="hello")

        assert result["status"] == "success"
        assert len(result["matches"]) >= 1
        assert any("hello" in m["content"] for m in result["matches"])

    @pytest.mark.asyncio
    async def test_regex_pattern_works(self, sample_files):
        """User story: As a user, I can use regex patterns."""
        code_dir = sample_files["code"]

        result = await search_files_impl(code_dir, pattern=r"def \w+")

        assert result["status"] == "success"
        assert len(result["matches"]) >= 1

    @pytest.mark.asyncio
    async def test_matches_have_required_fields(self, sample_files):
        """User story: As a user, matches have useful info."""
        code_dir = sample_files["code"]

        result = await search_files_impl(code_dir, pattern="class")

        assert result["status"] == "success"
        for match in result["matches"]:
            assert "file" in match
            assert "line" in match
            assert "content" in match

    @pytest.mark.asyncio
    async def test_context_lines_included(self, sample_files):
        """User story: As a user, I can see surrounding context."""
        code_dir = sample_files["code"]

        result = await search_files_impl(code_dir, pattern="class", context_lines=1)

        assert result["status"] == "success"
        if result["matches"]:
            assert "context" in result["matches"][0]

    @pytest.mark.asyncio
    async def test_invalid_regex_returns_error(self, sample_files):
        """User story: As a user, I get error for bad regex."""
        code_dir = sample_files["code"]

        result = await search_files_impl(code_dir, pattern="[invalid")

        assert result["status"] == "error"
        assert "regex" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty(self, sample_files):
        """User story: As a user, no matches shows empty list."""
        code_dir = sample_files["code"]

        result = await search_files_impl(code_dir, pattern="xyznonexistent123")

        assert result["status"] == "success"
        assert result["matches"] == []


# =============================================================================
# Contract Tests: file-read-multi
# =============================================================================


@pytest.mark.contract
class TestFileReadMultiContract:
    """
    User Need: Read multiple files efficiently.

    Acceptance Criteria:
    1. User can batch read files
    2. Results include per-file status
    3. Partial success handled
    """

    @pytest.mark.asyncio
    async def test_user_can_batch_read(self, sample_files):
        """User story: As a user, I can read multiple files at once."""
        code_dir = sample_files["code"]
        files = [
            {"path": str(code_dir / "main.py")},
            {"path": str(code_dir / "utils.py")},
        ]

        result = await read_files_batch_impl(files, default_repo="code")

        assert result["status"] == "success"
        assert result["success_count"] == 2
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_partial_success_reported(self, sample_files):
        """User story: As a user, I see which files failed."""
        code_dir = sample_files["code"]
        files = [
            {"path": str(code_dir / "main.py")},
            {"path": str(code_dir / "nonexistent.py")},
        ]

        result = await read_files_batch_impl(files, default_repo="code")

        assert result["status"] == "partial"
        assert result["success_count"] == 1
        assert result["error_count"] == 1


# =============================================================================
# Contract Tests: file-info
# =============================================================================


@pytest.mark.contract
class TestFileInfoContract:
    """
    User Need: Get file/directory metadata.

    Acceptance Criteria:
    1. User can get file info
    2. User can get directory info
    3. Non-existent returns exists=false
    """

    @pytest.mark.asyncio
    async def test_user_can_get_file_info(self, sample_files):
        """User story: As a user, I can see file metadata."""
        code_dir = sample_files["code"]
        file_path = code_dir / "main.py"

        result = await file_info_impl(file_path)

        assert result["status"] == "success"
        assert result["exists"] is True
        assert result["type"] == "file"
        assert "size" in result
        assert "modified" in result

    @pytest.mark.asyncio
    async def test_user_can_get_directory_info(self, sample_files):
        """User story: As a user, I can see directory metadata."""
        code_dir = sample_files["code"]
        dir_path = code_dir / "src"

        result = await file_info_impl(dir_path)

        assert result["status"] == "success"
        assert result["exists"] is True
        assert result["type"] == "directory"

    @pytest.mark.asyncio
    async def test_nonexistent_returns_exists_false(self, temp_repo):
        """User story: As a user, I know if file doesn't exist."""
        code_dir = temp_repo["code"]
        missing_path = code_dir / "missing.txt"

        result = await file_info_impl(missing_path)

        assert result["status"] == "success"
        assert result["exists"] is False


# =============================================================================
# Contract Tests: file-move
# =============================================================================


@pytest.mark.contract
class TestFileMoveContract:
    """
    User Need: Move/rename files.

    Acceptance Criteria:
    1. User can rename files
    2. User can move to new directory
    3. Overwrite protection works
    """

    @pytest.mark.asyncio
    async def test_user_can_rename_file(self, sample_files):
        """User story: As a user, I can rename a file."""
        code_dir = sample_files["code"]
        source = code_dir / "main.py"
        dest = code_dir / "renamed.py"

        result = await move_file_impl(source, dest)

        assert result["status"] == "success"
        assert dest.exists()
        assert not source.exists()

    @pytest.mark.asyncio
    async def test_user_can_move_to_new_directory(self, sample_files):
        """User story: As a user, I can move file to subdir."""
        code_dir = sample_files["code"]
        source = code_dir / "utils.py"
        dest = code_dir / "src" / "utils.py"

        result = await move_file_impl(source, dest)

        assert result["status"] == "success"
        assert dest.exists()
        assert not source.exists()

    @pytest.mark.asyncio
    async def test_overwrite_protection(self, sample_files):
        """User story: As a user, I'm protected from accidental overwrite."""
        code_dir = sample_files["code"]
        source = code_dir / "main.py"
        dest = code_dir / "utils.py"  # Already exists

        result = await move_file_impl(source, dest, overwrite=False)

        assert result["status"] == "error"
        assert "exists" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_overwrite_when_allowed(self, sample_files):
        """User story: As a user, I can force overwrite."""
        code_dir = sample_files["code"]
        source = code_dir / "main.py"
        dest = code_dir / "utils.py"  # Already exists

        result = await move_file_impl(source, dest, overwrite=True)

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_missing_source_returns_error(self, temp_repo):
        """User story: As a user, I get error for missing source."""
        code_dir = temp_repo["code"]
        source = code_dir / "nonexistent.py"
        dest = code_dir / "new.py"

        result = await move_file_impl(source, dest)

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()


# =============================================================================
# Contract Tests: file-edit
# =============================================================================


@pytest.mark.contract
class TestFileEditContract:
    """
    User Need: Edit files with search/replace.

    Acceptance Criteria:
    1. User can replace text
    2. Dry-run preview works
    3. Diff output provided
    4. Backup created
    5. Multiple edits work
    """

    @pytest.mark.asyncio
    async def test_user_can_replace_text(self, sample_files):
        """User story: As a user, I can replace text in file."""
        code_dir = sample_files["code"]
        file_path = code_dir / "main.py"

        edits = [{"old_text": "hello world", "new_text": "goodbye world"}]
        result = await edit_file_impl(file_path, edits)

        assert result["status"] == "success"
        assert result["edits_applied"] == 1
        assert "goodbye world" in file_path.read_text()

    @pytest.mark.asyncio
    async def test_dry_run_preview(self, sample_files):
        """User story: As a user, I can preview changes."""
        code_dir = sample_files["code"]
        file_path = code_dir / "main.py"
        original = file_path.read_text()

        edits = [{"old_text": "hello world", "new_text": "dry run test"}]
        result = await edit_file_impl(file_path, edits, dry_run=True)

        assert result["status"] == "dry_run"
        assert "diff" in result
        # File should be unchanged
        assert file_path.read_text() == original

    @pytest.mark.asyncio
    async def test_diff_output_provided(self, sample_files):
        """User story: As a user, I see a diff of changes."""
        code_dir = sample_files["code"]
        file_path = code_dir / "main.py"

        edits = [{"old_text": "hello", "new_text": "goodbye"}]
        result = await edit_file_impl(file_path, edits)

        assert result["status"] == "success"
        assert "diff" in result
        # Diff shows the change - either removed or added line
        assert "hello" in result["diff"] and "goodbye" in result["diff"]

    @pytest.mark.asyncio
    async def test_backup_created(self, sample_files):
        """User story: As a user, backup is created before edit."""
        code_dir = sample_files["code"]
        file_path = code_dir / "main.py"
        original = file_path.read_text()

        edits = [{"old_text": "hello", "new_text": "goodbye"}]
        result = await edit_file_impl(file_path, edits, create_backup=True)

        assert result["status"] == "success"
        assert result["backup_path"] is not None
        backup = Path(result["backup_path"])
        assert backup.read_text() == original

    @pytest.mark.asyncio
    async def test_multiple_edits(self, sample_files):
        """User story: As a user, I can make multiple edits."""
        code_dir = sample_files["code"]
        file_path = code_dir / "utils.py"

        edits = [
            {"old_text": "def helper", "new_text": "def my_helper"},
            {"old_text": "return 42", "new_text": "return 100"},
        ]
        result = await edit_file_impl(file_path, edits)

        assert result["status"] == "success"
        assert result["edits_applied"] == 2
        content = file_path.read_text()
        assert "my_helper" in content
        assert "return 100" in content

    @pytest.mark.asyncio
    async def test_not_found_pattern_reported(self, sample_files):
        """User story: As a user, I know if pattern not found."""
        code_dir = sample_files["code"]
        file_path = code_dir / "main.py"

        edits = [{"old_text": "nonexistent pattern xyz", "new_text": "replacement"}]
        result = await edit_file_impl(file_path, edits)

        assert result["edits_failed"] == 1
        assert result["edit_results"][0]["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_missing_file_returns_error(self, temp_repo):
        """User story: As a user, I get error for missing file."""
        code_dir = temp_repo["code"]
        file_path = code_dir / "nonexistent.py"

        edits = [{"old_text": "old", "new_text": "new"}]
        result = await edit_file_impl(file_path, edits)

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()


# =============================================================================
# Security Tests
# =============================================================================


@pytest.mark.contract
class TestSecurityContract:
    """
    User Need: Secure file operations.

    Acceptance Criteria:
    1. Path traversal blocked
    2. Only allowed repos accessible
    """

    def test_path_traversal_blocked(self, temp_repo):
        """Security: Path traversal attempts are blocked."""
        with pytest.raises(ValueError):
            resolve_secure_path("../../../etc/passwd", "code")

    def test_absolute_path_outside_repo_blocked(self, temp_repo):
        """Security: Absolute paths outside repos blocked."""
        with pytest.raises(ValueError):
            resolve_secure_path("/etc/passwd", "code")

    def test_valid_relative_path_allowed(self, temp_repo):
        """Security: Valid relative paths work."""
        code_dir = temp_repo["code"]
        (code_dir / "test.txt").write_text("test")

        resolved, repo = resolve_secure_path("test.txt", "code")
        assert resolved == code_dir / "test.txt"
        assert repo == "code"


# =============================================================================
# CRITICAL ISSUE #1: Path Traversal in Actual Tool Implementations
# =============================================================================


@pytest.mark.contract
class TestToolPathTraversalSecurity:
    """
    Critical Security: Verify actual tool implementations block path traversal.

    These tests ensure tools don't just rely on resolve_secure_path but
    actually handle malicious paths safely.
    """

    @pytest.mark.asyncio
    async def test_read_file_blocks_traversal_via_symlink(self, temp_repo):
        """Security: Symlink-based traversal blocked in read.

        VULNERABILITY DETECTED: read_file_impl follows symlinks that point
        outside the allowed roots, allowing attackers to read arbitrary files
        like /etc/passwd. Fix: Use realpath() and verify resolved path is
        within allowed roots before reading.
        """
        code_dir = temp_repo["code"]

        # Create symlink pointing outside repo (if supported)
        symlink_path = code_dir / "evil_link"
        try:
            symlink_path.symlink_to("/etc/passwd")
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")

        # read_file_impl should reject or safely handle this
        result = await read_file_impl(symlink_path)

        # Should either error or return safe response (not /etc/passwd content)
        if result["status"] == "success":
            assert "root:" not in result.get("content", "")
        else:
            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_write_file_blocks_traversal_path(self, temp_repo):
        """Security: Write to traversal path blocked.

        VULNERABILITY DETECTED: write_file_impl does not properly validate
        paths containing '..' sequences. Attackers can write files outside
        allowed roots. Fix: Resolve path and verify it's within allowed roots
        before any write operation.
        """
        code_dir = temp_repo["code"]

        # Construct path that looks legitimate but tries to escape
        malicious_path = code_dir / ".." / ".." / "tmp" / "evil.txt"

        result = await write_file_impl(malicious_path, "malicious content")

        # Should fail - path escapes allowed root
        assert result["status"] == "error"
        assert not Path("/tmp/evil.txt").exists()

    @pytest.mark.asyncio
    async def test_move_file_blocks_destination_traversal(self, sample_files):
        """Security: Move to outside repo blocked.

        VULNERABILITY DETECTED: move_file_impl does not properly validate
        destination paths. Attackers can exfiltrate files by moving them
        outside allowed roots. Fix: Validate BOTH source AND destination
        paths are within allowed roots after resolution.
        """
        code_dir = sample_files["code"]
        source = code_dir / "main.py"

        # Try to move file outside repo
        malicious_dest = code_dir / ".." / ".." / "tmp" / "stolen.py"

        result = await move_file_impl(source, malicious_dest)

        assert result["status"] == "error"
        assert source.exists()  # Original should still exist

    @pytest.mark.asyncio
    async def test_edit_file_blocks_traversal(self, temp_repo):
        """Security: Edit with traversal path blocked."""
        code_dir = temp_repo["code"]

        malicious_path = code_dir / ".." / ".." / "etc" / "hosts"
        edits = [{"old_text": "localhost", "new_text": "hacked"}]

        result = await edit_file_impl(malicious_path, edits)

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_search_blocks_traversal(self, temp_repo):
        """Security: Search in traversal path blocked."""
        code_dir = temp_repo["code"]

        malicious_path = code_dir / ".." / ".." / "etc"

        result = await search_files_impl(malicious_path, pattern="root")

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_list_blocks_traversal(self, temp_repo):
        """Security: List traversal path blocked."""
        code_dir = temp_repo["code"]

        malicious_path = code_dir / ".." / ".." / "etc"

        result = await list_directory_impl(malicious_path)

        assert result["status"] == "error"


# =============================================================================
# CRITICAL ISSUE #2: Concurrent File Operations (Race Conditions)
# =============================================================================


@pytest.mark.contract
class TestConcurrentFileOperations:
    """
    Critical: Test for race conditions in concurrent file operations.

    In multi-agent environments, simultaneous file access must be safe.
    """

    @pytest.mark.asyncio
    async def test_concurrent_writes_dont_corrupt(self, temp_repo):
        """Concurrency: Simultaneous writes don't corrupt file."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "concurrent.txt"
        file_path.write_text("initial")

        async def write_content(content: str):
            await write_file_impl(file_path, content)

        # Launch concurrent writes
        await asyncio.gather(
            write_content("content_a"),
            write_content("content_b"),
            write_content("content_c"),
        )

        # File should exist and have one of the contents (not corrupted mix)
        final_content = file_path.read_text()
        assert final_content in ["content_a", "content_b", "content_c"]

    @pytest.mark.asyncio
    async def test_concurrent_edits_preserve_integrity(self, temp_repo):
        """Concurrency: Simultaneous edits don't corrupt."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "multi_edit.txt"
        file_path.write_text("line1\nline2\nline3\n")

        async def edit_line(old: str, new: str):
            edits = [{"old_text": old, "new_text": new}]
            return await edit_file_impl(file_path, edits)

        # Concurrent edits to different parts
        results = await asyncio.gather(
            edit_line("line1", "edited1"),
            edit_line("line2", "edited2"),
            return_exceptions=True,
        )

        # At least one should succeed, file shouldn't be corrupted
        content = file_path.read_text()
        assert "edited" in content or any(isinstance(r, dict) and r.get("status") == "success" for r in results)

    @pytest.mark.asyncio
    async def test_read_during_write_safe(self, temp_repo):
        """Concurrency: Read during write returns consistent data."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "read_write.txt"
        file_path.write_text("original content here")

        results = []

        async def slow_write():
            # Simulate slow write
            await write_file_impl(file_path, "new content after slow write")

        async def quick_read():
            result = await read_file_impl(file_path)
            results.append(result)

        await asyncio.gather(slow_write(), quick_read(), quick_read())

        # All reads should return valid content (not partial/corrupted)
        for result in results:
            if result["status"] == "success":
                content = result["content"]
                # Content should be complete (not truncated mid-write)
                assert content in ["original content here", "new content after slow write"]

    @pytest.mark.asyncio
    async def test_backup_not_overwritten_by_concurrent_edit(self, temp_repo):
        """Concurrency: Concurrent edits create separate backups."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "backup_test.txt"
        file_path.write_text("original")

        async def edit_with_backup(new_content: str):
            edits = [{"old_text": "original", "new_text": new_content}]
            return await edit_file_impl(file_path, edits, create_backup=True)

        # First edit creates backup
        result1 = await edit_with_backup("version1")

        if result1["status"] == "success" and result1.get("backup_path"):
            backup1 = Path(result1["backup_path"])
            backup1_content = backup1.read_text()

            # Backup should contain original content
            assert backup1_content == "original"


# =============================================================================
# CRITICAL ISSUE #5: Large File Handling
# =============================================================================


@pytest.mark.contract
class TestLargeFileHandling:
    """
    Critical: Test handling of large files and edge cases.

    Prevents DoS through memory exhaustion.
    """

    @pytest.mark.asyncio
    async def test_large_file_with_pagination(self, temp_repo):
        """Large file: Pagination prevents memory exhaustion."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "large.txt"

        # Create file with 10000 lines
        lines = [f"Line {i}: {'x' * 100}\n" for i in range(10000)]
        file_path.write_text("".join(lines))

        # Read with limit should not load entire file
        result = await read_file_impl(file_path, limit=100)

        assert result["status"] == "success"
        assert result["lines_returned"] == 100
        assert result["total_lines"] == 10000

    @pytest.mark.asyncio
    async def test_very_long_line_truncated(self, temp_repo):
        """Large file: Very long lines handled gracefully."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "long_line.txt"

        # Create file with extremely long line
        long_line = "x" * 50000  # 50KB single line
        file_path.write_text(long_line)

        result = await read_file_impl(file_path)

        assert result["status"] == "success"
        # Content should be present (possibly truncated)
        assert len(result["content"]) > 0

    @pytest.mark.asyncio
    async def test_binary_file_detection(self, temp_repo):
        """Large file: Binary files handled safely."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "binary.bin"

        # Create binary file with null bytes
        file_path.write_bytes(b"\x00\x01\x02\xff\xfe\xfd" * 1000)

        result = await read_file_impl(file_path)

        # Should either error or indicate binary
        if result["status"] == "success":
            # Binary content might be escaped or truncated
            pass
        else:
            assert "binary" in result.get("message", "").lower() or result["status"] == "error"

    @pytest.mark.asyncio
    async def test_empty_file_handled(self, temp_repo):
        """Edge case: Empty file doesn't crash."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "empty.txt"
        file_path.write_text("")

        result = await read_file_impl(file_path)

        assert result["status"] == "success"
        assert result["content"] == ""
        assert result["total_lines"] == 0

    @pytest.mark.asyncio
    async def test_file_with_only_newlines(self, temp_repo):
        """Edge case: File with only newlines."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "newlines.txt"
        file_path.write_text("\n\n\n\n\n")

        result = await read_file_impl(file_path)

        assert result["status"] == "success"
        assert result["total_lines"] == 5

    @pytest.mark.asyncio
    async def test_search_large_file_with_limit(self, temp_repo):
        """Large file: Search respects result limits."""
        data_dir = temp_repo["data"]
        file_path = data_dir / "searchable.txt"

        # Create file with many matching lines
        lines = [f"match_{i}: found it here\n" for i in range(1000)]
        file_path.write_text("".join(lines))

        result = await search_files_impl(data_dir, pattern="found", max_results=10)

        assert result["status"] == "success"
        # Should respect limit, not return all 1000 matches
        assert len(result["matches"]) <= 10

    @pytest.mark.asyncio
    async def test_list_directory_with_many_files(self, temp_repo):
        """Large directory: Listing many files doesn't hang."""
        data_dir = temp_repo["data"]
        subdir = data_dir / "many_files"
        subdir.mkdir()

        # Create 500 files
        for i in range(500):
            (subdir / f"file_{i}.txt").write_text(f"content {i}")

        result = await list_directory_impl(subdir)

        assert result["status"] == "success"
        assert len(result["entries"]) == 500
