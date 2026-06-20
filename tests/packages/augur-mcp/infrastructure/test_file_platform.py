"""
Tests for platform detection, security layer, and file utilities (infrastructure/file_platform.py).

Validates path security (traversal detection, allowed roots enforcement),
cross-platform utilities, and safe file operations.

Run with: pytest tests/packages/augur-mcp/infrastructure/test_file_platform.py -v
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.mcp.augur_framework.tools.infrastructure.file_platform import (
    IS_WINDOWS,
    get_safe_encoding,
    normalize_path,
    resolve_secure_path,
    retry_on_windows_error,
    safe_copy,
    safe_delete,
    safe_rename,
    validate_path_within_roots,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_roots(tmp_path: Path, monkeypatch):
    """Set up isolated allowed root directories."""
    code_dir = tmp_path / "code"
    data_dir = tmp_path / "data"
    runtime_dir = tmp_path / "runtime"
    code_dir.mkdir()
    data_dir.mkdir()
    runtime_dir.mkdir()

    roots = {"code": code_dir, "data": data_dir, "runtime": runtime_dir}
    monkeypatch.setattr("src.mcp.augur_framework.tools.infrastructure.file_platform._ALLOWED_ROOTS", roots)
    monkeypatch.setattr("src.mcp.augur_framework.tools.infrastructure.file_platform.get_allowed_roots", lambda: roots)
    return roots


# =============================================================================
# Platform Detection
# =============================================================================


class TestPlatformDetection:
    """Tests for platform detection constants."""

    def test_is_windows_is_bool(self):
        """IS_WINDOWS is a boolean."""
        assert isinstance(IS_WINDOWS, bool)

    def test_normalize_path_noop_on_unix(self):
        """On non-Windows, normalize_path returns the path unchanged."""
        if not IS_WINDOWS:
            p = Path("/some/path")
            assert normalize_path(p) == p

    def test_get_safe_encoding_default(self):
        """On non-Windows, get_safe_encoding returns utf-8 as-is."""
        if not IS_WINDOWS:
            assert get_safe_encoding("utf-8") == "utf-8"
            assert get_safe_encoding("latin-1") == "latin-1"


# =============================================================================
# retry_on_windows_error
# =============================================================================


class TestRetryOnWindowsError:
    """Tests for retry_on_windows_error utility."""

    def test_succeeds_on_first_try(self):
        """Function that succeeds immediately returns its result."""
        result = retry_on_windows_error(lambda: 42)
        assert result == 42

    def test_raises_non_retryable_error(self):
        """Non-retryable errors are raised immediately."""

        def _fail():
            raise ValueError("not retryable")

        with pytest.raises(ValueError, match="not retryable"):
            retry_on_windows_error(_fail, retry_errors=(PermissionError,))

    def test_retries_on_permission_error(self):
        """PermissionError triggers retry."""
        call_count = 0

        def _fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise PermissionError("locked")
            return "ok"

        with patch("src.mcp.augur_framework.tools.infrastructure.file_platform.time.sleep"):
            result = retry_on_windows_error(_fail_then_succeed, max_retries=5)
        assert result == "ok"
        assert call_count == 3

    def test_exhausted_retries_raises(self):
        """After max_retries, the last error is raised."""

        def _always_fail():
            raise PermissionError("always locked")

        with patch("src.mcp.augur_framework.tools.infrastructure.file_platform.time.sleep"):
            with pytest.raises(PermissionError, match="always locked"):
                retry_on_windows_error(_always_fail, max_retries=3)


# =============================================================================
# safe_delete
# =============================================================================


class TestSafeDelete:
    """Tests for safe_delete utility."""

    def test_delete_existing_file(self, tmp_path: Path):
        """Deletes an existing file and returns True."""
        f = tmp_path / "test.txt"
        f.write_text("content")
        assert safe_delete(f) is True
        assert not f.exists()

    def test_delete_nonexistent_returns_false(self, tmp_path: Path):
        """Returns False for nonexistent path."""
        assert safe_delete(tmp_path / "nope.txt") is False

    def test_delete_empty_directory(self, tmp_path: Path):
        """Deletes an empty directory."""
        d = tmp_path / "empty_dir"
        d.mkdir()
        assert safe_delete(d) is True
        assert not d.exists()


# =============================================================================
# safe_rename
# =============================================================================


class TestSafeRename:
    """Tests for safe_rename utility."""

    def test_rename_file(self, tmp_path: Path):
        """Renames a file from source to destination."""
        src = tmp_path / "old.txt"
        dst = tmp_path / "new.txt"
        src.write_text("content")

        safe_rename(src, dst)
        assert not src.exists()
        assert dst.read_text() == "content"

    def test_rename_overwrites_destination(self, tmp_path: Path):
        """On Unix, replace() overwrites destination."""
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("new content")
        dst.write_text("old content")

        safe_rename(src, dst)
        assert dst.read_text() == "new content"


# =============================================================================
# safe_copy
# =============================================================================


class TestSafeCopy:
    """Tests for safe_copy utility."""

    def test_copy_file(self, tmp_path: Path):
        """Copies file preserving metadata."""
        src = tmp_path / "original.txt"
        dst = tmp_path / "copy.txt"
        src.write_text("hello")

        safe_copy(src, dst)
        assert src.exists()
        assert dst.read_text() == "hello"


# =============================================================================
# validate_path_within_roots
# =============================================================================


class TestValidatePathWithinRoots:
    """Tests for path security validation."""

    def test_valid_path_within_root(self, mock_roots):
        """Path within an allowed root passes validation."""
        valid_path = mock_roots["code"] / "src" / "main.py"
        valid_path.parent.mkdir(parents=True, exist_ok=True)
        valid_path.touch()
        # Should not raise
        validate_path_within_roots(valid_path)

    def test_path_outside_roots_raises(self, mock_roots):
        """Path outside all roots raises PermissionError."""
        outside_path = Path("/tmp/evil/path")
        with pytest.raises(PermissionError, match="outside allowed"):
            validate_path_within_roots(outside_path)

    def test_root_itself_is_valid(self, mock_roots):
        """The root directory itself is a valid path."""
        validate_path_within_roots(mock_roots["code"])


# =============================================================================
# resolve_secure_path
# =============================================================================


class TestResolveSecurePath:
    """Tests for secure path resolution."""

    def test_relative_path_code_repo(self, mock_roots):
        """Relative path resolved against code repo."""
        resolved, repo = resolve_secure_path("src/main.py", "code")
        assert repo == "code"
        assert str(mock_roots["code"]) in str(resolved)

    def test_relative_path_auto_detection(self, mock_roots):
        """Auto mode resolves relative path against available repos."""
        resolved, repo = resolve_secure_path("src/main.py", "auto")
        assert repo in ("data", "code", "runtime")

    def test_absolute_path_within_root(self, mock_roots):
        """Absolute path within an allowed root is accepted."""
        abs_path = str(mock_roots["code"] / "main.py")
        resolved, repo = resolve_secure_path(abs_path, "code")
        assert repo == "code"

    def test_absolute_path_outside_roots_raises(self, mock_roots):
        """Absolute path outside allowed roots raises ValueError."""
        with pytest.raises(ValueError, match="outside allowed"):
            resolve_secure_path("/etc/passwd", "code")

    def test_unavailable_repo_raises(self, mock_roots, monkeypatch):
        """Requesting a repo that doesn't exist in roots raises ValueError."""
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.file_platform.get_allowed_roots",
            lambda: {"code": mock_roots["code"]},
        )
        with pytest.raises(ValueError, match="not available"):
            resolve_secure_path("file.txt", "data")

    def test_runtime_prefix_stripped(self, mock_roots):
        """Path starting with 'runtime/' resolves within runtime root."""
        resolved, repo = resolve_secure_path("runtime/logs/app.log", "auto")
        assert repo == "runtime"
        # The 'runtime' prefix should be stripped from the resolved path
        assert "runtime/runtime" not in str(resolved)

    def test_traversal_attempt_rejected(self, mock_roots):
        """Path that escapes root via symlink traversal is caught."""
        # Trying a relative path that navigates above root
        with pytest.raises(ValueError):
            resolve_secure_path("../../../../etc/passwd", "code")


# =============================================================================
# Indexed document-source roots (Desktop / Downloads)
# =============================================================================


class TestDocumentSourceRootsAllowed:
    """Indexed document-source roots must resolve as allowed repositories.

    Regression (2026-06): Browse indexes Desktop and Downloads via
    ``default_document_sources``, but ``file-info`` rejected those absolute
    paths as ``outside allowed repositories``, so users could not reveal or
    open an indexed Desktop/Downloads document.
    """

    def test_absolute_desktop_path_resolves(self, tmp_path: Path, monkeypatch):
        """An absolute path inside the indexed Desktop source resolves."""
        import src.mcp.augur_framework.tools.infrastructure.file_platform as fp

        for name in ("code", "vault", "documents", "runtime", "logs"):
            (tmp_path / name).mkdir()
        desktop = tmp_path / "Desktop"
        desktop.mkdir()
        doc = desktop / "report.doc"
        doc.write_text("x")

        monkeypatch.setattr(fp, "_ALLOWED_ROOTS", {})
        monkeypatch.setattr(fp, "get_project_root", lambda: tmp_path / "code")
        monkeypatch.setattr(fp, "get_vault_dir", lambda: tmp_path / "vault")
        monkeypatch.setattr(fp, "get_documents_dir", lambda: tmp_path / "documents")
        monkeypatch.setattr(fp, "get_runtime_dir", lambda: tmp_path / "runtime")
        monkeypatch.setattr(fp, "get_logs_dir", lambda: tmp_path / "logs")
        # default_document_sources derives Desktop/Downloads from Path.home().
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        resolved, repo = resolve_secure_path(str(doc), "auto")
        assert resolved == doc.resolve()
        assert repo == "desktop"
