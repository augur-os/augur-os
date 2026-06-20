"""
Tests for file read/write implementations (infrastructure/file_rw.py).

Validates read_file_impl (text and binary modes), write_file_impl
(atomic writes, backups), and write_binary_file_impl.

Run with: pytest tests/packages/augur-mcp/infrastructure/test_file_rw.py -v
"""

import base64
from pathlib import Path
from unittest.mock import patch

import pytest

from src.mcp.augur_framework.tools.infrastructure.file_rw import (
    read_file_impl,
    write_binary_file_impl,
    write_file_impl,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_roots(tmp_path: Path, monkeypatch):
    """Set up isolated allowed roots pointing to tmp_path."""
    roots = {"code": tmp_path, "data": tmp_path}
    monkeypatch.setattr("src.mcp.augur_framework.tools.infrastructure.file_platform._ALLOWED_ROOTS", roots)
    monkeypatch.setattr("src.mcp.augur_framework.tools.infrastructure.file_platform.get_allowed_roots", lambda: roots)
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.file_rw.validate_path_within_roots", lambda p: None
    )
    return roots


# =============================================================================
# read_file_impl
# =============================================================================


class TestReadFileImpl:
    """Tests for text file reading."""

    @pytest.mark.asyncio
    async def test_read_existing_file(self, tmp_path: Path, mock_roots):
        """Read a basic text file."""
        f = tmp_path / "test.txt"
        f.write_text("line 1\nline 2\nline 3\n")

        result = await read_file_impl(f)
        assert result["status"] == "success"
        assert result["total_lines"] == 3
        assert result["lines_returned"] == 3
        assert "line 1\nline 2\nline 3" == result["content"]

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, tmp_path: Path, mock_roots):
        """Reading a nonexistent file returns error."""
        result = await read_file_impl(tmp_path / "nope.txt")
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_read_directory_returns_error(self, tmp_path: Path, mock_roots):
        """Reading a directory (not a file) returns error."""
        result = await read_file_impl(tmp_path)
        assert result["status"] == "error"
        assert "Not a file" in result["message"]

    @pytest.mark.asyncio
    async def test_read_with_offset(self, tmp_path: Path, mock_roots):
        """Read with offset skips initial lines."""
        f = tmp_path / "lines.txt"
        f.write_text("line 0\nline 1\nline 2\nline 3\nline 4\n")

        result = await read_file_impl(f, offset=2)
        assert result["status"] == "success"
        assert result["offset"] == 2
        assert result["content"].startswith("line 2")

    @pytest.mark.asyncio
    async def test_read_with_limit(self, tmp_path: Path, mock_roots):
        """Read with limit returns at most N lines."""
        f = tmp_path / "many.txt"
        f.write_text("\n".join(f"line {i}" for i in range(100)) + "\n")

        result = await read_file_impl(f, limit=5)
        assert result["status"] == "success"
        assert result["lines_returned"] == 5
        assert result["total_lines"] == 100

    @pytest.mark.asyncio
    async def test_read_binary_mode(self, tmp_path: Path, mock_roots):
        """Binary read returns base64-encoded content."""
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        result = await read_file_impl(f, binary=True)
        assert result["status"] == "success"
        assert "content_base64" in result
        assert result["size_bytes"] == 108
        assert result["mime_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_read_binary_too_large(self, tmp_path: Path, mock_roots):
        """Binary read rejects files exceeding MAX_BINARY_SIZE."""
        f = tmp_path / "huge.bin"
        f.write_bytes(b"\x00" * 10)  # Small file, but we mock the stat

        with patch.object(type(f.stat()), "st_size", new_callable=lambda: property(lambda self: 60 * 1024 * 1024)):
            # Actually write a small file but make stat report huge size
            pass

        # Instead, just write a small file and patch MAX_BINARY_SIZE to be very small
        with patch("src.mcp.augur_framework.tools.infrastructure.file_rw.MAX_BINARY_SIZE", 5):
            result = await read_file_impl(f, binary=True)
            assert result["status"] == "error"
            assert "too large" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_read_empty_file(self, tmp_path: Path, mock_roots):
        """Reading an empty file returns empty content."""
        f = tmp_path / "empty.txt"
        f.write_text("")

        result = await read_file_impl(f)
        assert result["status"] == "success"
        assert result["content"] == ""
        assert result["total_lines"] == 0

    @pytest.mark.asyncio
    async def test_read_security_check(self, tmp_path: Path, monkeypatch):
        """Path outside allowed roots is rejected by security layer."""
        roots = {"code": tmp_path / "safe"}
        (tmp_path / "safe").mkdir()
        monkeypatch.setattr("src.mcp.augur_framework.tools.infrastructure.file_platform._ALLOWED_ROOTS", roots)
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.file_platform.get_allowed_roots", lambda: roots
        )
        # Restore real validate_path_within_roots
        from src.mcp.augur_framework.tools.infrastructure.file_platform import (
            validate_path_within_roots as real_validate,
        )

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.file_rw.validate_path_within_roots", real_validate
        )

        outside = tmp_path / "outside.txt"
        outside.write_text("secret")

        result = await read_file_impl(outside)
        assert result["status"] == "error"
        assert "denied" in result["message"].lower() or "outside" in result["message"].lower()


# =============================================================================
# write_file_impl
# =============================================================================


class TestWriteFileImpl:
    """Tests for text file writing."""

    @pytest.mark.asyncio
    async def test_write_new_file(self, tmp_path: Path, mock_roots):
        """Write creates a new file."""
        f = tmp_path / "new.txt"
        result = await write_file_impl(f, "hello world")

        assert result["status"] == "success"
        assert f.read_text() == "hello world"
        assert result["bytes_written"] == len(b"hello world")

    @pytest.mark.asyncio
    async def test_write_with_backup(self, tmp_path: Path, mock_roots):
        """Write creates backup of existing file."""
        f = tmp_path / "existing.txt"
        f.write_text("old content")

        result = await write_file_impl(f, "new content", create_backup=True)
        assert result["status"] == "success"
        assert f.read_text() == "new content"
        assert result["backup_path"] is not None
        assert Path(result["backup_path"]).exists()

    @pytest.mark.asyncio
    async def test_write_without_backup(self, tmp_path: Path, mock_roots):
        """Write without backup skips backup creation."""
        f = tmp_path / "no_backup.txt"
        f.write_text("old")

        result = await write_file_impl(f, "new", create_backup=False)
        assert result["status"] == "success"
        assert result["backup_path"] is None

    @pytest.mark.asyncio
    async def test_write_creates_parent_dirs(self, tmp_path: Path, mock_roots):
        """Write creates parent directories when create_dirs=True."""
        f = tmp_path / "a" / "b" / "c" / "deep.txt"
        result = await write_file_impl(f, "deep content", create_dirs=True)
        assert result["status"] == "success"
        assert f.read_text() == "deep content"

    @pytest.mark.asyncio
    async def test_write_append_preserves_existing_content(self, tmp_path: Path, mock_roots):
        """Append mode extends the file atomically instead of replacing it."""
        f = tmp_path / "append.txt"
        f.write_text("first\n", encoding="utf-8")

        result = await write_file_impl(f, "second\n", append=True)

        assert result["status"] == "success"
        assert result["appended"] is True
        assert f.read_text(encoding="utf-8") == "first\nsecond\n"

    @pytest.mark.asyncio
    async def test_write_unicode(self, tmp_path: Path, mock_roots):
        """Write handles Unicode content."""
        f = tmp_path / "unicode.txt"
        content = "Hello World"
        result = await write_file_impl(f, content)
        assert result["status"] == "success"
        assert f.read_text(encoding="utf-8") == content


# =============================================================================
# write_binary_file_impl
# =============================================================================


class TestWriteBinaryFileImpl:
    """Tests for binary file writing."""

    @pytest.mark.asyncio
    async def test_write_valid_binary(self, tmp_path: Path, mock_roots):
        """Write valid base64-encoded binary content."""
        f = tmp_path / "image.png"
        # PNG magic bytes + some data
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        b64_content = base64.b64encode(png_data).decode("ascii")

        result = await write_binary_file_impl(f, b64_content)
        assert result["status"] == "success"
        assert result["bytes_written"] == len(png_data)
        assert result["mime_type"] == "image/png"
        assert f.read_bytes() == png_data

    @pytest.mark.asyncio
    async def test_write_invalid_base64(self, tmp_path: Path, mock_roots):
        """Invalid base64 content returns error."""
        f = tmp_path / "bad.bin"
        result = await write_binary_file_impl(f, "not-valid-base64!!!")
        assert result["status"] == "error"
        assert "base64" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_write_binary_too_large(self, tmp_path: Path, mock_roots):
        """Binary content exceeding MAX_BINARY_SIZE returns error."""
        f = tmp_path / "huge.bin"
        with patch("src.mcp.augur_framework.tools.infrastructure.file_rw.MAX_BINARY_SIZE", 10):
            large_data = base64.b64encode(b"\x00" * 20).decode("ascii")
            result = await write_binary_file_impl(f, large_data)
            assert result["status"] == "error"
            assert "too large" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_write_binary_with_backup(self, tmp_path: Path, mock_roots):
        """Binary write creates backup of existing file."""
        f = tmp_path / "existing.bin"
        f.write_bytes(b"old data")

        new_data = base64.b64encode(b"new data").decode("ascii")
        result = await write_binary_file_impl(f, new_data, create_backup=True)
        assert result["status"] == "success"
        assert result["backup_path"] is not None
        assert f.read_bytes() == b"new data"

    @pytest.mark.asyncio
    async def test_write_binary_magic_bytes_mismatch_warning(self, tmp_path: Path, mock_roots):
        """Mismatched magic bytes produce a warning but write succeeds."""
        f = tmp_path / "fake.png"
        # Not a real PNG (wrong magic bytes)
        bad_data = base64.b64encode(b"not a png file").decode("ascii")

        result = await write_binary_file_impl(f, bad_data)
        assert result["status"] == "success"
        # The warning field is included when magic bytes don't match
        assert "warning" in result
