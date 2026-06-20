"""Tests for adaptive engine commit verification."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DAEMON_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = DAEMON_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_engine_verification_importable():
    """Verify that engine_verification can be imported without errors."""
    mod = importlib.import_module("skills.daemon.scripts.adaptive.engine_verification")
    assert mod is not None


def _git(repo: Path, *args: str) -> str:
    import subprocess

    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_verify_commit_fails_closed_without_cached_baseline(tmp_path):
    from skills.daemon.scripts.adaptive.engine_verification import VerificationMixin

    class Verifier(VerificationMixin):
        pass

    _init_repo(tmp_path)
    source = tmp_path / "source.ts"
    source.write_text("const value = 1;\n", encoding="utf-8")
    _commit_all(tmp_path, "base")
    source.write_text("const value = 2;\n", encoding="utf-8")
    commit_hash = _commit_all(tmp_path, "auto fix")
    engine = Verifier()
    engine._project_root = tmp_path
    engine._verify_command = f"{sys.executable} -c 'import sys; sys.exit(1)'"

    assert engine.verify_commit(commit_hash) is False
    assert source.read_text(encoding="utf-8") == "const value = 1;\n"
    assert _git(tmp_path, "status", "--porcelain") == ""
    assert "revert" in _git(tmp_path, "log", "--oneline", "-1").lower()


def test_verify_commit_reverts_target_commit_without_reverting_later_work(tmp_path):
    from skills.daemon.scripts.adaptive.engine_verification import VerificationMixin

    class Verifier(VerificationMixin):
        pass

    _init_repo(tmp_path)
    source = tmp_path / "source.ts"
    source.write_text("const value = 1;\n", encoding="utf-8")
    _commit_all(tmp_path, "base")

    source.write_text("const value = 2;\n", encoding="utf-8")
    auto_commit = _commit_all(tmp_path, "auto fix")

    notes = tmp_path / "notes.md"
    notes.write_text("user work\n", encoding="utf-8")
    later_commit = _commit_all(tmp_path, "later user work")

    engine = Verifier()
    engine._project_root = tmp_path
    engine._verify_command = f"{sys.executable} -c 'import sys; sys.exit(1)'"

    assert engine.verify_commit(auto_commit) is False
    assert source.read_text(encoding="utf-8") == "const value = 1;\n"
    assert notes.read_text(encoding="utf-8") == "user work\n"
    assert _git(tmp_path, "rev-parse", "HEAD") != later_commit
    assert "auto fix" in _git(tmp_path, "log", "--oneline", "-1")
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_engine_verification_does_not_use_broad_worktree_mutation_fallback():
    source = (
        DAEMON_ROOT / "scripts" / "adaptive" / "engine_verification.py"
    ).read_text(encoding="utf-8")

    assert "git reset --hard" not in source
    assert '"reset", "--hard"' not in source
    assert '"checkout", f"{commit_hash}~1", "--", "."' not in source
    assert '"checkout", "HEAD", "--", "."' not in source
    assert '"stash", "push"' not in source
    assert '"stash", "pop"' not in source
    assert '"clean"' not in source
