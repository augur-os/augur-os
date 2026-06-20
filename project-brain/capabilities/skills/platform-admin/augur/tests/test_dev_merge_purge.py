"""Tests for `/dev-merge --purge` technical-leftover classification."""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import stat
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "dev_merge_purge.py"


def _module():
    module_name = "platform_admin_dev_merge_purge_test"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_classify_dirty_path_marks_known_generated_agent_files_as_technical_leftovers():
    classify_dirty_path = _module().classify_dirty_path

    assert classify_dirty_path(Path("AGENTS.md")) == "technical_leftover"
    assert classify_dirty_path(Path("CLAUDE.md")) == "technical_leftover"
    assert classify_dirty_path(Path("CODEX.md")) == "technical_leftover"
    assert classify_dirty_path(Path(".gemini/GEMINI.md")) == "technical_leftover"
    assert classify_dirty_path(Path(".opencode/AGENTS.md")) == "technical_leftover"
    assert classify_dirty_path(Path(".claude/settings.json")) == "technical_leftover"
    assert classify_dirty_path(Path(".gemini/skills/ingest/SKILL.md")) == "technical_leftover"
    assert classify_dirty_path(Path(".venv/bin/python")) == "technical_leftover"
    assert classify_dirty_path(Path("project-brain/BRAIN.yaml")) == "technical_leftover"
    assert classify_dirty_path(Path("project-brain/config/inventory/ai-artifacts.json")) == "technical_leftover"


def test_classify_dirty_path_rejects_meaningful_repo_changes():
    classify_dirty_path = _module().classify_dirty_path

    assert classify_dirty_path(Path("src/app.py")) == "meaningful_repo_change"
    assert classify_dirty_path(Path("docs/spec.md")) == "meaningful_repo_change"
    assert classify_dirty_path(Path("plugins/agents/dev-merge.md")) == "meaningful_repo_change"
    assert classify_dirty_path(Path("scripts/ai-launch.sh")) == "meaningful_repo_change"


def test_classify_dirty_path_marks_unknown_paths_as_ambiguous():
    classify_dirty_path = _module().classify_dirty_path

    assert classify_dirty_path(Path("tmp/random-artifact.txt")) == "ambiguous"


def test_dirty_paths_parses_modified_and_untracked_entries_without_trimming(tmp_path: Path):
    mod = _module()
    repo = _init_repo(tmp_path)

    (repo / "docs").mkdir()
    (repo / "docs" / "notes.md").write_text("draft\n")
    _git(repo, "add", "docs/notes.md")
    _git(repo, "commit", "-m", "add notes")
    (repo / "docs" / "notes.md").write_text("changed\n")
    (repo / "plugins").mkdir()
    (repo / "plugins" / "scratch.txt").write_text("new\n")

    assert mod._dirty_paths(repo) == ["docs/notes.md", "plugins/scratch.txt"]


def test_decide_purgeability_requires_no_clean_salvage_and_only_technical_leftovers():
    decide_purgeability = _module().decide_purgeability

    purgeable = decide_purgeability(
        commit_classes=["already_in_main", "stale_or_conflicting"],
        dirty_classes=["technical_leftover", "technical_leftover"],
    )
    blocked_by_commit = decide_purgeability(
        commit_classes=["already_in_main", "clean_salvage"],
        dirty_classes=["technical_leftover"],
    )
    blocked_by_dirty = decide_purgeability(
        commit_classes=["already_in_main"],
        dirty_classes=["meaningful_repo_change"],
    )
    blocked_by_ambiguous = decide_purgeability(
        commit_classes=["already_in_main"],
        dirty_classes=["ambiguous"],
    )

    assert purgeable == ("purged", None)
    assert blocked_by_commit == ("skipped_merge_worthy_commits", "clean_salvage")
    assert blocked_by_dirty == ("skipped_meaningful_changes", "meaningful_repo_change")
    assert blocked_by_ambiguous == ("skipped_ambiguous_leftovers", "ambiguous")


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Codex")
    _git(repo, "config", "user.email", "codex@example.com")
    (repo / "README.md").write_text("root\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    return repo


def test_inventory_leftover_candidates_marks_technical_only_branch_as_purgeable(tmp_path: Path):
    mod = _module()
    repo = _init_repo(tmp_path)

    _git(repo, "checkout", "-b", "codex/leftover-tech")
    (repo / "AGENTS.md").write_text("generated\n")
    _git(repo, "add", "AGENTS.md")
    _git(repo, "commit", "-m", "agent sync")
    _git(repo, "checkout", "main")

    candidates = mod.inventory_leftover_candidates(repo, target_branch="main")
    candidate = next(item for item in candidates if item.branch == "codex/leftover-tech")

    assert candidate.commit_classes == ["stale_or_conflicting"]
    assert candidate.dirty_classes == []
    assert mod.decide_purgeability(
        commit_classes=candidate.commit_classes,
        dirty_classes=candidate.dirty_classes,
    ) == ("purged", None)


def test_inventory_leftover_candidates_blocks_branch_with_meaningful_commit(tmp_path: Path):
    mod = _module()
    repo = _init_repo(tmp_path)

    _git(repo, "checkout", "-b", "codex/leftover-real")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "ai-launch.sh").write_text("#!/bin/sh\n")
    _git(repo, "add", "scripts/ai-launch.sh")
    _git(repo, "commit", "-m", "real change")
    _git(repo, "checkout", "main")

    candidates = mod.inventory_leftover_candidates(repo, target_branch="main")
    candidate = next(item for item in candidates if item.branch == "codex/leftover-real")

    assert candidate.commit_classes == ["clean_salvage"]
    assert mod.decide_purgeability(
        commit_classes=candidate.commit_classes,
        dirty_classes=candidate.dirty_classes,
    ) == ("skipped_merge_worthy_commits", "clean_salvage")


def test_purge_candidate_removes_purgeable_branch(tmp_path: Path):
    mod = _module()
    repo = _init_repo(tmp_path)

    _git(repo, "checkout", "-b", "codex/leftover-tech")
    (repo / "AGENTS.md").write_text("generated\n")
    _git(repo, "add", "AGENTS.md")
    _git(repo, "commit", "-m", "agent sync")
    _git(repo, "checkout", "main")

    candidate = next(
        item
        for item in mod.inventory_leftover_candidates(repo, target_branch="main")
        if item.branch == "codex/leftover-tech"
    )
    result = mod.purge_candidate(repo, candidate, dry_run=False)

    branches = _git(repo, "branch", "--format=%(refname:short)").splitlines()

    assert result.status == "purged"
    assert result.branch_deleted is True
    assert "codex/leftover-tech" not in branches


def test_purge_candidate_repairs_codex_threads_for_removed_worktree(tmp_path: Path):
    mod = _module()
    repo = _init_repo(tmp_path)
    worktree_path = tmp_path / "augur-wt-leftover"
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    _git(repo, "worktree", "add", str(worktree_path), "-b", "codex/leftover-tech")
    (worktree_path / "AGENTS.md").write_text("generated\n")
    _git(worktree_path, "add", "AGENTS.md")
    _git(worktree_path, "commit", "-m", "agent sync")

    with sqlite3.connect(codex_home / "state_5.sqlite") as conn:
        conn.execute(
            "create table threads (id text, cwd text, git_branch text, git_sha text)"
        )
        conn.execute(
            "insert into threads values (?, ?, ?, ?)",
            ("thread-1", str(worktree_path), "codex/leftover-tech", "old-sha"),
        )

    candidate = next(
        item
        for item in mod.inventory_leftover_candidates(repo, target_branch="main")
        if item.branch == "codex/leftover-tech"
    )
    result = mod.purge_candidate(repo, candidate, dry_run=False, codex_home=codex_home)

    with sqlite3.connect(codex_home / "state_5.sqlite") as conn:
        row = conn.execute("select cwd, git_branch, git_sha from threads").fetchone()

    assert result.status == "purged"
    assert result.worktree_removed is True
    assert worktree_path.exists() is False
    assert row == (str(repo.resolve()), "main", _git(repo, "rev-parse", "HEAD"))


def test_purge_candidate_removes_orphaned_directory_after_partial_git_worktree_remove(
    tmp_path: Path, monkeypatch
):
    mod = _module()
    repo = _init_repo(tmp_path)
    orphan_path = tmp_path / "orphaned-worktree"
    orphan_path.mkdir()
    readonly_file = orphan_path / "CODEX.md"
    readonly_file.write_text("generated\n")
    readonly_file.chmod(stat.S_IREAD)
    candidate = mod.PurgeCandidate(
        branch="codex/orphaned-worktree",
        worktree_path=str(orphan_path),
        commit_classes=[],
        dirty_classes=[],
        commit_details=[],
        dirty_paths=[],
    )
    real_git = mod._git
    calls = []

    def fake_git(repo_root, *args, **kwargs):
        if args[:3] == ("worktree", "remove", "--force"):
            raise RuntimeError("fatal: not a working tree")
        if args == ("worktree", "list", "--porcelain"):
            return (
                f"worktree {repo.as_posix()}\n"
                f"HEAD {real_git(repo, 'rev-parse', 'HEAD')}\n"
                "branch refs/heads/main\n"
            )
        if args[:2] == ("branch", "-D"):
            calls.append(args)
            return ""
        return real_git(repo_root, *args, **kwargs)

    monkeypatch.setattr(mod, "_git", fake_git)

    try:
        result = mod.purge_candidate(repo, candidate, dry_run=False)
    finally:
        if readonly_file.exists():
            readonly_file.chmod(stat.S_IREAD | stat.S_IWRITE)

    assert result.status == "purged"
    assert result.worktree_removed is True
    assert result.branch_deleted is True
    assert orphan_path.exists() is False
    assert calls == [("branch", "-D", "codex/orphaned-worktree")]


def test_readonly_retry_handler_ignores_already_missing_paths(tmp_path: Path):
    mod = _module()
    missing_path = tmp_path / "already-gone.txt"
    calls = []

    mod._make_writable_and_retry(lambda path: calls.append(path), str(missing_path), None)

    assert calls == []


def test_windows_filesystem_path_prefixes_long_absolute_paths():
    if os.name != "nt":
        return
    mod = _module()
    long_path = Path("C:/") / ("a" * 260)

    assert mod._filesystem_path(long_path).startswith("\\\\?\\")


def test_orphaned_directory_cleanup_retries_transient_directory_not_empty(
    tmp_path: Path, monkeypatch
):
    mod = _module()
    repo = _init_repo(tmp_path)
    orphan_path = tmp_path / "orphaned-worktree"
    orphan_path.mkdir()
    (orphan_path / "leftover.txt").write_text("leftover\n")
    real_rmtree = mod.shutil.rmtree
    attempts = []

    def flaky_rmtree(path, *, onerror):
        attempts.append(Path(path))
        if len(attempts) == 1:
            raise OSError(145, "The directory is not empty")
        return real_rmtree(path, onerror=onerror)

    monkeypatch.setattr(mod.shutil, "rmtree", flaky_rmtree)

    assert mod._remove_orphaned_worktree_directory(repo, orphan_path) is True
    assert orphan_path.exists() is False
    assert len(attempts) == 2
    assert all(str(item).endswith(str(orphan_path.resolve())) for item in attempts)


def test_readonly_retry_handler_clears_directory_children_before_rmdir(tmp_path: Path):
    mod = _module()
    directory = tmp_path / "late-children"
    directory.mkdir()
    (directory / "remaining.txt").write_text("late\n")

    mod._make_writable_and_retry(os.rmdir, str(directory), None)

    assert directory.exists() is False


def test_purge_candidate_unregisters_worktree_from_registry(tmp_path: Path, monkeypatch):
    """`git worktree remove` leaves the Augur worktree registry untouched, so the
    purge must also drop the registry entry — otherwise a stale row and its
    allocated dashboard/MCP ports leak (the bug a real `/dev-merge purge` hit)."""
    mod = _module()
    repo = _init_repo(tmp_path)
    worktree_path = tmp_path / "augur-wt-registered"

    # The purge shells out to `<repo>/scripts/worktree_registry.py`; symlink the
    # real script so its `__file__`-relative `src.config.paths` import still
    # resolves against the live repo, and redirect the registry file into a
    # throwaway state dir via the AUGUR_STATE override.
    real_registry = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1]) / "scripts" / "worktree_registry.py"
    (repo / "scripts").mkdir()
    try:
        (repo / "scripts" / "worktree_registry.py").symlink_to(real_registry)
    except OSError:
        # Fallback for Windows standard users who cannot create symlinks
        project_root = real_registry.parent.parent.as_posix()
        wrapper_content = f"""import sys
sys.path.insert(0, "{project_root}")
import runpy
runpy.run_path("{real_registry.as_posix()}", run_name="__main__")
"""
        (repo / "scripts" / "worktree_registry.py").write_text(wrapper_content, encoding="utf-8")
    monkeypatch.setenv("AUGUR_STATE", str(tmp_path / "state"))

    _git(repo, "worktree", "add", str(worktree_path), "-b", "codex/leftover-tech")
    (worktree_path / "AGENTS.md").write_text("generated\n")
    _git(worktree_path, "add", "AGENTS.md")
    _git(worktree_path, "commit", "-m", "agent sync")

    def _registry(*args: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(repo / "scripts" / "worktree_registry.py"), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(proc.stdout)

    assert _registry(
        "register", "--path", str(worktree_path), "--name", "leftover-tech"
    )["success"] is True

    candidate = next(
        item
        for item in mod.inventory_leftover_candidates(repo, target_branch="main")
        if item.branch == "codex/leftover-tech"
    )
    result = mod.purge_candidate(repo, candidate, dry_run=False)

    registered_paths = {wt["path"] for wt in _registry("list")["worktrees"]}

    assert result.status == "purged"
    assert result.worktree_removed is True
    assert result.registry_unregistered is True
    assert str(worktree_path.resolve()) not in registered_paths


def test_purge_candidate_skips_worktree_with_active_ai_process(tmp_path: Path, monkeypatch):
    mod = _module()
    repo = _init_repo(tmp_path)
    worktree_path = tmp_path / "augur-wt-active"

    _git(repo, "worktree", "add", str(worktree_path), "-b", "codex/leftover-active")
    (worktree_path / "AGENTS.md").write_text("generated\n")
    _git(worktree_path, "add", "AGENTS.md")
    _git(worktree_path, "commit", "-m", "agent sync")

    monkeypatch.setattr(
        mod,
        "active_ai_processes_for_path",
        lambda _path: [mod.ActiveWorktreeProcess(pid=123, command="codex")],
        raising=False,
    )

    candidate = next(
        item
        for item in mod.inventory_leftover_candidates(repo, target_branch="main")
        if item.branch == "codex/leftover-active"
    )
    result = mod.purge_candidate(repo, candidate, dry_run=False)

    branches = _git(repo, "branch", "--format=%(refname:short)").splitlines()

    assert result.status == "skipped_active_processes"
    assert result.reason == "active_processes"
    assert result.active_processes == [mod.ActiveWorktreeProcess(pid=123, command="codex")]
    assert result.worktree_removed is False
    assert result.branch_deleted is False
    assert worktree_path.exists() is True
    assert "codex/leftover-active" in branches
