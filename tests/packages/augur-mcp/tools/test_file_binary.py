"""
Binary File Operations MCP Tool Contract Tests.

User Need: Read and write binary files (images, PDFs, ZIPs) via MCP tools.

Run with: cd packages/augur-mcp && uv run pytest tests/tools/test_file_binary.py -v
"""

import asyncio
import base64
from pathlib import Path

import pytest

from src.mcp.augur_framework.tools.infrastructure.files import (
    _guess_mime_type,
    _validate_asset_magic_bytes,
    read_file_impl,
    write_binary_file_impl,
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

    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.file_platform._ALLOWED_ROOTS",
        {"code": code_dir, "data": data_dir},
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.file_platform.get_allowed_roots",
        lambda: {"code": code_dir, "data": data_dir},
    )

    return {"code": code_dir, "data": data_dir}


# Minimal valid PNG: 1x1 pixel red
MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n"  # PNG signature
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
    b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Minimal valid PDF
MINIMAL_PDF = b"%PDF-1.0\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"

# Minimal valid ZIP with local file header (PK\x03\x04)
# Contains a single empty file named "a"
MINIMAL_ZIP = (
    b"PK\x03\x04\x14\x00\x00\x00\x00\x00\x00\x00!\x00"  # local file header
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x01\x00\x00\x00a"  # filename "a"
    b"PK\x01\x02\x14\x03\x14\x00\x00\x00\x00\x00\x00\x00!\x00"  # central dir
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\xa4\x81\x00\x00\x00\x00a"  # filename "a"
    b"PK\x05\x06\x00\x00\x00\x00\x01\x00\x01\x00"  # end of central dir
    b"/\x00\x00\x00%\x00\x00\x00\x00\x00"
)

# Minimal valid GIF
MINIMAL_GIF = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"


# =============================================================================
# Contract Tests: file-write-binary
# =============================================================================


@pytest.mark.contract
class TestFileWriteBinaryContract:
    """Tests for binary file write functionality."""

    def test_write_png_round_trip(self, temp_repo):
        """Write a PNG file and read it back — content should be identical."""
        code_dir = temp_repo["code"]
        target = code_dir / "assets" / "test.png"
        encoded = base64.b64encode(MINIMAL_PNG).decode("ascii")

        result = asyncio.run(write_binary_file_impl(target, encoded))

        assert result["status"] == "success"
        assert result["bytes_written"] == len(MINIMAL_PNG)
        assert result["mime_type"] == "image/png"
        assert target.exists()
        assert target.read_bytes() == MINIMAL_PNG

    def test_write_pdf_round_trip(self, temp_repo):
        """Write a PDF file and read it back."""
        code_dir = temp_repo["code"]
        target = code_dir / "docs" / "test.pdf"
        encoded = base64.b64encode(MINIMAL_PDF).decode("ascii")

        result = asyncio.run(write_binary_file_impl(target, encoded))

        assert result["status"] == "success"
        assert result["bytes_written"] == len(MINIMAL_PDF)
        assert target.read_bytes() == MINIMAL_PDF

    def test_write_zip_round_trip(self, temp_repo):
        """Write a ZIP file and read it back."""
        code_dir = temp_repo["code"]
        target = code_dir / "archives" / "test.zip"
        encoded = base64.b64encode(MINIMAL_ZIP).decode("ascii")

        result = asyncio.run(write_binary_file_impl(target, encoded))

        assert result["status"] == "success"
        assert target.read_bytes() == MINIMAL_ZIP

    def test_write_creates_parent_dirs(self, temp_repo):
        """Nested directories are created automatically."""
        code_dir = temp_repo["code"]
        target = code_dir / "deep" / "nested" / "path" / "image.png"
        encoded = base64.b64encode(MINIMAL_PNG).decode("ascii")

        result = asyncio.run(write_binary_file_impl(target, encoded, create_dirs=True))

        assert result["status"] == "success"
        assert target.exists()

    def test_write_creates_backup(self, temp_repo):
        """Existing file gets backed up before overwrite."""
        code_dir = temp_repo["code"]
        target = code_dir / "image.png"
        target.write_bytes(b"old content")

        encoded = base64.b64encode(MINIMAL_PNG).decode("ascii")
        result = asyncio.run(write_binary_file_impl(target, encoded, create_backup=True))

        assert result["status"] == "success"
        assert result["backup_path"] is not None
        backup = Path(result["backup_path"])
        assert backup.exists()
        assert backup.read_bytes() == b"old content"
        assert target.read_bytes() == MINIMAL_PNG

    def test_write_no_backup(self, temp_repo):
        """Backup can be disabled."""
        code_dir = temp_repo["code"]
        target = code_dir / "image.png"
        target.write_bytes(b"old content")

        encoded = base64.b64encode(MINIMAL_PNG).decode("ascii")
        result = asyncio.run(write_binary_file_impl(target, encoded, create_backup=False))

        assert result["status"] == "success"
        assert result["backup_path"] is None

    def test_write_invalid_base64(self, temp_repo):
        """Invalid base64 content returns error."""
        code_dir = temp_repo["code"]
        target = code_dir / "bad.png"

        result = asyncio.run(write_binary_file_impl(target, "not-valid-base64!!!"))

        assert result["status"] == "error"
        assert "Invalid base64" in result["message"]
        assert not target.exists()

    def test_write_magic_bytes_mismatch_warns(self, temp_repo):
        """Writing PDF content as .png succeeds but includes warning."""
        code_dir = temp_repo["code"]
        target = code_dir / "mismatched.png"
        # Write PDF data but name it .png
        encoded = base64.b64encode(MINIMAL_PDF).decode("ascii")

        result = asyncio.run(write_binary_file_impl(target, encoded))

        # Should succeed (warning only, not blocking)
        assert result["status"] == "success"
        assert "warning" in result
        assert "Magic bytes mismatch" in result["warning"]
        assert target.read_bytes() == MINIMAL_PDF

    def test_write_outside_allowed_roots(self, temp_repo, tmp_path):
        """Writing outside allowed repos fails."""
        target = tmp_path / "outside" / "evil.bin"
        encoded = base64.b64encode(b"data").decode("ascii")

        result = asyncio.run(write_binary_file_impl(target, encoded))

        assert result["status"] == "error"
        assert "Access denied" in result["message"] or "outside" in result["message"]


# =============================================================================
# Contract Tests: file-read binary mode
# =============================================================================


@pytest.mark.contract
class TestFileReadBinaryContract:
    """Tests for binary file read functionality."""

    def test_read_binary_png(self, temp_repo):
        """Read a PNG file in binary mode returns base64 + metadata."""
        code_dir = temp_repo["code"]
        target = code_dir / "test.png"
        target.write_bytes(MINIMAL_PNG)

        result = asyncio.run(read_file_impl(target, binary=True))

        assert result["status"] == "success"
        assert "content_base64" in result
        assert result["size_bytes"] == len(MINIMAL_PNG)
        assert result["mime_type"] == "image/png"
        # Verify round-trip
        decoded = base64.b64decode(result["content_base64"])
        assert decoded == MINIMAL_PNG

    def test_read_binary_pdf(self, temp_repo):
        """Read a PDF file in binary mode."""
        code_dir = temp_repo["code"]
        target = code_dir / "test.pdf"
        target.write_bytes(MINIMAL_PDF)

        result = asyncio.run(read_file_impl(target, binary=True))

        assert result["status"] == "success"
        assert result["mime_type"] == "application/pdf"
        decoded = base64.b64decode(result["content_base64"])
        assert decoded == MINIMAL_PDF

    def test_read_binary_file_not_found(self, temp_repo):
        """Reading nonexistent file returns error."""
        code_dir = temp_repo["code"]
        target = code_dir / "nonexistent.png"

        result = asyncio.run(read_file_impl(target, binary=True))

        assert result["status"] == "error"
        assert "not found" in result["message"].lower() or "File not found" in result["message"]

    def test_read_binary_unknown_mime(self, temp_repo):
        """Unknown extension gets application/octet-stream."""
        code_dir = temp_repo["code"]
        target = code_dir / "data.qwx"
        target.write_bytes(b"\x00\x01\x02\x03")

        result = asyncio.run(read_file_impl(target, binary=True))

        assert result["status"] == "success"
        assert result["mime_type"] == "application/octet-stream"

    def test_read_text_mode_unchanged(self, temp_repo):
        """Default text mode still works as before."""
        code_dir = temp_repo["code"]
        target = code_dir / "hello.txt"
        target.write_text("hello\nworld\n")

        result = asyncio.run(read_file_impl(target, binary=False))

        assert result["status"] == "success"
        assert "content" in result
        assert "hello" in result["content"]
        # Should NOT have binary fields
        assert "content_base64" not in result


# =============================================================================
# Contract Tests: full round-trip (write binary -> read binary)
# =============================================================================


@pytest.mark.contract
class TestBinaryRoundTripContract:
    """End-to-end round-trip: write binary, read binary, compare."""

    def test_png_full_round_trip(self, temp_repo):
        """Write PNG via binary write, read via binary read, data is identical."""
        code_dir = temp_repo["code"]
        target = code_dir / "roundtrip.png"
        original_b64 = base64.b64encode(MINIMAL_PNG).decode("ascii")

        # Write
        write_result = asyncio.run(write_binary_file_impl(target, original_b64))
        assert write_result["status"] == "success"

        # Read back
        read_result = asyncio.run(read_file_impl(target, binary=True))
        assert read_result["status"] == "success"
        assert read_result["content_base64"] == original_b64

    def test_gif_full_round_trip(self, temp_repo):
        """Write GIF via binary write, read via binary read, data is identical."""
        code_dir = temp_repo["code"]
        target = code_dir / "roundtrip.gif"
        original_b64 = base64.b64encode(MINIMAL_GIF).decode("ascii")

        write_result = asyncio.run(write_binary_file_impl(target, original_b64))
        assert write_result["status"] == "success"

        read_result = asyncio.run(read_file_impl(target, binary=True))
        assert read_result["status"] == "success"
        assert read_result["content_base64"] == original_b64


# =============================================================================
# Unit Tests: magic byte validation
# =============================================================================


class TestMagicByteValidation:
    """Tests for _validate_asset_magic_bytes helper."""

    def test_valid_png(self):
        valid, msg = _validate_asset_magic_bytes(MINIMAL_PNG, ".png")
        assert valid is True
        assert msg == ""

    def test_valid_pdf(self):
        valid, msg = _validate_asset_magic_bytes(MINIMAL_PDF, ".pdf")
        assert valid is True

    def test_valid_gif(self):
        valid, msg = _validate_asset_magic_bytes(MINIMAL_GIF, ".gif")
        assert valid is True

    def test_valid_zip(self):
        valid, msg = _validate_asset_magic_bytes(MINIMAL_ZIP, ".zip")
        assert valid is True

    def test_mismatch_pdf_as_png(self):
        """PDF content doesn't match PNG magic bytes."""
        valid, msg = _validate_asset_magic_bytes(MINIMAL_PDF, ".png")
        assert valid is False
        assert "Magic bytes mismatch" in msg

    def test_mismatch_png_as_jpg(self):
        """PNG content doesn't match JPG magic bytes."""
        valid, msg = _validate_asset_magic_bytes(MINIMAL_PNG, ".jpg")
        assert valid is False
        assert "Magic bytes mismatch" in msg

    def test_unknown_extension_passes(self):
        """Unknown extension is always valid (no check possible)."""
        valid, msg = _validate_asset_magic_bytes(b"anything", ".qwx")
        assert valid is True

    def test_empty_data_too_small(self):
        """Empty data fails for known extensions."""
        valid, msg = _validate_asset_magic_bytes(b"", ".png")
        assert valid is False
        assert "too small" in msg.lower()


# =============================================================================
# Unit Tests: MIME type guessing
# =============================================================================


class TestMimeTypeGuessing:
    """Tests for _guess_mime_type helper."""

    def test_png_mime(self):
        assert _guess_mime_type(Path("test.png")) == "image/png"

    def test_jpg_mime(self):
        assert _guess_mime_type(Path("test.jpg")) == "image/jpeg"

    def test_pdf_mime(self):
        assert _guess_mime_type(Path("test.pdf")) == "application/pdf"

    def test_zip_mime(self):
        assert _guess_mime_type(Path("test.zip")) == "application/zip"

    def test_unknown_mime(self):
        assert _guess_mime_type(Path("test.qwx")) == "application/octet-stream"


# =============================================================================
# Contract Tests: text file-write unchanged
# =============================================================================


@pytest.mark.contract
class TestTextFileWriteUnchanged:
    """Verify existing text file-write behavior is unaffected."""

    def test_text_write_still_works(self, temp_repo):
        """Standard text write continues to work."""
        code_dir = temp_repo["code"]
        target = code_dir / "text.txt"

        result = asyncio.run(write_file_impl(target, "hello world\n"))

        assert result["status"] == "success"
        assert target.read_text() == "hello world\n"

    def test_text_write_with_encoding(self, temp_repo):
        """Text write with explicit encoding still works."""
        code_dir = temp_repo["code"]
        target = code_dir / "encoded.txt"

        result = asyncio.run(write_file_impl(target, "hello", encoding="utf-8"))

        assert result["status"] == "success"
        assert target.read_text(encoding="utf-8") == "hello"


# Track 3a PR 2: TestLanguageDetection and TestSkillContentMatching
# removed — they tested helpers that supported the now-retired
# match-content-to-skill MCP tool. The helpers (_detect_language,
# _score_skill_match, _build_skill_profiles, match_content_to_skill_impl)
# remain in src/mcp/augur_mcp/infrastructure/file_assets.py but are
# unused by the framework after PR 2.
