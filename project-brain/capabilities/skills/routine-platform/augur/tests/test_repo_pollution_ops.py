"""Tests for auto-repo-pollution scan/fix protocol."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "repo_pollution_ops.py"
_SPEC = importlib.util.spec_from_file_location("repo_pollution_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _git_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    return root


def _ctx(root: Path, **kw) -> OpsContext:
    return OpsContext(project_root=root, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-repo-pollution"


def test_scan_not_a_git_repo(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert "Not a git repo" in result.summary


def test_scan_clean_tree(tmp_path: Path) -> None:
    root = _git_repo(tmp_path)
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("x = 1\n")
    result = mod.scan(_ctx(root))
    assert result.issues == []
    assert result.severity == "info"


def test_scan_detects_all_pollution_kinds(tmp_path: Path) -> None:
    root = _git_repo(tmp_path)
    (root / ".DS_Store").write_text("junk")
    (root / "tmp_audio.wav").write_bytes(b"\x00")
    (root / "browser-proof-task.png").write_bytes(b"\x89PNG")
    (root / "real-report.pdf").write_bytes(b"%PDF")
    # orphan pycache: no sibling .py left
    (root / "lib" / "__pycache__").mkdir(parents=True)
    (root / "lib" / "__pycache__" / "m.cpython-312.pyc").write_bytes(b"\x00")
    # active pycache: sibling .py exists — must NOT be flagged
    (root / "src" / "__pycache__").mkdir(parents=True)
    (root / "src" / "__pycache__" / "live.cpython-312.pyc").write_bytes(b"\x00")
    (root / "src" / "live.py").write_text("x = 1\n")
    (root / "empty-husk").mkdir()

    result = mod.scan(_ctx(root))
    by_cat = {}
    for issue in result.issues:
        by_cat.setdefault(issue["category"], []).append(issue)

    assert "os-junk" in by_cat
    orphan_paths = [i["path"] for i in by_cat.get("orphan-pycache", [])]
    assert any("lib" in p for p in orphan_paths)
    assert not any("src" in p for p in orphan_paths)
    assert "empty-dir" in by_cat
    artifacts = {Path(i["path"]).name for i in by_cat.get("session-artifact", [])}
    assert artifacts == {"tmp_audio.wav", "browser-proof-task.png"}
    strays = {Path(i["path"]).name for i in by_cat.get("stray-binary", [])}
    assert strays == {"real-report.pdf"}


def test_scan_skips_tracked_binaries_and_build_dir(tmp_path: Path) -> None:
    root = _git_repo(tmp_path)
    asset = root / "docs" / "logo.png"
    asset.parent.mkdir()
    asset.write_bytes(b"\x89PNG")
    subprocess.run(["git", "add", "docs/logo.png"], cwd=str(root), check=True)
    (root / "build" / "out").mkdir(parents=True)
    (root / "build" / "out" / "bundle.zip").write_bytes(b"PK")

    result = mod.scan(_ctx(root))
    paths = [i["path"] for i in result.issues]
    assert not any("logo.png" in p for p in paths)
    assert not any("bundle.zip" in p for p in paths)


def test_fix_removes_auto_items_keeps_work_products(tmp_path: Path) -> None:
    root = _git_repo(tmp_path)
    (root / ".DS_Store").write_text("junk")
    (root / "merge-verify-chat.png").write_bytes(b"\x89PNG")
    keeper = root / "quarterly-report.pdf"
    keeper.write_bytes(b"%PDF")
    (root / "empty-husk").mkdir()

    scan_result = mod.scan(_ctx(root))
    fix_result = mod.fix(_ctx(root, difficulty=1), list(scan_result.issues))

    assert isinstance(fix_result, FixResult)
    assert fix_result.success is True
    assert not (root / ".DS_Store").exists()
    assert not (root / "merge-verify-chat.png").exists()
    assert not (root / "empty-husk").exists()
    assert keeper.exists()
    assert "manual item(s) reported" in fix_result.summary


def test_fix_dry_run_changes_nothing(tmp_path: Path) -> None:
    root = _git_repo(tmp_path)
    junk = root / ".DS_Store"
    junk.write_text("junk")
    scan_result = mod.scan(_ctx(root))
    result = mod.fix(_ctx(root, difficulty=1, dry_run=True), list(scan_result.issues))
    assert result.success is True
    assert junk.exists()


def test_scan_skips_nested_git_checkouts(tmp_path: Path) -> None:
    """Worktrees/embedded checkouts are separate trees — never scanned (rule 24)."""
    root = _git_repo(tmp_path)
    worktree = root / ".claude" / "worktrees" / "wt-x"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: elsewhere\n")
    (worktree / "proof-browser-verify.png").write_bytes(b"\x89PNG")

    result = mod.scan(_ctx(root))
    assert not any("wt-x" in i["path"] for i in result.issues)


def test_scan_ignores_symlinked_dirs(tmp_path: Path) -> None:
    """Symlinked cache dirs (ADR-270 redirection) are not pollution."""
    root = _git_repo(tmp_path)
    target = tmp_path / "external-cache"
    target.mkdir()
    (root / ".mypy_cache").symlink_to(target)

    result = mod.scan(_ctx(root))
    assert not any("mypy_cache" in i["path"] for i in result.issues)


def test_fix_cascades_newly_empty_parents(tmp_path: Path) -> None:
    root = _git_repo(tmp_path)
    leaf = root / "a" / "b" / "c"
    leaf.mkdir(parents=True)

    scan_result = mod.scan(_ctx(root))
    mod.fix(_ctx(root, difficulty=1), list(scan_result.issues))
    assert not (root / "a").exists()
