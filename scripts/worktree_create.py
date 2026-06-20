"""Create + provision an Augur worktree and print ONLY its path.

This backs the harness `WorktreeCreate` hook (EnterWorktree). The hook contract is:
the hook creates the worktree and echoes its path to stdout. We create a sibling
`augur-<name>` worktree, allocate its dashboard/MCP ports, and write
`.augur-worktree.yaml` so `aug dev build` resolves the worktree's own port. The
slower per-worktree MCP generation + full preflight are repaired on the first
`aug dev build` / start-dev (worktree_preflight --repair), keeping this within the
hook timeout.

Stdout is exactly the worktree path (one line). All diagnostics go to stderr.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scripts.agent_launch import register_worktree, resolve_base_ref, run_git


def create_and_provision(repo: Path, name: str) -> Path:
    wt_dir = repo.parent / f"augur-{name}"
    if not wt_dir.exists():
        base_ref = resolve_base_ref(repo)
        run_git(repo, "worktree", "add", str(wt_dir), "-b", name, base_ref)
    # Allocates dashboard/mcp ports + writes .augur-worktree.yaml (captures its own stdout).
    register_worktree(repo, wt_dir, name)
    return wt_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Create + provision an Augur worktree; print its path.")
    parser.add_argument("--name", required=True, help="Worktree name (becomes augur-<name> + branch).")
    parser.add_argument("--repo", default=None, help="Main repo root (default: cwd).")
    args = parser.parse_args()

    repo = Path(args.repo).resolve() if args.repo else Path.cwd()
    wt_dir = create_and_provision(repo, args.name)
    # ONLY the worktree path on stdout — the WorktreeCreate hook contract.
    print(str(wt_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
