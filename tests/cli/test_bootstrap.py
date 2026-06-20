"""Tests for CLI bootstrap path resolution (ADR-258)."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cli_bootstrap import (
    resolve_project_root,
    configure_sys_path,
    _is_repo_checkout,
    _ensure_user_dir,
    should_reexec_cli_from_project_root,
)


@pytest.fixture(autouse=True)
def preserve_src_modules():
    """CLI bootstrap tests intentionally mutate src.* module bindings."""
    saved = {name: module for name, module in sys.modules.items() if name == "src" or name.startswith("src.")}
    yield
    for name in list(sys.modules):
        if (name == "src" or name.startswith("src.")) and name not in saved:
            sys.modules.pop(name, None)
    sys.modules.update(saved)


class TestResolveProjectRoot:
    def test_augur_root_env_var_takes_precedence(self, tmp_path):
        """AUGUR_ROOT env var should win when cwd is not an Augur checkout."""
        non_repo = tmp_path / "outside"
        non_repo.mkdir()
        with patch.dict(os.environ, {"AUGUR_ROOT": str(tmp_path)}):
            with patch("src.cli_bootstrap.Path.cwd", return_value=non_repo):
                result = resolve_project_root()
                assert result == tmp_path

    def test_cwd_worktree_overrides_stale_augur_root(self, tmp_path):
        """Running aug inside a worktree should not import state from main."""
        main_root = tmp_path / "Augur"
        worktree_root = tmp_path / "augur-wt"
        (main_root / "src" / "mcp" / "augur_shared").mkdir(parents=True)
        (worktree_root / "src" / "mcp" / "augur_shared").mkdir(parents=True)

        with patch.dict(os.environ, {"AUGUR_ROOT": str(main_root)}):
            with patch("src.cli_bootstrap.Path.cwd", return_value=worktree_root):
                result = resolve_project_root()
                assert result == worktree_root

    def test_repo_checkout_detected(self):
        """When running from repo without AUGUR_ROOT, should detect the checkout."""
        env = os.environ.copy()
        env.pop("AUGUR_ROOT", None)
        with patch.dict(os.environ, env, clear=True):
            result = resolve_project_root()
            assert _is_repo_checkout(result)
            assert (result / "src" / "mcp" / "augur_shared").is_dir()

    def test_user_dir_fallback(self, tmp_path):
        """When not in repo and no AUGUR_ROOT, falls back to ~/.augur/."""
        env = os.environ.copy()
        env.pop("AUGUR_ROOT", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("src.cli_bootstrap._is_repo_checkout", return_value=False):
                with patch("src.cli_bootstrap._get_user_dir", return_value=tmp_path / ".augur"):
                    result = resolve_project_root()
                    assert result == tmp_path / ".augur"

    def test_is_repo_checkout_true(self, tmp_path):
        """_is_repo_checkout returns True when augur_mcp exists."""
        (tmp_path / "src" / "mcp" / "augur_shared").mkdir(parents=True)
        assert _is_repo_checkout(tmp_path)

    def test_is_repo_checkout_false(self, tmp_path):
        """_is_repo_checkout returns False for arbitrary dirs."""
        assert not _is_repo_checkout(tmp_path)


class TestEnsureUserDir:
    def test_creates_minimal_structure(self, tmp_path):
        with patch("src.cli_bootstrap.Path.home", return_value=tmp_path):
            result = _ensure_user_dir()
            assert result == tmp_path / ".augur"
            assert (result / "config").is_dir()
            assert (result / "state").is_dir()
            assert (result / "state" / "sessions").is_dir()
            assert (result / "plugins").is_dir()

    def test_idempotent(self, tmp_path):
        """Calling twice doesn't fail."""
        with patch("src.cli_bootstrap.Path.home", return_value=tmp_path):
            _ensure_user_dir()
            _ensure_user_dir()
            assert (tmp_path / ".augur" / "config").is_dir()


class TestConfigureSysPath:
    def test_removes_src_dir_from_path(self, tmp_path):
        """src/ dir should be removed to prevent stdlib shadowing."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        package_src = tmp_path / "src" / "mcp"
        package_src.mkdir()

        original_path = sys.path.copy()
        sys.path.insert(0, str(src_dir))
        try:
            configure_sys_path(tmp_path)
            assert str(src_dir) not in [str(Path(p).resolve()) for p in sys.path]
            assert str(package_src) in sys.path
        finally:
            sys.path = original_path

    def test_adds_project_root(self, tmp_path):
        (tmp_path / "src" / "mcp").mkdir(parents=True)
        original_path = sys.path.copy()
        try:
            configure_sys_path(tmp_path)
            assert str(tmp_path) in sys.path
        finally:
            sys.path = original_path

    def test_updates_loaded_src_package_to_active_worktree(self, tmp_path):
        """A main-imported console script must not pin src.* imports to main."""
        stale_root = tmp_path / "Augur"
        worktree_root = tmp_path / "augur-wt"
        (stale_root / "src" / "mcp" / "augur_shared").mkdir(parents=True)
        (worktree_root / "src" / "mcp" / "augur_shared").mkdir(parents=True)
        (stale_root / "src" / "__init__.py").write_text("", encoding="utf-8")
        (worktree_root / "src" / "__init__.py").write_text("", encoding="utf-8")

        class LoadedSrc:
            __path__ = [str(stale_root / "src")]
            __file__ = str(stale_root / "src" / "__init__.py")

        previous = sys.modules.get("src")
        sys.modules["src"] = LoadedSrc()
        try:
            configure_sys_path(worktree_root)

            loaded_src = sys.modules["src"]
            assert list(loaded_src.__path__) == [str(worktree_root / "src")]
            assert loaded_src.__file__ == str(worktree_root / "src" / "__init__.py")
        finally:
            if previous is None:
                sys.modules.pop("src", None)
            else:
                sys.modules["src"] = previous


class TestCliReexec:
    def test_reexec_needed_when_console_script_loaded_cli_from_main(self, tmp_path):
        main_root = tmp_path / "Augur"
        worktree_root = tmp_path / "augur-wt"
        main_cli = main_root / "src" / "cli.py"
        main_cli.parent.mkdir(parents=True)
        main_cli.write_text("", encoding="utf-8")
        (worktree_root / "src" / "mcp" / "augur_shared").mkdir(parents=True)

        assert should_reexec_cli_from_project_root(worktree_root, main_cli)

    def test_reexec_not_needed_when_cli_file_is_from_active_root(self, tmp_path):
        worktree_root = tmp_path / "augur-wt"
        active_cli = worktree_root / "src" / "cli.py"
        active_cli.parent.mkdir(parents=True)
        active_cli.write_text("", encoding="utf-8")
        (worktree_root / "src" / "mcp" / "augur_shared").mkdir(parents=True)

        assert not should_reexec_cli_from_project_root(worktree_root, active_cli)
