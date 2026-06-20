#!/usr/bin/env python3
"""Helpers for safe `/dev-merge --purge` leftover cleanup."""

from __future__ import annotations

import argparse
import errno
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from codex_thread_state import repoint_threads_for_removed_worktree

# The live AI/client process ownership guard is shared across every
# worktree-removal path — it lives in worktree_guard.py, not here.
from worktree_guard import ActiveWorktreeProcess, active_ai_processes_for_path


TECHNICAL_LEFTOVER_PATHS = {
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
    Path("CODEX.md"),
    Path(".claude/settings.json"),
    Path(".gemini/GEMINI.md"),
    Path(".opencode/AGENTS.md"),
    Path("project-brain/BRAIN.yaml"),
}
TECHNICAL_LEFTOVER_PREFIXES = (
    Path(".venv"),
    Path(".gemini/skills"),
    Path(".opencode/skills"),
    Path("project-brain/config/inventory"),
)
MEANINGFUL_REPO_ROOTS = {"apps", "config", "docs", "plugins", "scripts", "skills", "src", "staging", "tests"}


@dataclass(frozen=True)
class BranchCommit:
    sha: str
    subject: str
    classification: str
    paths: list[str]


@dataclass(frozen=True)
class PurgeCandidate:
    branch: str
    worktree_path: str | None
    commit_classes: list[str]
    dirty_classes: list[str]
    commit_details: list[BranchCommit]
    dirty_paths: list[str]


@dataclass(frozen=True)
class PurgeResult:
    branch: str
    status: str
    reason: str | None
    worktree_removed: bool
    branch_deleted: bool
    codex_threads_repointed: int
    active_processes: list[ActiveWorktreeProcess] = field(default_factory=list)
    registry_unregistered: bool = False


def _git(repo_root: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=check,
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "git command failed")
    return proc.stdout.strip()


def _normalize_path(path: Path) -> str:
    resolved = str(Path(path).resolve())
    return resolved.casefold() if os.name == "nt" else resolved


def _filesystem_path(path: Path | str) -> str:
    resolved = str(Path(path).resolve())
    if os.name != "nt" or resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved.removeprefix("\\\\")
    return "\\\\?\\" + resolved


def _path_exists(path: Path | str) -> bool:
    return os.path.exists(_filesystem_path(path))


def _path_is_dir(path: Path | str) -> bool:
    return os.path.isdir(_filesystem_path(path))


def _make_writable_and_retry(func, path: str, _exc_info) -> None:
    fs_path = _filesystem_path(path)
    try:
        current_mode = os.stat(fs_path).st_mode
    except FileNotFoundError:
        return
    os.chmod(fs_path, current_mode | stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
    try:
        func(fs_path)
    except OSError as exc:
        if func is os.rmdir and _is_directory_not_empty_error(exc):
            _remove_directory_contents(Path(fs_path))
            func(fs_path)
            return
        raise


def _remove_file_if_present(path: Path) -> None:
    fs_path = _filesystem_path(path)
    try:
        current_mode = os.stat(fs_path).st_mode
        os.chmod(fs_path, current_mode | stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
        os.unlink(fs_path)
    except FileNotFoundError:
        return


def _remove_directory_contents(path: Path) -> None:
    try:
        entries = list(os.scandir(_filesystem_path(path)))
    except FileNotFoundError:
        return
    for entry in entries:
        child = Path(entry.path)
        if entry.is_dir(follow_symlinks=False):
            _remove_tree_with_retries(child)
        else:
            _remove_file_if_present(child)


def _is_directory_not_empty_error(exc: OSError) -> bool:
    return getattr(exc, "winerror", None) == 145 or getattr(exc, "errno", None) in {
        errno.ENOTEMPTY,
        145,
    }


def _remove_tree_with_retries(path: Path, *, attempts: int = 3) -> None:
    last_error: OSError | None = None
    for attempt in range(attempts):
        try:
            shutil.rmtree(_filesystem_path(path), onerror=_make_writable_and_retry)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            if not _is_directory_not_empty_error(exc):
                raise
            last_error = exc
            if not _path_exists(path):
                return
            if attempt < attempts - 1:
                time.sleep(0.2 * (attempt + 1))
                continue
    if _path_exists(path) and last_error is not None:
        raise last_error


def _remove_orphaned_worktree_directory(repo_root: Path, worktree_path: Path) -> bool:
    """Remove a directory left after Git has already unregistered a worktree."""
    repo_root = Path(repo_root).resolve()
    worktree_path = Path(worktree_path).resolve()
    if not _path_exists(worktree_path):
        return True
    if worktree_path == repo_root or not _path_is_dir(worktree_path):
        return False
    if _path_exists(worktree_path / ".git"):
        return False

    registered_paths = {
        _normalize_path(Path(path))
        for path in _parse_worktrees(repo_root).values()
    }
    if _normalize_path(worktree_path) in registered_paths:
        return False

    _remove_tree_with_retries(worktree_path)
    return not _path_exists(worktree_path)


def _unregister_worktree(repo_root: Path, worktree_path: Path) -> bool:
    """Drop a removed worktree from the Augur worktree registry.

    `git worktree remove` only clears git's own worktree metadata. The Augur
    worktree registry (`get_runtime_dir()/worktree_registry.yaml`) keeps a
    separate entry plus the dashboard/MCP ports allocated to that worktree, so a
    purge that skips this step leaves a stale registry row and leaks its ports.
    Best-effort: a missing registry script or an entry that was never registered
    both count as success, because the desired end state — no registry row for
    this path — already holds.
    """
    registry_script = repo_root / "scripts" / "worktree_registry.py"
    if not registry_script.exists():
        return False
    proc = subprocess.run(
        [sys.executable, str(registry_script), "unregister", "--path", str(worktree_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return True
    # `unregister` exits non-zero when the path was never registered; that still
    # leaves the registry without an entry for this path, which is the goal.
    return "not registered" in (proc.stdout + proc.stderr).lower()


def classify_dirty_path(path: Path) -> str:
    """Classify one dirty path for purge safety."""
    normalized = Path(path)
    if normalized in TECHNICAL_LEFTOVER_PATHS:
        return "technical_leftover"
    if any(prefix == normalized or prefix in normalized.parents for prefix in TECHNICAL_LEFTOVER_PREFIXES):
        return "technical_leftover"
    if normalized.parts and normalized.parts[0] in MEANINGFUL_REPO_ROOTS:
        return "meaningful_repo_change"
    return "ambiguous"


def decide_purgeability(*, commit_classes: list[str], dirty_classes: list[str]) -> tuple[str, str | None]:
    """Return the purge decision and blocking reason when present."""
    if any(item == "clean_salvage" for item in commit_classes):
        return ("skipped_merge_worthy_commits", "clean_salvage")
    if any(item == "meaningful_repo_change" for item in dirty_classes):
        return ("skipped_meaningful_changes", "meaningful_repo_change")
    if any(item == "ambiguous" for item in dirty_classes):
        return ("skipped_ambiguous_leftovers", "ambiguous")
    return ("purged", None)


def _list_local_branches(repo_root: Path, *, target_branch: str) -> list[str]:
    branches = _git(repo_root, "branch", "--format=%(refname:short)").splitlines()
    return [branch.strip() for branch in branches if branch.strip() and branch.strip() != target_branch]


def _parse_worktrees(repo_root: Path) -> dict[str, str]:
    """Return branch -> worktree path for attached branches."""
    output = _git(repo_root, "worktree", "list", "--porcelain")
    mapping: dict[str, str] = {}
    current_path: str | None = None
    for line in output.splitlines():
        if line.startswith("worktree "):
            current_path = line.removeprefix("worktree ").strip()
            continue
        if line.startswith("branch ") and current_path:
            branch_ref = line.removeprefix("branch ").strip()
            branch = branch_ref.removeprefix("refs/heads/")
            mapping[branch] = current_path
    return mapping


def _classify_paths(paths: list[str]) -> list[str]:
    return [classify_dirty_path(Path(path)) for path in paths]


def _paths_for_commit(repo_root: Path, sha: str) -> list[str]:
    output = _git(repo_root, "show", "--pretty=", "--name-only", "--no-renames", sha)
    return [line.strip() for line in output.splitlines() if line.strip()]


def _classify_unique_commit(repo_root: Path, sha: str) -> tuple[str, list[str]]:
    paths = _paths_for_commit(repo_root, sha)
    path_classes = _classify_paths(paths)
    if path_classes and all(item == "technical_leftover" for item in path_classes):
        return ("stale_or_conflicting", paths)
    return ("clean_salvage", paths)


def _commit_details(repo_root: Path, *, branch: str, target_branch: str) -> list[BranchCommit]:
    output = _git(repo_root, "cherry", "-v", target_branch, branch, check=False)
    if not output:
        return []

    details: list[BranchCommit] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        prefix, sha, subject = line.split(" ", 2)
        if prefix == "-":
            details.append(
                BranchCommit(
                    sha=sha,
                    subject=subject,
                    classification="already_in_main",
                    paths=[],
                )
            )
            continue
        classification, paths = _classify_unique_commit(repo_root, sha)
        details.append(
            BranchCommit(
                sha=sha,
                subject=subject,
                classification=classification,
                paths=paths,
            )
        )
    return details


def _dirty_paths(worktree_path: Path) -> list[str]:
    output = _git(worktree_path, "status", "--porcelain", "-uall")
    if not output:
        return []

    paths: list[str] = []
    for line in output.splitlines():
        if len(line) < 3:
            continue
        entry = line[2:].strip()
        if not entry:
            continue
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        paths.append(entry)
    return paths


def inventory_leftover_candidates(repo_root: Path, *, target_branch: str = "main") -> list[PurgeCandidate]:
    """Inspect non-target local branches and attached worktrees for purge candidates."""
    repo_root = Path(repo_root).resolve()
    worktrees = _parse_worktrees(repo_root)
    candidates: list[PurgeCandidate] = []

    for branch in _list_local_branches(repo_root, target_branch=target_branch):
        worktree_path = worktrees.get(branch)
        commit_details = _commit_details(repo_root, branch=branch, target_branch=target_branch)
        dirty_paths = _dirty_paths(Path(worktree_path)) if worktree_path else []
        candidates.append(
            PurgeCandidate(
                branch=branch,
                worktree_path=worktree_path,
                commit_classes=[item.classification for item in commit_details],
                dirty_classes=_classify_paths(dirty_paths),
                commit_details=commit_details,
                dirty_paths=dirty_paths,
            )
        )

    return candidates


def purge_candidate(
    repo_root: Path,
    candidate: PurgeCandidate,
    *,
    dry_run: bool = True,
    target_branch: str = "main",
    codex_home: Path | None = None,
) -> PurgeResult:
    """Delete one purgeable leftover branch/worktree."""
    repo_root = Path(repo_root).resolve()
    status, reason = decide_purgeability(
        commit_classes=candidate.commit_classes,
        dirty_classes=candidate.dirty_classes,
    )
    if status != "purged":
        return PurgeResult(
            branch=candidate.branch,
            status=status,
            reason=reason,
            worktree_removed=False,
            branch_deleted=False,
            codex_threads_repointed=0,
        )

    worktree_removed = False
    branch_deleted = False
    codex_threads_repointed = 0
    registry_unregistered = False
    if not dry_run:
        if candidate.worktree_path:
            worktree_path = Path(candidate.worktree_path).resolve()
            if worktree_path != repo_root and worktree_path.exists():
                active_processes = active_ai_processes_for_path(worktree_path)
                if active_processes:
                    return PurgeResult(
                        branch=candidate.branch,
                        status="skipped_active_processes",
                        reason="active_processes",
                        worktree_removed=False,
                        branch_deleted=False,
                        codex_threads_repointed=0,
                        active_processes=active_processes,
                    )
                repair_result = repoint_threads_for_removed_worktree(
                    worktree_path=worktree_path,
                    repo_root=repo_root,
                    target_branch=target_branch,
                    codex_home=codex_home,
                )
                codex_threads_repointed = repair_result.updated_threads
                try:
                    _git(repo_root, "worktree", "remove", "--force", str(worktree_path))
                except (RuntimeError, subprocess.CalledProcessError):
                    if not _remove_orphaned_worktree_directory(repo_root, worktree_path):
                        raise
                worktree_removed = True
                registry_unregistered = _unregister_worktree(repo_root, worktree_path)
        _git(repo_root, "branch", "-D", candidate.branch)
        branch_deleted = True

    return PurgeResult(
        branch=candidate.branch,
        status=status,
        reason=reason,
        worktree_removed=worktree_removed,
        branch_deleted=branch_deleted,
        codex_threads_repointed=codex_threads_repointed,
        registry_unregistered=registry_unregistered,
    )


def _cmd_status(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    candidates = inventory_leftover_candidates(repo_root, target_branch=args.target_branch)
    payload = []
    for candidate in candidates:
        decision, reason = decide_purgeability(
            commit_classes=candidate.commit_classes,
            dirty_classes=candidate.dirty_classes,
        )
        item = asdict(candidate)
        item["decision"] = decision
        item["reason"] = reason
        payload.append(item)
    print(json.dumps({"candidates": payload}, indent=2))
    return 0


def _cmd_purge(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    candidates = inventory_leftover_candidates(repo_root, target_branch=args.target_branch)
    if args.branch:
        candidates = [item for item in candidates if item.branch == args.branch]

    results = [
        purge_candidate(
            repo_root,
            candidate,
            dry_run=args.dry_run,
            target_branch=args.target_branch,
        )
        for candidate in candidates
    ]
    print(json.dumps({"results": [asdict(result) for result in results]}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe purge helper for /dev-merge leftovers")
    parser.add_argument("--repo-root", default=".", help="Repo root to inspect")
    parser.add_argument("--target-branch", default="main", help="Target branch to compare against")

    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Report leftover purgeability")
    status_parser.set_defaults(func=_cmd_status)

    purge_parser = subparsers.add_parser("purge", help="Purge eligible leftover branches/worktrees")
    purge_parser.add_argument("--branch", help="Optional single branch to purge")
    purge_parser.add_argument("--dry-run", action="store_true", help="Report only; do not delete")
    purge_parser.set_defaults(func=_cmd_purge)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
