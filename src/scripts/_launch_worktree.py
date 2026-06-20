"""
scripts._launch_worktree — Worktree helpers for the agent launcher.

Depends on _launch_git (run_git) and _launch_session (exec_client).

Split from src/scripts/agent_launch.py (WS5, behavior-preserving).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.scripts._launch_git import run_git


def helper_env(repo: Path) -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = [str(repo), str(repo / "project-brain" / "capabilities")]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    return env


def run_python_helper(
    repo: Path,
    rel_script: str,
    *args: str,
    required: bool = False,
) -> str | None:
    script = repo / rel_script
    if not script.exists():
        if required:
            raise RuntimeError(f"required helper not found: {rel_script}")
        return None

    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=helper_env(repo),
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"{rel_script} failed"
        if required:
            raise RuntimeError(message)
        print(f"Warning: {message}", file=sys.stderr)
        return None
    return result.stdout


def register_worktree(repo: Path, wt_dir: Path, name: str) -> tuple[str | None, str | None]:
    raw = run_python_helper(
        repo,
        "scripts/worktree_registry.py",
        "register",
        "--path",
        str(wt_dir),
        "--name",
        name,
    )
    if raw is None:
        return None, None

    data = json.loads(raw)
    if not data.get("success", False):
        raise RuntimeError(str(data.get("error") or "worktree registration failed"))

    worktree = data.get("worktree") if isinstance(data.get("worktree"), dict) else {}
    dashboard_port = data.get("dashboard_port") or worktree.get("dashboard_port")
    mcp_port = data.get("mcp_port") or worktree.get("mcp_port")

    if dashboard_port:
        (wt_dir / ".env.local").write_text(f"PORT={dashboard_port}\n", encoding="utf-8")
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (wt_dir / ".augur-worktree.yaml").write_text(
            "\n".join(
                [
                    "worktree: true",
                    f"dashboard_port: {dashboard_port}",
                    f"mcp_port: {mcp_port or ''}",
                    f"main_repo: {repo}",
                    f"name: {name}",
                    f"created_at: {created_at}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    return (str(dashboard_port) if dashboard_port else None, str(mcp_port) if mcp_port else None)


def bootstrap_worktree(repo: Path, wt_dir: Path) -> None:
    run_python_helper(
        repo,
        "scripts/worktree_preflight.py",
        "--root",
        str(wt_dir),
        "--profile",
        "worktree",
        "--repair",
        required=True,
    )


def generate_mcp_config(repo: Path, wt_dir: Path, name: str) -> None:
    run_python_helper(
        repo,
        "scripts/generate-worktree-mcp.py",
        "--path",
        str(wt_dir),
        "--name",
        name,
        "--all",
    )


def derive_worktree_name() -> str:
    return datetime.now().strftime("wt-%Y%m%d-%H%M%S")


def resolve_base_ref(repo: Path) -> str:
    run_git(repo, "fetch", "origin", "main")
    if run_git(repo, "rev-parse", "--verify", "--quiet", "origin/main", check=False).returncode == 0:
        return "origin/main"
    return "main"


# create_worktree lives in agent_launch.py (must call resolve_base_ref/run_git/etc. via agent_launch globals for test monkeypatching)
