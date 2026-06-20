#!/usr/bin/env python3
"""Repair Codex thread metadata after disposable Augur worktrees are removed."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_STATE_DB = "state_5.sqlite"


@dataclass(frozen=True)
class CodexThreadRepairResult:
    status: str
    updated_threads: int
    state_db: str
    worktree_path: str
    repo_root: str
    target_branch: str
    git_sha: str | None


def _codex_state_db(codex_home: Path | None = None) -> Path:
    home = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return home / DEFAULT_STATE_DB


def _git_sha(repo_root: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _candidate_cwd_values(worktree_path: Path) -> list[str]:
    expanded = Path(worktree_path).expanduser()
    resolved = expanded.resolve(strict=False)
    return sorted({str(expanded), str(resolved)})


def repoint_threads_for_removed_worktree(
    *,
    worktree_path: Path,
    repo_root: Path,
    target_branch: str = "main",
    codex_home: Path | None = None,
    dry_run: bool = False,
) -> CodexThreadRepairResult:
    """Point Codex threads from a removed worktree back to the main repo checkout."""
    state_db = _codex_state_db(codex_home)
    repo_root = Path(repo_root).expanduser().resolve()
    git_sha = _git_sha(repo_root)
    cwd_values = _candidate_cwd_values(Path(worktree_path))
    display_worktree = cwd_values[-1]

    if not state_db.exists():
        return CodexThreadRepairResult(
            status="missing_codex_state",
            updated_threads=0,
            state_db=str(state_db),
            worktree_path=display_worktree,
            repo_root=str(repo_root),
            target_branch=target_branch,
            git_sha=git_sha,
        )

    _ph = "(" + ",".join(["?"] * len(cwd_values)) + ")"
    _count_prefix = "select count(*) from threads where cwd in"
    _update_prefix = (
        "update threads set cwd = ?, git_branch = ?, git_sha = coalesce(?, git_sha)"
        " where cwd in"
    )
    with sqlite3.connect(state_db) as conn:
        if dry_run:
            row = conn.execute(
                _count_prefix + " " + _ph,
                cwd_values,
            ).fetchone()
            updated = int(row[0] if row else 0)
            status = "dry_run"
        else:
            conn.execute(
                _update_prefix + " " + _ph,
                [str(repo_root), target_branch, git_sha, *cwd_values],
            )
            updated = conn.execute("select changes()").fetchone()[0]
            status = "updated"

    return CodexThreadRepairResult(
        status=status,
        updated_threads=int(updated),
        state_db=str(state_db),
        worktree_path=display_worktree,
        repo_root=str(repo_root),
        target_branch=target_branch,
        git_sha=git_sha,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repair Codex thread CWD metadata")
    parser.add_argument("--worktree-path", required=True, help="Removed worktree path")
    parser.add_argument("--repo-root", required=True, help="Checkout to repoint threads to")
    parser.add_argument("--target-branch", default="main", help="Branch name for repaired threads")
    parser.add_argument("--codex-home", help="Codex home directory, defaults to ~/.codex")
    parser.add_argument("--dry-run", action="store_true", help="Report matching threads without updating")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = repoint_threads_for_removed_worktree(
        worktree_path=Path(args.worktree_path),
        repo_root=Path(args.repo_root),
        target_branch=args.target_branch,
        codex_home=Path(args.codex_home) if args.codex_home else None,
        dry_run=args.dry_run,
    )
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
