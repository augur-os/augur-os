"""Tests for git_archive — git-aware archive moves for tracked files."""
from __future__ import annotations

# TODO_CLEANUP: This file is 973 lines — consider splitting into smaller modules
import importlib.util
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "git_archive.py"
_SPEC = importlib.util.spec_from_file_location("git_archive_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
sys.modules["git_archive_under_test"] = mod
_SPEC.loader.exec_module(mod)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        shell=False,
        text=True,
        capture_output=True,
        check=False,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        shell=False,
        text=True,
        capture_output=True,
        check=False,
    ).returncode == 0
    assert _git(repo, "config", "user.email", "test@example.com").returncode == 0
    assert _git(repo, "config", "user.name", "Test User").returncode == 0
    return repo


def _commit_file(repo: Path, rel_path: str, content: str = "hello\n") -> Path:
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    assert _git(repo, "add", rel_path).returncode == 0
    assert _git(repo, "commit", "-m", f"add {rel_path}").returncode == 0
    return path


def _init_bare_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    result = subprocess.run(
        ["git", "init", "--bare", str(remote)],
        shell=False,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return remote


def _configure_origin(repo: Path, remote: Path) -> None:
    assert _git(repo, "remote", "add", "origin", str(remote)).returncode == 0
    branch = _git(repo, "branch", "--show-current").stdout.strip()
    assert branch
    assert _git(repo, "push", "-u", "origin", branch).returncode == 0


def test_git_history_purge_commits_pushes_deletes_payload_and_preserves_ledger(tmp_path):
    repo = _init_repo(tmp_path)
    remote = _init_bare_remote(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md", "# Old note\n")
    _configure_origin(repo, remote)

    result = mod.apply_git_history_purge_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        source_kind="vault-notes",
        reason="superseded",
        artifact_group="uart-debug",
        apply_run_id="run-1",
        brain_id="private",
    )

    assert result["status"] == "succeeded"
    assert result["archive_mode"] == "git-history-purge"
    assert result["git_action"] == "mv+purge"
    assert result["archive_pushed"] is True
    assert result["purge_pushed"] is True
    assert result["archive_commit"]
    assert result["purge_commit"]
    assert result["archive_commit"] != result["purge_commit"]

    archived_rel = result["archived_path"]
    assert archived_rel.startswith("archive/sweep/notes/")
    assert not source.exists()
    assert not (repo / archived_rel).exists()
    assert (repo / "archive" / "_ledger" / "sweep.jsonl").is_file()

    events = [
        json.loads(line)
        for line in (repo / "archive" / "_ledger" / "sweep.jsonl").read_text().splitlines()
    ]
    assert [event["event"] for event in events] == ["archive_prepared", "purged"]
    assert events[0]["archive_record_id"] == events[1]["archive_record_id"]
    assert events[0]["original_path"] == "notes/topic/page.md"
    assert events[0]["archived_path"] == archived_rel
    assert events[1]["archive_commit"] == result["archive_commit"]
    assert "purge_commit" not in events[1]
    assert "git restore --source=" + result["archive_commit"] in events[1]["recovery_hint"]

    remote_log = subprocess.run(
        ["git", "--git-dir", str(remote), "log", "--oneline", "--all"],
        shell=False,
        text=True,
        capture_output=True,
        check=False,
    )
    assert remote_log.returncode == 0
    assert "archive sweep payload" in remote_log.stdout
    assert "purge swept archive payload" in remote_log.stdout


def test_git_history_purge_recovery_hint_restores_original_path_in_fresh_clone(tmp_path):
    repo = _init_repo(tmp_path)
    remote = _init_bare_remote(tmp_path)
    source = _commit_file(repo, "notes/firmware/uart-debug.md", "# UART debug\n")
    _configure_origin(repo, remote)

    result = mod.apply_git_history_purge_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        source_kind="vault-notes",
        reason="superseded",
        artifact_group="uart-debug",
        apply_run_id="run-recovery-hint",
        brain_id="private",
    )

    assert result["status"] == "succeeded"

    recovery_repo = tmp_path / "recovery"
    assert subprocess.run(
        ["git", "clone", str(remote), str(recovery_repo)],
        shell=False,
        text=True,
        capture_output=True,
        check=False,
    ).returncode == 0

    commands_text = result["recovery_hint"]
    for prefix in ("Restore with ", "Restore to archive path with "):
        if commands_text.startswith(prefix):
            commands_text = commands_text.removeprefix(prefix)
            break
    commands_text = commands_text.removesuffix(".")
    commands_text = commands_text.replace("; then restore active path with ", "; ")
    commands = [command.strip() for command in commands_text.split(";") if command.strip()]

    for command in commands:
        completed = subprocess.run(
            shlex.split(command),
            cwd=str(recovery_repo),
            shell=False,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, (
            f"recovery command failed: {command}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    assert (recovery_repo / "notes/firmware/uart-debug.md").read_text(encoding="utf-8") == (
        "# UART debug\n"
    )


def test_git_history_purge_keeps_payload_when_archive_push_fails(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md", "# Old note\n")
    push_calls = []

    def fail_archive_push(repo_root: Path, remote: str, branch: str):
        push_calls.append((remote, branch))
        return False, "network down"

    monkeypatch.setattr(mod, "_push_branch", fail_archive_push)

    result = mod.apply_git_history_purge_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        source_kind="vault-notes",
        reason="superseded",
        artifact_group=None,
        apply_run_id="run-archive-push-fail",
        brain_id="private",
    )

    assert result["status"] == "partial"
    assert result["failure_phase"] == "archive_push"
    assert result["archive_pushed"] is False
    assert result["purged"] is False
    assert push_calls
    assert not source.exists()
    assert (repo / result["archived_path"]).exists()

    events = [
        json.loads(line)
        for line in (repo / "archive" / "_ledger" / "sweep.jsonl").read_text().splitlines()
    ]
    assert [event["event"] for event in events] == ["archive_prepared"]


def test_git_history_purge_reports_local_purge_when_purge_push_fails(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md", "# Old note\n")
    call_count = {"push": 0}

    def fail_second_push(repo_root: Path, remote: str, branch: str):
        call_count["push"] += 1
        if call_count["push"] == 1:
            return True, ""
        return False, "remote rejected"

    monkeypatch.setattr(mod, "_push_branch", fail_second_push)

    result = mod.apply_git_history_purge_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        source_kind="vault-notes",
        reason="superseded",
        artifact_group=None,
        apply_run_id="run-purge-push-fail",
        brain_id="private",
    )

    assert result["status"] == "partial"
    assert result["failure_phase"] == "purge_push"
    assert result["archive_pushed"] is True
    assert result["purged"] is True
    assert result["purge_pushed"] is False
    assert not (repo / result["archived_path"]).exists()
    assert (repo / "archive" / "_ledger" / "sweep.jsonl").is_file()


def test_preview_git_history_purge_archive_has_no_side_effects(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "skills/team-skill/SKILL.md", "# Skill\n")
    before = _git(repo, "status", "--porcelain").stdout

    result = mod.preview_git_history_purge_archive(
        repo_root=repo,
        source_path=source,
        source_tab="skills",
        source_kind="brain-skill",
        reason="superseded",
        artifact_group="team-skill",
        apply_run_id="run-preview",
        brain_id="firmware-team",
    )

    assert result["status"] == "would_succeed"
    assert result["archive_mode"] == "git-history-purge"
    assert result["git_action"] == "mv+purge"
    assert result["archived_path"].startswith("archive/sweep/skills/")
    assert not (repo / "archive").exists()
    assert _git(repo, "status", "--porcelain").stdout == before


def test_git_history_purge_refuses_core_augur_product_skill(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "docs" / "adrs").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname = \"augur\"\n", encoding="utf-8")
    assert _git(repo, "add", "pyproject.toml").returncode == 0
    assert _git(repo, "commit", "-m", "add project marker").returncode == 0
    source = _commit_file(repo, "project-brain/capabilities/skills/core-skill/SKILL.md", "# Core\n")

    result = mod.apply_git_history_purge_archive(
        repo_root=repo,
        source_path=source,
        source_tab="skills",
        source_kind="brain-skill",
        reason="superseded",
        artifact_group="core-skill",
        apply_run_id="run-core-refusal",
        brain_id="project",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "core_product_skill"
    assert source.exists()


def test_tracked_file_is_archived_with_git_mv(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    today = datetime.now(timezone.utc).date().isoformat()

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    archived_rel = f"archive/sweep/notes/{today}/notes/topic/page.md"
    assert result["status"] == "succeeded"
    assert result["git_action"] == "mv"
    assert result["from"] == "notes/topic/page.md"
    assert result["to"] == archived_rel
    assert result["original_path"] == str(source.resolve())
    assert result["archived_path"] == archived_rel
    assert result["repo_root"] == str(repo.resolve())
    assert result["reason"] == "stale sweep result"
    assert result["artifact_group"] == "topic"
    assert result["apply_run_id"] == "run-123"
    assert "git mv" in result["recovery_hint"]
    assert "notes/topic/page.md" in result["recovery_hint"]
    assert archived_rel in result["recovery_hint"]
    archived = repo / result["archived_path"]
    assert not source.exists()
    assert archived.read_text(encoding="utf-8") == "hello\n"
    assert _git(repo, "status", "--porcelain").stdout == (
        f"R  notes/topic/page.md -> {archived_rel}\n"
    )


def test_untracked_file_is_refused(tmp_path):
    repo = _init_repo(tmp_path)
    source = repo / "sources/raw.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("draft\n", encoding="utf-8")

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="sources",
        reason="stale sweep result",
        artifact_group=None,
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "untracked"
    assert source.exists()
    assert not (repo / "archive").exists()


def test_dirty_tracked_file_is_refused(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "pages/home.md")
    source.write_text("changed\n", encoding="utf-8")

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="pages",
        reason="stale sweep result",
        artifact_group="site",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "dirty"
    assert source.read_text(encoding="utf-8") == "changed\n"
    assert not (repo / "archive").exists()


def test_missing_absolute_path_outside_repo_is_refused_as_outside_repo(tmp_path):
    repo = _init_repo(tmp_path)
    source = tmp_path / "outside" / "missing.md"

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "outside_repo"
    assert not (repo / "archive").exists()


def test_existing_directory_outside_repo_is_refused_as_outside_repo(tmp_path):
    repo = _init_repo(tmp_path)
    source = tmp_path / "outside"
    source.mkdir()

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "outside_repo"
    assert source.exists()
    assert not (repo / "archive").exists()


def test_missing_path_inside_repo_is_refused_as_source_missing(tmp_path):
    repo = _init_repo(tmp_path)
    source = repo / "notes" / "missing.md"

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "source_missing"
    assert not (repo / "archive").exists()


def test_existing_directory_inside_repo_is_refused_as_source_missing(tmp_path):
    repo = _init_repo(tmp_path)
    source = repo / "notes" / "topic"
    source.mkdir(parents=True)

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "source_missing"
    assert source.exists()
    assert not (repo / "archive").exists()


def test_outside_final_symlink_source_is_refused_as_outside_repo(tmp_path):
    repo = _init_repo(tmp_path)
    target = _commit_file(repo, "notes/topic/page.md")
    outside = tmp_path / "outside"
    outside.mkdir()
    symlink_source = outside / "linked.md"
    symlink_source.symlink_to(target)

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=symlink_source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "outside_repo"
    assert target.exists()
    assert symlink_source.exists()
    assert not (repo / "archive").exists()


def test_outside_path_through_symlinked_parent_is_refused_as_outside_repo(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/real/page.md")
    outside = tmp_path / "outside"
    outside.mkdir()
    symlink_parent = outside / "linked"
    symlink_parent.symlink_to(repo / "notes" / "real", target_is_directory=True)
    linked_source = symlink_parent / "page.md"

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=linked_source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "outside_repo"
    assert source.exists()
    assert linked_source.exists()
    assert not (repo / "archive").exists()


def test_inside_source_path_through_symlinked_parent_is_refused_as_symlink(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/real/page.md")
    symlink_parent = repo / "notes" / "linked"
    symlink_parent.symlink_to(repo / "notes" / "real", target_is_directory=True)
    linked_source = symlink_parent / "page.md"

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=linked_source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "symlink"
    assert source.exists()
    assert linked_source.exists()
    assert not (repo / "archive").exists()


def test_archive_parent_symlink_is_refused_and_source_remains(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    today = datetime.now(timezone.utc).date().isoformat()
    symlink_target = repo / "outside-archive-target"
    symlink_target.mkdir()
    archive_day = repo / "archive" / "sweep" / "notes" / today
    archive_day.mkdir(parents=True)
    (archive_day / "notes").symlink_to(symlink_target, target_is_directory=True)

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "archive_parent_symlink"
    assert source.exists()
    assert not (symlink_target / "topic").exists()
    assert _git(repo, "status", "--porcelain", "--", "notes/topic/page.md").stdout == ""


def test_archive_parent_regular_file_collision_is_refused_and_source_remains(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    today = datetime.now(timezone.utc).date().isoformat()
    archive_day = repo / "archive" / "sweep" / "notes" / today
    archive_day.mkdir(parents=True)
    (archive_day / "notes").write_text("not a directory\n", encoding="utf-8")

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "archive_parent_not_directory"
    assert source.exists()
    assert _git(repo, "status", "--porcelain", "--", "notes/topic/page.md").stdout == ""


def test_non_git_repo_root_is_refused(tmp_path):
    repo = tmp_path / "not-git"
    source = repo / "notes" / "topic.md"
    source.parent.mkdir(parents=True)
    source.write_text("hello\n", encoding="utf-8")

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "not_git_repository"
    assert source.exists()


def test_nested_git_repo_root_is_refused_as_mismatch(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")

    result = mod.apply_git_archive(
        repo_root=repo / "notes",
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "repo_root_mismatch"
    assert source.exists()


def test_staged_only_change_is_refused_as_dirty(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "pages/home.md")
    source.write_text("staged\n", encoding="utf-8")
    assert _git(repo, "add", "pages/home.md").returncode == 0

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="pages",
        reason="stale sweep result",
        artifact_group="site",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "dirty"
    assert source.read_text(encoding="utf-8") == "staged\n"
    assert not (repo / "archive").exists()


def test_invalid_source_tab_is_refused(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="invalid",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "invalid_source_tab"
    assert source.exists()
    assert not (repo / "archive").exists()


def test_inside_final_symlink_source_is_refused_as_symlink(tmp_path):
    repo = _init_repo(tmp_path)
    target = _commit_file(repo, "notes/topic/page.md")
    symlink_source = repo / "notes" / "topic" / "linked.md"
    symlink_source.symlink_to(target)

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=symlink_source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "symlink"
    assert target.exists()
    assert symlink_source.exists()
    assert not (repo / "archive").exists()


def test_existing_archive_destination_is_refused(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    today = datetime.now(timezone.utc).date().isoformat()
    archived = repo / "archive" / "sweep" / "notes" / today / "notes" / "topic" / "page.md"
    archived.parent.mkdir(parents=True)
    archived.write_text("already archived\n", encoding="utf-8")

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "archive_destination_exists"
    assert source.exists()
    assert archived.read_text(encoding="utf-8") == "already archived\n"


def test_preview_refuses_existing_archive_destination_without_side_effects(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    today = datetime.now(timezone.utc).date().isoformat()
    archived = repo / "archive" / "sweep" / "notes" / today / "notes" / "topic" / "page.md"
    archived.parent.mkdir(parents=True)
    archived.write_text("already archived\n", encoding="utf-8")

    result = mod.preview_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "would_refuse"
    assert result["refusal_category"] == "archive_destination_exists"
    assert source.exists()
    assert archived.read_text(encoding="utf-8") == "already archived\n"
    assert _git(repo, "status", "--porcelain", "--", "notes/topic/page.md").stdout == ""


def test_preview_refuses_archive_parent_symlink_without_side_effects(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    today = datetime.now(timezone.utc).date().isoformat()
    symlink_target = repo / "outside-archive-target"
    symlink_target.mkdir()
    archive_day = repo / "archive" / "sweep" / "notes" / today
    archive_day.mkdir(parents=True)
    (archive_day / "notes").symlink_to(symlink_target, target_is_directory=True)

    result = mod.preview_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "would_refuse"
    assert result["refusal_category"] == "archive_parent_symlink"
    assert source.exists()
    assert not (symlink_target / "topic").exists()
    assert _git(repo, "status", "--porcelain", "--", "notes/topic/page.md").stdout == ""


def test_preview_refuses_archive_parent_file_collision_without_side_effects(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    today = datetime.now(timezone.utc).date().isoformat()
    archive_day = repo / "archive" / "sweep" / "notes" / today
    archive_day.mkdir(parents=True)
    (archive_day / "notes").write_text("not a directory\n", encoding="utf-8")

    result = mod.preview_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "would_refuse"
    assert result["refusal_category"] == "archive_parent_not_directory"
    assert source.exists()
    assert _git(repo, "status", "--porcelain", "--", "notes/topic/page.md").stdout == ""


def test_symlinked_repo_root_with_source_under_same_symlink_archives(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    repo_link = tmp_path / "repo-link"
    repo_link.symlink_to(repo, target_is_directory=True)
    linked_source = repo_link / "notes" / "topic" / "page.md"
    today = datetime.now(timezone.utc).date().isoformat()

    result = mod.apply_git_archive(
        repo_root=repo_link,
        source_path=linked_source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    archived_rel = f"archive/sweep/notes/{today}/notes/topic/page.md"
    assert result["status"] == "succeeded"
    assert result["git_action"] == "mv"
    assert result["from"] == "notes/topic/page.md"
    assert result["to"] == archived_rel
    assert result["archived_path"] == archived_rel
    assert result["repo_root"] == str(repo.resolve())
    assert not source.exists()
    assert not linked_source.exists()
    assert (repo / archived_rel).read_text(encoding="utf-8") == "hello\n"
    assert _git(repo, "status", "--porcelain").stdout == (
        f"R  notes/topic/page.md -> {archived_rel}\n"
    )


def test_symlinked_repo_root_with_canonical_source_archives(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    repo_link = tmp_path / "repo-link"
    repo_link.symlink_to(repo, target_is_directory=True)
    today = datetime.now(timezone.utc).date().isoformat()

    result = mod.apply_git_archive(
        repo_root=repo_link,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    archived_rel = f"archive/sweep/notes/{today}/notes/topic/page.md"
    assert result["status"] == "succeeded"
    assert result["git_action"] == "mv"
    assert result["from"] == "notes/topic/page.md"
    assert result["to"] == archived_rel
    assert result["archived_path"] == archived_rel
    assert result["repo_root"] == str(repo.resolve())
    assert not source.exists()
    assert (repo / archived_rel).read_text(encoding="utf-8") == "hello\n"
    assert _git(repo, "status", "--porcelain").stdout == (
        f"R  notes/topic/page.md -> {archived_rel}\n"
    )


def test_symlinked_repo_root_refuses_canonical_source_outside_repo(tmp_path):
    repo = _init_repo(tmp_path)
    repo_link = tmp_path / "repo-link"
    repo_link.symlink_to(repo, target_is_directory=True)
    outside = tmp_path / "outside" / "page.md"
    outside.parent.mkdir()
    outside.write_text("outside\n", encoding="utf-8")

    result = mod.apply_git_archive(
        repo_root=repo_link,
        source_path=outside,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "outside_repo"
    assert outside.exists()
    assert not (repo / "archive").exists()


def test_symlinked_repo_root_still_refuses_in_repo_symlinked_parent(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/real/page.md")
    symlink_parent = repo / "notes" / "linked"
    symlink_parent.symlink_to(repo / "notes" / "real", target_is_directory=True)
    repo_link = tmp_path / "repo-link"
    repo_link.symlink_to(repo, target_is_directory=True)
    linked_source = repo_link / "notes" / "linked" / "page.md"

    result = mod.apply_git_archive(
        repo_root=repo_link,
        source_path=linked_source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "symlink"
    assert source.exists()
    assert linked_source.exists()
    assert not (repo / "archive").exists()


def test_dangling_archive_destination_symlink_is_refused_and_source_remains(tmp_path):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    today = datetime.now(timezone.utc).date().isoformat()
    archived = repo / "archive" / "sweep" / "notes" / today / "notes" / "topic" / "page.md"
    archived.parent.mkdir(parents=True)
    archived.symlink_to(repo / "missing-archive-target.md")

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "archive_destination_exists"
    assert source.exists()
    assert archived.is_symlink()
    assert not archived.exists()
    assert _git(repo, "status", "--porcelain", "--", "notes/topic/page.md").stdout == ""


def test_git_status_failure_is_refused_with_error(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    original_git = mod._git

    def fake_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if args[:3] == ("status", "--porcelain", "--"):
            return subprocess.CompletedProcess(
                ["git", "-C", str(repo_root), *args],
                128,
                "",
                "forced status failure",
            )
        return original_git(repo_root, *args)

    monkeypatch.setattr(mod, "_git", fake_git)

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "git_status_failed"
    assert result["error"] == "forced status failure"
    assert source.exists()
    assert not (repo / "archive").exists()


def test_git_mv_failed_removes_empty_archive_directories_created_by_call(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    original_git = mod._git

    def fake_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if args and args[0] == "mv":
            return subprocess.CompletedProcess(
                ["git", "-C", str(repo_root), *args],
                1,
                "",
                "forced mv failure",
            )
        return original_git(repo_root, *args)

    monkeypatch.setattr(mod, "_git", fake_git)

    result = mod.apply_git_archive(
        repo_root=repo,
        source_path=source,
        source_tab="notes",
        reason="stale sweep result",
        artifact_group="topic",
        apply_run_id="run-123",
    )

    assert result["status"] == "refused"
    assert result["refusal_category"] == "git_mv_failed"
    assert source.exists()
    assert not (repo / "archive").exists()
    assert _git(repo, "status", "--porcelain", "--", "notes/topic/page.md").stdout == ""
