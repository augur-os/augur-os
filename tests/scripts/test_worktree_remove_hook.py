"""Integration: the WorktreeRemove hook fully reaps a clean, merged worktree.

Regression for the bug where `worktree-unregister` read `CLAUDE_WORKTREE_PATH`
(unset for this event) instead of the stdin `worktree_path`, so it acted on `.`
(the main checkout) and never cleaned the sibling worktree — leaving the dir +
branch + registry entry. The fix routes the WorktreeRemove hook through the
cross-client, no-loss purge (enqueue + sweep → worktree-launch.sh cleanup).

This is the cross-client cleanup path: it must work for a worktree regardless of
which client created it, and never delete a path a live client still owns.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, check=False)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
@pytest.mark.skipif(sys.platform == "win32", reason="Windows holds directory handles, blocking worktree removal; validation pending (ROADMAP)")
def test_worktree_remove_hook_reaps_clean_merged_worktree(tmp_path):
    name = f"wt-removetest-{tmp_path.name[-8:]}"
    wt = ROOT.parent / f"augur-{name}"
    env = {
        **os.environ,
        "CLAUDE_PROJECT_DIR": str(ROOT),
        "AUGUR_STATE": str(tmp_path / "state"),  # isolate the registry/queue
    }
    try:
        # Provision a real worktree (reuse the create script).
        setup = subprocess.run(
            [sys.executable, "scripts/worktree_create.py", "--name", name, "--repo", str(ROOT)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert wt.is_dir(), f"setup failed to create worktree: {setup.stderr}"

        # Fire the WorktreeRemove hook exactly as the harness does: path via stdin.
        stdin = json.dumps({"hook_event_name": "WorktreeRemove", "worktree_path": str(wt)})
        subprocess.run(
            ["node", "scripts/hooks/run-hook.mjs", "worktree-remove"],
            cwd=str(ROOT),
            input=stdin,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        # Clean (artifacts gitignored), merged (no commits ahead), unowned → fully reaped.
        assert not wt.exists(), "WorktreeRemove hook did not remove the worktree directory"
    finally:
        if wt.exists():
            _git("worktree", "remove", "--force", str(wt))
        _git("branch", "-D", name)
        if wt.exists():
            shutil.rmtree(wt, ignore_errors=True)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_worktree_remove_hook_never_touches_main_checkout(tmp_path):
    """The hook must no-op when handed the main checkout path (never self-purge)."""
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT), "AUGUR_STATE": str(tmp_path / "state")}
    stdin = json.dumps({"hook_event_name": "WorktreeRemove", "worktree_path": str(ROOT)})
    subprocess.run(
        ["node", "scripts/hooks/run-hook.mjs", "worktree-remove"],
        cwd=str(ROOT),
        input=stdin,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    # Main checkout is untouched.
    assert (ROOT / ".git").exists()
    assert (ROOT / "scripts" / "worktree_create.py").exists()
