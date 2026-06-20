"""Tests for client config directory resolution."""

import os
import pytest
from unittest.mock import patch
from pathlib import Path


class TestGetClientConfigDir:
    def test_claude_code_global_default(self):
        from src.config.paths import get_client_config_dir

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUGUR_CLAUDE_CONFIG", None)
            result = get_client_config_dir("claude-code")
            assert result == Path.home() / ".claude"

    def test_codex_global_default(self):
        from src.config.paths import get_client_config_dir

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUGUR_CODEX_CONFIG", None)
            result = get_client_config_dir("codex")
            assert result == Path.home() / ".codex"

    def test_gemini_global_default(self):
        from src.config.paths import get_client_config_dir

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUGUR_GEMINI_CONFIG", None)
            result = get_client_config_dir("gemini")
            assert result == Path.home() / ".gemini"

    def test_env_override(self):
        from src.config.paths import get_client_config_dir

        with patch.dict(os.environ, {"AUGUR_CLAUDE_CONFIG": "/custom/path"}):
            result = get_client_config_dir("claude-code")
            assert result == Path("/custom/path")

    def test_project_scope_returns_cwd_relative(self):
        from src.config.paths import get_client_config_dir

        result = get_client_config_dir("claude-code", scope="project")
        assert result == Path.cwd() / ".claude"

    def test_unknown_client_raises(self):
        from src.config.paths import get_client_config_dir

        with pytest.raises(ValueError, match="Unknown client"):
            get_client_config_dir("unknown-client")


class TestGetClientRuntimeDir:
    def test_claude_code_runtime_dir(self):
        from src.config.paths import get_client_runtime_dir

        result = get_client_runtime_dir("claude-code")
        assert result == Path.home() / ".claude"

    def test_codex_runtime_dir(self):
        from src.config.paths import get_client_runtime_dir

        result = get_client_runtime_dir("codex")
        assert result == Path.home() / ".codex"

    def test_gemini_runtime_dir(self):
        from src.config.paths import get_client_runtime_dir

        result = get_client_runtime_dir("gemini")
        assert result == Path.home() / ".gemini"

    def test_antigravity_runtime_dir(self):
        from src.config.paths import get_client_runtime_dir

        result = get_client_runtime_dir("antigravity")
        assert result == Path.home() / ".gemini" / "antigravity"

    def test_claude_desktop_runtime_dir_darwin(self):
        from src.config.paths import get_client_runtime_dir

        with patch("src.config.paths.sys.platform", "darwin"):
            result = get_client_runtime_dir("claude-desktop")
        assert result == Path.home() / "Library" / "Application Support" / "Claude"

    def test_claude_desktop_runtime_dir_windows_prefers_appdata(self):
        from src.config.paths import get_client_runtime_dir

        with patch("src.config.paths.sys.platform", "win32"), patch.dict(
            os.environ,
            {"APPDATA": r"C:\Users\tester\AppData\Roaming"},
            clear=False,
        ):
            result = get_client_runtime_dir("claude-desktop")

        assert result == Path(r"C:\Users\tester\AppData\Roaming") / "Claude"


class TestClaudeNativeMemoryDir:
    def test_encode_claude_project_path_strips_windows_path_separators(self):
        from src.config.paths import encode_claude_project_path

        encoded = encode_claude_project_path(r"C:\Users\tester\Projects\Augur")

        assert encoded == "C--Users-tester-Projects-Augur"
        assert "\\" not in encoded
        assert ":" not in encoded

    def test_get_claude_native_memory_dir_stays_under_claude_state_root(self, tmp_path):
        from src.config.paths import get_claude_native_memory_dir

        home = tmp_path / "home"
        project_root = r"C:\Users\tester\Projects\Augur"
        project_state = home / ".claude" / "projects" / "C--Users-tester-Projects-Augur"
        project_state.mkdir(parents=True)

        with patch("src.config.paths.Path.home", return_value=home):
            result = get_claude_native_memory_dir(project_root, create=True)

        assert result == project_state / "memory"
        assert result.is_dir()


class TestGetPythonExecutable:
    def test_get_python_executable_prefers_windows_venv(self, tmp_path):
        from src.config.paths import get_python_executable

        venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text("")

        with patch("src.config.paths.get_project_root", return_value=tmp_path), patch(
            "src.config.paths.os.name",
            "nt",
        ):
            result = get_python_executable()

        assert result == venv_python
