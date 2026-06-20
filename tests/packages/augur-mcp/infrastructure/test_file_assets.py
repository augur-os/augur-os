"""
Tests for binary asset helpers and skill content matching (infrastructure/file_assets.py).

Validates magic byte validation, MIME type detection, asset subfolder suggestions,
language detection, and skill scoring logic.

Run with: pytest tests/packages/augur-mcp/infrastructure/test_file_assets.py -v
"""

from pathlib import Path
from typing import Any

import pytest

from src.mcp.augur_framework.tools.infrastructure.file_assets import (
    _detect_language,
    _guess_mime_type,
    _score_skill_match,
    _suggest_asset_subfolder,
    _validate_asset_magic_bytes,
)

# =============================================================================
# _validate_asset_magic_bytes
# =============================================================================


class TestValidateAssetMagicBytes:
    """Tests for binary format magic byte validation."""

    def test_valid_png(self):
        """Valid PNG magic bytes pass validation."""
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        valid, msg = _validate_asset_magic_bytes(data, ".png")
        assert valid is True
        assert msg == ""

    def test_valid_jpeg(self):
        """Valid JPEG magic bytes pass validation."""
        data = b"\xff\xd8\xff" + b"\x00" * 100
        valid, msg = _validate_asset_magic_bytes(data, ".jpg")
        assert valid is True

    def test_valid_jpeg_alternate_ext(self):
        """Valid JPEG with .jpeg extension passes."""
        data = b"\xff\xd8\xff" + b"\x00" * 100
        valid, msg = _validate_asset_magic_bytes(data, ".jpeg")
        assert valid is True

    def test_valid_pdf(self):
        """Valid PDF magic bytes pass validation."""
        data = b"%PDF-1.4" + b"\x00" * 100
        valid, msg = _validate_asset_magic_bytes(data, ".pdf")
        assert valid is True

    def test_valid_zip(self):
        """Valid ZIP magic bytes pass validation."""
        data = b"PK\x03\x04" + b"\x00" * 100
        valid, msg = _validate_asset_magic_bytes(data, ".zip")
        assert valid is True

    def test_valid_gif(self):
        """Valid GIF magic bytes pass validation."""
        data = b"GIF89a" + b"\x00" * 100
        valid, msg = _validate_asset_magic_bytes(data, ".gif")
        assert valid is True

    def test_valid_webp(self):
        """Valid WEBP magic bytes pass validation."""
        data = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 100
        valid, msg = _validate_asset_magic_bytes(data, ".webp")
        assert valid is True

    def test_invalid_png_magic_bytes(self):
        """Wrong magic bytes for PNG are detected."""
        data = b"not a png" + b"\x00" * 100
        valid, msg = _validate_asset_magic_bytes(data, ".png")
        assert valid is False
        assert "mismatch" in msg.lower()

    def test_file_too_small(self):
        """File smaller than expected magic bytes size is caught."""
        data = b"\x89"  # Only 1 byte, PNG needs 4
        valid, msg = _validate_asset_magic_bytes(data, ".png")
        assert valid is False
        assert "too small" in msg.lower()

    def test_unknown_extension_passes(self):
        """Unknown extensions are not validated (return True)."""
        valid, msg = _validate_asset_magic_bytes(b"anything", ".xyz")
        assert valid is True
        assert msg == ""

    def test_webp_riff_but_not_webp(self):
        """RIFF header without WEBP signature is detected."""
        data = b"RIFF" + b"\x00\x00\x00\x00" + b"AVI " + b"\x00" * 100
        valid, msg = _validate_asset_magic_bytes(data, ".webp")
        assert valid is False
        assert "not WEBP" in msg

    def test_case_insensitive_extension(self):
        """Extension comparison is case-insensitive."""
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        valid, msg = _validate_asset_magic_bytes(data, ".PNG")
        assert valid is True


# =============================================================================
# _guess_mime_type
# =============================================================================


class TestGuessMimeType:
    """Tests for MIME type guessing."""

    def test_png(self):
        assert _guess_mime_type(Path("image.png")) == "image/png"

    def test_jpeg(self):
        assert _guess_mime_type(Path("photo.jpg")) == "image/jpeg"

    def test_pdf(self):
        assert _guess_mime_type(Path("doc.pdf")) == "application/pdf"

    def test_python(self):
        mime = _guess_mime_type(Path("script.py"))
        assert "python" in mime.lower() or "text" in mime.lower()

    def test_unknown_extension(self):
        """Unknown extension falls back to application/octet-stream."""
        assert _guess_mime_type(Path("file.xyz123")) == "application/octet-stream"

    def test_no_extension(self):
        """File with no extension returns octet-stream."""
        assert _guess_mime_type(Path("Makefile")) == "application/octet-stream"


# =============================================================================
# _suggest_asset_subfolder
# =============================================================================


class TestSuggestAssetSubfolder:
    """Tests for asset subfolder suggestions."""

    def test_image_extensions(self):
        """Image extensions suggest 'images' subfolder."""
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp"]:
            assert _suggest_asset_subfolder(f"file{ext}") == "images", f"Failed for {ext}"

    def test_document_extensions(self):
        """Document extensions suggest 'reports' subfolder."""
        for ext in [".pdf", ".docx", ".doc", ".txt", ".csv", ".xlsx", ".xls"]:
            assert _suggest_asset_subfolder(f"file{ext}") == "reports", f"Failed for {ext}"

    def test_presentation_extensions(self):
        """Presentation extensions suggest 'presentations' subfolder."""
        for ext in [".pptx", ".ppt", ".key"]:
            assert _suggest_asset_subfolder(f"file{ext}") == "presentations", f"Failed for {ext}"

    def test_video_extensions(self):
        """Video extensions suggest 'videos' subfolder."""
        for ext in [".mp4", ".mov", ".avi", ".webm"]:
            assert _suggest_asset_subfolder(f"file{ext}") == "videos", f"Failed for {ext}"

    def test_audio_extensions(self):
        """Audio extensions suggest 'audio' subfolder."""
        for ext in [".mp3", ".wav", ".m4a", ".ogg"]:
            assert _suggest_asset_subfolder(f"file{ext}") == "audio", f"Failed for {ext}"

    def test_archive_extensions(self):
        """Archive extensions suggest 'archives' subfolder."""
        for ext in [".zip", ".tar", ".gz", ".rar"]:
            assert _suggest_asset_subfolder(f"file{ext}") == "archives", f"Failed for {ext}"

    def test_unknown_extension(self):
        """Unknown extension returns empty string."""
        assert _suggest_asset_subfolder("file.xyz") == ""

    def test_no_extension(self):
        """File with no extension returns empty string."""
        assert _suggest_asset_subfolder("Makefile") == ""


# =============================================================================
# _detect_language
# =============================================================================


class TestDetectLanguage:
    """Tests for Unicode-based language detection."""

    def test_english_text(self):
        """English text is detected as 'en'."""
        assert _detect_language("Hello world, this is a test") == "en"

    def test_hebrew_text(self):
        """Hebrew text is detected as 'he'."""
        assert _detect_language("\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd") == "he"

    def test_arabic_text(self):
        """Arabic text is detected as 'ar'."""
        assert _detect_language("\u0645\u0631\u062d\u0628\u0627 \u0628\u0627\u0644\u0639\u0627\u0644\u0645") == "ar"

    def test_chinese_text(self):
        """Chinese text is detected as 'zh'."""
        assert _detect_language("\u4f60\u597d\u4e16\u754c") == "zh"

    def test_empty_string(self):
        """Empty string returns None."""
        assert _detect_language("") is None

    def test_numbers_only(self):
        """String with only numbers returns None (no script detected)."""
        assert _detect_language("1234567890") is None

    def test_mixed_but_majority_english(self):
        """Mixed text with majority English characters detects as 'en'."""
        text = "Hello world " + "\u05e9\u05dc"  # mostly English with a bit of Hebrew
        assert _detect_language(text) == "en"


# =============================================================================
# _score_skill_match
# =============================================================================


class TestScoreSkillMatch:
    """Tests for skill content scoring logic."""

    @pytest.fixture
    def career_profile(self) -> dict[str, Any]:
        """Sample career skill profile."""
        return {
            "skill_name": "career",
            "bundle": "career",
            "keywords": ["job", "interview", "resume", "career"],
            "languages": ["en"],
            "company_name": "TechCorp",
            "description": "Career management",
            "domain_dirs": ["applications", "interviews"],
            "has_posts": True,
            "has_assets": True,
        }

    def test_language_match_boosts_score(self, career_profile):
        """Matching language adds to score."""
        score_with_lang = _score_skill_match(career_profile, "job application", "en", None)
        score_without_lang = _score_skill_match(career_profile, "job application", "fr", None)
        assert score_with_lang > score_without_lang

    def test_company_name_match_boosts_score(self, career_profile):
        """Content containing company name gets a significant boost."""
        score_with_company = _score_skill_match(career_profile, "Work at TechCorp", None, None)
        score_without = _score_skill_match(career_profile, "Work at OtherCo", None, None)
        assert score_with_company > score_without

    def test_keyword_overlap_boosts_score(self, career_profile):
        """Content with matching keywords scores higher."""
        score_with_keywords = _score_skill_match(career_profile, "job interview resume", None, None)
        score_without = _score_skill_match(career_profile, "cooking recipe dinner", None, None)
        assert score_with_keywords > score_without

    def test_has_posts_bonus(self, career_profile):
        """Content-producing skills get a small bonus."""
        score_with_posts = _score_skill_match(career_profile, "test", None, None)
        career_profile["has_posts"] = False
        score_without_posts = _score_skill_match(career_profile, "test", None, None)
        assert score_with_posts > score_without_posts

    def test_score_capped_at_one(self, career_profile):
        """Score never exceeds 1.0."""
        # Load everything for maximum score
        content = "TechCorp job interview resume career applications"
        score = _score_skill_match(career_profile, content, "en", None)
        assert score <= 1.0

    def test_zero_score_for_no_match(self):
        """Empty profile with no matching signals scores 0."""
        empty_profile = {
            "skill_name": "empty",
            "keywords": [],
            "languages": [],
            "company_name": None,
            "domain_dirs": [],
            "has_posts": False,
        }
        score = _score_skill_match(empty_profile, "anything", None, None)
        assert score == 0.0

    def test_domain_dir_match(self, career_profile):
        """Content words matching domain dirs add to score."""
        score = _score_skill_match(career_profile, "applications interviews", None, None)
        assert score > 0.0
