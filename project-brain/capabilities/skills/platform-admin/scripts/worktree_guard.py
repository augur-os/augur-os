#!/usr/bin/env python3
"""Guards for Augur main-checkout, worktree branch, and worktree-removal safety.

Two guard families live here:
  - main-checkout / branch guards (`check_main_checkout_branch`, `is_main_checkout`)
  - the live AI/client process ownership guard (`active_ai_processes_for_path`),
    the single shared check every worktree-removal path must run before deleting
    a worktree.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class MainCheckoutGuardResult:
    ok: bool
    repo_root: str
    main_checkout: str
    branch: str
    is_main_checkout: bool
    message: str


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _git_optional(repo: Path, *args: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _main_checkout(repo_root: Path) -> Path:
    output = _git(repo_root, "worktree", "list", "--porcelain")
    for line in output.splitlines():
        if line.startswith("worktree "):
            return Path(line.removeprefix("worktree ").strip()).resolve()
    return repo_root.resolve()


def is_main_checkout(path: Path) -> bool:
    """Return True if `path` is the git main checkout (not a linked worktree).

    Returns False when `path` is inside a linked worktree, when `path` is not
    a git repository, or when the git invocation fails for any reason. Callers
    that need the failure detail should use `check_main_checkout_branch` instead.
    """
    try:
        resolved = path.resolve()
        return resolved == _main_checkout(resolved)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False


def is_inside_worktree(path: Path) -> bool:
    """Return True ONLY when `path` is confirmed to be inside a linked worktree.

    Returns False when `path` is the main checkout, when `path` is not a git
    repository, or when git status cannot be determined. Use this when the
    caller wants to skip work in linked worktrees but must fail-open (treat
    unknowns as 'safe to run').
    """
    try:
        resolved = path.resolve()
        main = _main_checkout(resolved)
        return resolved != main
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False


def _branch(repo_root: Path) -> str:
    # `git rev-parse --abbrev-ref HEAD` exits non-zero in a freshly
    # initialized repository with no commits. `symbolic-ref` still reports the
    # configured unborn branch, which is the value the guard needs.
    branch = _git_optional(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch:
        return branch
    branch = _git_optional(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    return branch or "HEAD"


def _is_ci_environment() -> bool:
    """True on an ephemeral CI runner (GitHub Actions et al.).

    CI checkouts are single-purpose and short-lived — a PR build routinely sits
    on a ``release/*`` or detached branch — with no shared developer dashboard or
    live AI session to strand. The main-checkout-branch protection exists to keep
    a developer from breaking their shared :3000 by switching the main checkout
    onto a feature branch, which never applies in CI.
    """
    return os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"


def check_main_checkout_branch(repo_root: Path, allowed_branch: str = "main") -> MainCheckoutGuardResult:
    root = repo_root.resolve()
    main_checkout = _main_checkout(root)
    branch = _branch(root)
    is_main_checkout = root == main_checkout
    in_ci = _is_ci_environment()
    ok = in_ci or (not is_main_checkout) or branch == allowed_branch
    if ok:
        if in_ci and is_main_checkout and branch != allowed_branch:
            message = f"branch guard bypassed in CI: root={root} branch={branch} (ephemeral runner)"
        else:
            message = f"branch guard passed: root={root} branch={branch} main_checkout={main_checkout}"
    else:
        message = (
            f"main checkout is on {branch}; continue branch work in a worktree or "
            f"merge it into {allowed_branch}"
        )
    return MainCheckoutGuardResult(
        ok=ok,
        repo_root=str(root),
        main_checkout=str(main_checkout),
        branch=branch,
        is_main_checkout=is_main_checkout,
        message=message,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Live AI/client process ownership guard
#
# The single shared check every worktree-removal path must run before deleting
# a worktree: `/dev-merge`'s successful-merge cleanup, `/dev-merge --purge`, and
# headless_runner all call `active_ai_processes_for_path`. A worktree must never
# be removed while a live `codex` / `claude` / `gemini` / Cowork process still
# owns its path — doing so orphans that session (crashes its cwd mid-command,
# breaks ${CLAUDE_PROJECT_DIR} hooks, leaves a stale worktree-registry entry).
# See ADR-195 and the /dev-merge contract.
# ──────────────────────────────────────────────────────────────────────────────

AI_CLIENT_PROCESS_MARKERS = ("codex", "claude", "gemini", "cowork")

# Env vars whose value, when equal to the worktree path, binds an AI/client
# session to that worktree even if its process cwd has relocated. Hooks the
# session has configured expand `${CLAUDE_PROJECT_DIR}` etc. at fire time, so
# removing the worktree breaks them — the same orphan symptom lsof-ownership
# protects against. Extend this tuple as new clients introduce path-binding
# env vars (vendor-neutral surface, no client tool name in the var-key list).
PATH_BINDING_ENV_KEYS = (
    "CLAUDE_PROJECT_DIR",
    "CLAUDE_WORKTREE_PATH",
    "CODEX_PROJECT_DIR",
    "AUGUR_PROJECT_DIR",
)


@dataclass(frozen=True)
class ActiveWorktreeProcess:
    pid: int
    command: str


def _current_process_lineage() -> set[int]:
    """Return PIDs of this process and all of its ancestors.

    A worktree-removal path runs as a child of the shell that invoked it, and
    that shell's command line routinely contains the target worktree path as an
    argument (for example when Codex thread repair runs in the same shell
    invocation). The shell snapshot path also embeds ``.claude``. Both facts
    make the active-process guard match the very command performing the
    removal. Excluding our own process tree removes that false positive while
    still catching genuine foreign owners.
    """
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,ppid="],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return _current_process_lineage_windows()

    parent_of: dict[int, int] = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        parent_of[pid] = ppid

    if not parent_of and os.name == "nt":
        return _current_process_lineage_windows()

    lineage: set[int] = set()
    current = os.getpid()
    while current > 0 and current not in lineage:
        lineage.add(current)
        current = parent_of.get(current, 0)
    return lineage


def _powershell_executable() -> str | None:
    for candidate in ("powershell.exe", "pwsh.exe", "powershell", "pwsh"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _windows_process_rows() -> list[dict]:
    """Return Win32 process rows, or an empty list if enumeration is unavailable."""
    executable = _powershell_executable()
    if not executable:
        return []

    script = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,CommandLine,ExecutablePath | "
        "ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            [executable, "-NoProfile", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []

    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return [row for row in parsed if isinstance(row, dict)]
    return []


def _current_process_lineage_windows() -> set[int]:
    parent_of: dict[int, int] = {}
    for row in _windows_process_rows():
        try:
            pid = int(row.get("ProcessId") or 0)
            ppid = int(row.get("ParentProcessId") or 0)
        except (TypeError, ValueError):
            continue
        if pid > 0:
            parent_of[pid] = ppid

    lineage: set[int] = set()
    current = os.getpid()
    while current > 0 and current not in lineage:
        lineage.add(current)
        current = parent_of.get(current, 0)
    return lineage or {os.getpid()}


def _path_markers_for(worktree_path: Path, resolved_path: Path) -> set[str]:
    markers = {str(Path(worktree_path).expanduser()), str(resolved_path)}
    if os.name == "nt":
        expanded: set[str] = set()
        for marker in markers:
            if not marker:
                continue
            expanded.add(marker)
            expanded.add(marker.replace("\\", "/"))
            expanded.add(marker.replace("/", "\\"))
        markers = expanded
    return {marker for marker in markers if marker}


def active_ai_processes_for_path(worktree_path: Path) -> list[ActiveWorktreeProcess]:
    """Return live AI/client processes that still own a worktree path.

    Ownership is detected three ways, with deliberately asymmetric lineage
    handling:

    - **`lsof +D` — hard signal.** A process reported by `lsof` has an open
      file descriptor or cwd *under* the worktree. That is genuine ownership
      and is reported **even when the process is in this process's own
      ancestry** — a `/dev-merge` cleaning up the worktree it is itself running
      from must still see itself and defer, not delete the ground it stands on.
    - **`ps` command-line embedding — soft signal.** A launched MCP/client
      helper may have no live FDs by removal time but still point at the
      checkout in its argv. This signal is lineage-filtered: the invoking shell
      legitimately carries the target path in its argv (e.g. as a `/dev-merge`
      argument or via the `.claude` shell-snapshot path), and that false
      positive must not block an otherwise-safe removal.
    - **`ps -E` env-var binding — hard signal.** An AI/client process whose
      env contains `CLAUDE_PROJECT_DIR=<path>` (or a sibling key from
      `PATH_BINDING_ENV_KEYS`) is logically bound to the worktree even when
      its process cwd has relocated and lsof can no longer find it. The hooks
      that session has configured expand `${CLAUDE_PROJECT_DIR}` at fire time;
      removing the worktree breaks them. Not lineage-filtered (the env-var
      binding is the same shape that identifies a real owner — there is no
      argv-noise false positive to suppress here).

    An empty list means no live AI/client session owns the path; a non-empty
    list means the caller MUST defer removal and surface the blocking PIDs.

    TODO_BUG: no orphan/staleness detection — a worktree's own zombie stack
    deadlocks its purge forever. Observed 2026-06-12: an orphaned
    `start-dev.sh` (reparented to PID 1, no TTY) kept the worktree's dashboard
    dev-server alive, which in turn parented an idle interactive claude session
    (transcript untouched for 33h, no shell left on its controlling TTY).
    The guard reported them as live owners on every `worktree_purge_queue.py
    sweep`, so the fully-merged worktree stayed `skip_owned` indefinitely and
    needed manual diagnosis + kill. The guard (or the sweep caller) should
    distinguish a real session from a stalled one — e.g. launcher ancestry
    reparented to PID 1, no terminal emulator holding the controlling TTY,
    and/or client transcript idle beyond a threshold — and either reap or at
    least escalate instead of skipping forever.
    """
    path = Path(worktree_path).expanduser().resolve(strict=False)
    own_lineage = _current_process_lineage()
    try:
        proc = subprocess.run(
            ["lsof", "-Fpc", "+D", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        proc = subprocess.CompletedProcess(["lsof"], 127, stdout="", stderr="")

    processes: dict[int, ActiveWorktreeProcess] = {}
    current_pid: int | None = None
    current_command: str | None = None

    def flush_current() -> None:
        # No lineage filter here: an lsof hit is hard evidence of ownership
        # (open FD / cwd under the path), genuine even for our own session.
        if current_pid is None or not current_command:
            return
        lowered = current_command.lower()
        if any(marker in lowered for marker in AI_CLIENT_PROCESS_MARKERS):
            processes[current_pid] = ActiveWorktreeProcess(pid=current_pid, command=current_command)

    for line in proc.stdout.splitlines():
        if line.startswith("p"):
            flush_current()
            try:
                current_pid = int(line[1:])
            except ValueError:
                current_pid = None
            current_command = None
        elif line.startswith("c"):
            current_command = line[1:]
    flush_current()

    # Some launched MCP/client helpers have no live file descriptors under the
    # worktree by the time removal runs, but their executable path or arguments
    # still point at the checkout. Treat those as active ownership too.
    path_markers = _path_markers_for(worktree_path, path)
    try:
        ps_proc = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        ps_proc = None
    if ps_proc is not None:
        for line in ps_proc.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            pid_text, separator, command = stripped.partition(" ")
            if not separator:
                continue
            try:
                pid = int(pid_text)
            except ValueError:
                continue
            if pid in own_lineage:
                continue
            command = command.strip()
            lowered = command.lower()
            if not any(marker in lowered for marker in AI_CLIENT_PROCESS_MARKERS):
                continue
            if not any(marker and marker in command for marker in path_markers):
                continue
            processes[pid] = ActiveWorktreeProcess(pid=pid, command=command)
    else:
        marker_lowers = {marker.lower() for marker in path_markers}
        for row in _windows_process_rows():
            try:
                pid = int(row.get("ProcessId") or 0)
            except (TypeError, ValueError):
                continue
            if pid in own_lineage:
                continue
            command = str(row.get("CommandLine") or row.get("ExecutablePath") or "").strip()
            if not command:
                continue
            lowered = command.lower()
            if not any(marker in lowered for marker in AI_CLIENT_PROCESS_MARKERS):
                continue
            if not any(marker and marker in lowered for marker in marker_lowers):
                continue
            processes[pid] = ActiveWorktreeProcess(pid=pid, command=command)

    # Third detection: env-var binding. `ps -E` includes each process's
    # environment after its command line; an AI/client process with a
    # `CLAUDE_PROJECT_DIR=<path>` (or sibling) entry is bound to the worktree
    # whether or not it currently has FDs/cwd under it. Match the exact
    # `KEY=<path>` token (substring match, but the key+path is specific
    # enough to avoid argv-noise — a grep with a regex like `KEY=[^ ]+`
    # never produces the literal expanded path).
    bindings: set[str] = set()
    for key in PATH_BINDING_ENV_KEYS:
        for marker in path_markers:
            if marker:
                bindings.add(f"{key}={marker}")
    try:
        env_proc = subprocess.run(
            ["ps", "-axE", "-o", "pid=,command="],
            check=False,
            capture_output=True,
            text=True,
        )
        env_stdout = env_proc.stdout
    except FileNotFoundError:
        env_stdout = ""
    for line in env_stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, separator, command = stripped.partition(" ")
        if not separator:
            continue
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if pid in processes:
            continue  # already reported by an earlier mechanism
        command = command.strip()
        lowered = command.lower()
        if not any(marker in lowered for marker in AI_CLIENT_PROCESS_MARKERS):
            continue
        if not any(binding in command for binding in bindings):
            continue
        processes[pid] = ActiveWorktreeProcess(pid=pid, command=command)

    return list(processes.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repo root or worktree path")
    parser.add_argument("--allowed-branch", default="main")
    parser.add_argument(
        "--active-processes",
        metavar="WORKTREE_PATH",
        help=(
            "Check whether a live AI/client process still owns WORKTREE_PATH. "
            "Exits 0 if it is safe to remove, 3 if a live owner is found. "
            "Every worktree-removal path must pass this before deleting a worktree."
        ),
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.active_processes:
        owners = active_ai_processes_for_path(Path(args.active_processes))
        if args.json:
            print(json.dumps([asdict(p) for p in owners], indent=2))
        elif owners:
            # `ps -axE` env-bound processes carry their full env in `command`,
            # which floods the terminal. Show enough to identify the process
            # and the binding token; full text stays in `--json`.
            for proc in owners:
                snippet = proc.command if len(proc.command) <= 200 else proc.command[:200] + "…"
                print(f"BLOCKED: pid={proc.pid} command={snippet}")
        else:
            print(f"safe to remove: no live AI/client process owns {args.active_processes}")
        return 3 if owners else 0

    result = check_main_checkout_branch(Path(args.repo_root), args.allowed_branch)
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(result.message)
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
