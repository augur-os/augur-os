#!/usr/bin/env python3
"""restart-augur — one command to make freshly-merged code go live.

What it does, per target checkout:
1. Sync to origin/main: fetch -> stash dirty work -> rebase onto origin/main ->
   restore the stash. On rebase/stash conflict it aborts and restores, never
   leaving a broken tree (it reports the conflict for manual reconcile instead).
2. Restart the Augur daemon (background routines) so its runtime loads new code.
3. Print the one step it must NOT do for you: restart your AI-client session(s)
   (Claude Code / Codex / Gemini). Their MCP servers re-spawn with the new code
   on restart, and ~/Library/Logs/Augur/mcp_invocations.jsonl begins filling.

It deliberately does NOT kill AI-client MCP servers by default (that disrupts
live tool connections mid-task). Pass --kill-mcp to do it (clients re-spawn them).

Usage:
    python3 restart_augur.py                 # sync the main checkout + restart daemon
    python3 restart_augur.py --checkout PATH
    python3 restart_augur.py --kill-mcp      # also bounce the MCP servers
    python3 restart_augur.py --dry-run
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path


def _run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def default_checkout() -> Path:
    """The main checkout is the first entry of `git worktree list` (no hardcoded paths)."""
    result = _run(["git", "worktree", "list", "--porcelain"])
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line.split(" ", 1)[1])
    return Path.cwd()


def sync_checkout(checkout: Path, *, target: str = "origin/main") -> dict:
    """fetch -> stash (if dirty) -> rebase onto target -> restore stash. Never leaves a broken tree."""
    checkout = Path(checkout)
    if not (checkout / ".git").exists():
        return {"ok": False, "step": "resolve", "error": f"not a git checkout: {checkout}"}
    remote = target.split("/", 1)[0] if "/" in target else "origin"
    _run(["git", "fetch", remote, "-q"], cwd=checkout)
    dirty = bool(_run(["git", "status", "--porcelain"], cwd=checkout).stdout.strip())
    stashed = False
    if dirty:
        stashed = _run(["git", "stash", "push", "-u", "-m", "restart-augur-autostash"], cwd=checkout).returncode == 0
    rebase = _run(["git", "rebase", target], cwd=checkout)
    if rebase.returncode != 0:
        _run(["git", "rebase", "--abort"], cwd=checkout)
        if stashed:
            _run(["git", "stash", "pop"], cwd=checkout)
        return {"ok": False, "step": "rebase",
                "error": (rebase.stderr or rebase.stdout).strip()[:300],
                "hint": "local commits conflict with origin/main — reconcile this checkout manually"}
    if stashed:
        pop = _run(["git", "stash", "pop"], cwd=checkout)
        if pop.returncode != 0:
            return {"ok": False, "step": "stash-pop",
                    "error": (pop.stderr or pop.stdout).strip()[:300],
                    "hint": "rebase succeeded but stashed changes conflict — resolve, then 'git stash drop'"}
    head = _run(["git", "rev-parse", "--short", "HEAD"], cwd=checkout).stdout.strip()
    return {"ok": True, "head": head, "restored_dirty": stashed}


def restart_daemon() -> dict:
    """Restart the Augur daemon via the platform service manager (best-effort)."""
    if sys.platform == "darwin":
        result = _run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/com.augur.daemon"])
        return {"ok": result.returncode == 0, "out": (result.stderr or result.stdout).strip()[:200] or "kickstarted"}
    return {"ok": False, "out": "non-macOS: restart via service_healer.py (install/heal)"}


def kill_mcp_servers() -> dict:
    """Kill augur MCP server processes so their clients re-spawn them with new code."""
    pids = [p for p in _run(["pgrep", "-f", "augur_framework --client-id"]).stdout.split() if p.isdigit()]
    for pid in pids:
        _run(["kill", pid])
    return {"ok": True, "killed": pids}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="restart-augur")
    parser.add_argument("--checkout", default=None, help="checkout to sync (default: main checkout)")
    parser.add_argument("--target", default="origin/main")
    parser.add_argument("--no-daemon", action="store_true", help="skip the daemon restart")
    parser.add_argument("--kill-mcp", action="store_true",
                        help="bounce augur MCP servers so clients re-spawn them (disrupts live tool connections)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    checkout = Path(args.checkout).expanduser() if args.checkout else default_checkout()
    print(f"restart-augur → checkout: {checkout} (target {args.target})")
    if args.dry_run:
        print("  (dry-run) would: sync -> origin/main, restart daemon, print client-restart step")
        return 0

    sync = sync_checkout(checkout, target=args.target)
    print(f"  sync: {sync}")
    if not sync["ok"]:
        print(f"  ⚠ sync failed at {sync['step']}: {sync.get('hint', '')} — fix the checkout, then re-run.")
    if not args.no_daemon:
        print(f"  daemon: {restart_daemon()}")
    if args.kill_mcp:
        print(f"  mcp: {kill_mcp_servers()} (clients re-spawn with new code)")

    print("\nManual step this script will not do for you (it can't restart the client it runs inside):")
    print("  • Restart your AI-client session(s) — Claude Code, and Codex/Gemini if used.")
    print("    Their MCP servers re-spawn with the new code on restart.")
    print("  • Verify: tail ~/Library/Logs/Augur/mcp_invocations.jsonl after a few tool calls.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
