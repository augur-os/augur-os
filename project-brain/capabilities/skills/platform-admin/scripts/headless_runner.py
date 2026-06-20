#!/usr/bin/env python3
"""
Headless Task Runner for Augur autonomous execution.

Takes a backlog task file, constructs a prompt with full context,
executes via Claude Code CLI in --print mode, and creates a draft PR
with the results.

Each execution runs in an isolated git worktree to support parallel runs.

Usage:
    python headless_runner.py --task /path/to/task.md
    python headless_runner.py --task /path/to/task.md --dry-run
    python headless_runner.py --task /path/to/task.md --model opus
"""
# TODO_CLEANUP: This file is 811 lines — consider splitting into smaller modules

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired, run  # nosec B404
from typing import Any


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve command executable to absolute path when available."""
    if not command:
        raise ValueError("Command must not be empty")

    executable = command[0]
    if Path(executable).is_absolute():
        return command

    resolved = shutil.which(executable)
    if not resolved:
        return command

    return [resolved, *command[1:]]


def _run_command(command: list[str], **kwargs: object) -> CompletedProcess:
    """Run subprocess with resolved executable path."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


from bootstrap_paths import ensure_project_paths  # noqa: E402

# Setup project root for imports
PROJECT_ROOT = ensure_project_paths(__file__)
SCRIPTS_DIR = Path(__file__).resolve().parent

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from src.config.paths import get_logs_dir  # noqa: E402
from codex_thread_state import repoint_threads_for_removed_worktree  # noqa: E402
from task_utils import read_task, task_lock, task_title, write_task  # noqa: E402
from worktree_guard import active_ai_processes_for_path  # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

WORKTREE_BASE = PROJECT_ROOT / ".worktrees"
LOG_DIR = get_logs_dir() / "headless"

ALLOWED_TOOLS = [
    "Edit",
    "Write",
    "Read",
    "Bash",
    "Glob",
    "Grep",
    "TodoWrite",
]

DEFAULT_TIMEOUT = 3600  # 1 hour
DEFAULT_MAX_BUDGET = 5.0  # $5 per task

# Files that must never be committed by autonomous execution
SENSITIVE_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.keystore",
    "credentials.json",
    "secrets.yaml",
    "secrets.yml",
    "*.secret",
    "token.json",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "id_rsa",
    "id_ed25519",
]


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RunResult:
    """Result of a headless task execution."""

    task_id: str
    task_path: str
    task_title: str
    task_type: str
    success: bool
    branch_name: str
    worktree_path: str
    pr_url: str | None = None
    pr_number: int | None = None
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    error: str | None = None
    duration_seconds: float = 0.0
    files_changed: int = 0
    started_at: str = ""
    completed_at: str = ""
    model: str = "sonnet"
    dry_run: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# TASK PARSING
# ═══════════════════════════════════════════════════════════════════════════════


def parse_task(task_path: Path) -> tuple[dict[str, Any], str, str, str]:
    """Parse a backlog task file and extract key fields.

    Returns:
        (frontmatter, body, task_id, title)
    """
    frontmatter, body = read_task(task_path)
    tid = str(frontmatter.get("id", task_path.stem))
    title = task_title(body, task_path.stem)
    return frontmatter, body, tid, title


def build_prompt(frontmatter: dict[str, Any], body: str, title: str) -> str:
    """Build a Claude Code prompt from task content.

    Constructs a structured prompt that gives Claude Code full context
    about the task, acceptance criteria, and constraints.
    """
    task_type = str(frontmatter.get("type", "unknown")).strip()
    priority = str(frontmatter.get("priority", "medium")).strip()
    workspace = str(frontmatter.get("workspace", str(PROJECT_ROOT))).strip()

    prompt_parts = [
        f"# Task: {title}",
        "",
        f"**Type**: {task_type}",
        f"**Priority**: {priority}",
        f"**Workspace**: {workspace}",
        "",
        "## Instructions",
        "",
        body,
        "",
        "## Execution Rules",
        "",
        "- Complete the task fully as described above.",
        "- Follow existing code patterns and conventions in the codebase.",
        "- Run tests or build commands if relevant to verify your changes.",
        "- Do NOT commit changes — the runner handles git operations.",
        "- If you encounter blockers, document them clearly in your output.",
    ]

    return "\n".join(prompt_parts)


# ═══════════════════════════════════════════════════════════════════════════════
# GIT WORKTREE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════


def create_worktree(task_id: str) -> tuple[Path, str]:
    """Create an isolated git worktree for this task.

    Returns:
        (worktree_path, branch_name)
    """
    # Sanitize task_id for branch name
    safe_id = task_id.replace(" ", "-").replace("/", "-")[:60]
    branch_name = f"auto/{safe_id}"
    worktree_path = WORKTREE_BASE / f"auto-{safe_id}"

    WORKTREE_BASE.mkdir(parents=True, exist_ok=True)

    # Clean up stale worktree if it exists
    if worktree_path.exists():
        cleanup_worktree(worktree_path, branch_name)

    # Ensure main is up to date
    _run_command(
        ["git", "fetch", "origin", "main"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        timeout=30,
    )

    # Create worktree with new branch from origin/main
    result = _run_command(
        ["git", "worktree", "add", str(worktree_path), "-b", branch_name, "origin/main"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        # Branch might already exist — try without -b
        _run_command(
            ["git", "branch", "-D", branch_name],
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=10,
        )
        result = _run_command(
            ["git", "worktree", "add", str(worktree_path), "-b", branch_name, "origin/main"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {result.stderr}")

    return worktree_path, branch_name


def cleanup_worktree(worktree_path: Path, branch_name: str) -> None:
    """Remove a git worktree and its branch.

    Never removes a worktree a live AI/client session still owns — doing so
    orphans that session (crashes its cwd mid-command, breaks
    ${CLAUDE_PROJECT_DIR} hooks). When a live owner is found, the removal AND
    the branch deletion are deferred and the blocking PIDs are reported.
    """
    active = active_ai_processes_for_path(worktree_path)
    if active:
        for proc in active:
            _out(
                f"headless_runner: deferring worktree removal — {worktree_path} is "
                f"owned by a live AI/client process pid={proc.pid} ({proc.command})",
                file=sys.stderr,
            )
        return
    try:
        _run_command(
            ["git", "worktree", "remove", str(worktree_path), "--force"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=15,
        )
    except Exception as exc:
        # Fallback: manual cleanup
        _out(f"headless_runner: worktree remove failed ({exc}), using fallback cleanup", file=sys.stderr)
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)
        _run_command(
            ["git", "worktree", "prune"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=10,
        )

    try:
        repoint_threads_for_removed_worktree(
            worktree_path=worktree_path,
            repo_root=PROJECT_ROOT,
            target_branch="main",
        )
    except Exception as exc:
        _out(f"headless_runner: Codex thread state repair failed ({exc})", file=sys.stderr)

    # Delete the branch (it was merged via PR or failed)
    try:
        _run_command(
            ["git", "branch", "-D", branch_name],
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=10,
        )
    except Exception as exc:
        _out(f"headless_runner: branch cleanup failed ({exc})", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════════════
# CLAUDE CODE EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════


def run_claude(
    prompt: str,
    worktree_path: Path,
    model: str = "sonnet",
    timeout: int = DEFAULT_TIMEOUT,
    max_budget: float = DEFAULT_MAX_BUDGET,
) -> tuple[int, str, str]:
    """Execute Claude Code CLI in non-interactive --print mode.

    Returns:
        (exit_code, stdout, stderr)
    """
    cmd = [
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        "--no-session-persistence",
        f"--model={model}",
        f"--max-budget-usd={max_budget}",
        f"--allowedTools={','.join(ALLOWED_TOOLS)}",
        "-p",
        prompt,
    ]

    env = os.environ.copy()
    env["CLAUDE_CODE_HEADLESS"] = "1"

    try:
        proc = _run_command(
            cmd,
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except TimeoutExpired:
        return -1, "", f"Timeout after {timeout}s"
    except FileNotFoundError:
        return -2, "", "claude CLI not found in PATH"


# ═══════════════════════════════════════════════════════════════════════════════
# GIT OPERATIONS (POST-EXECUTION)
# ═══════════════════════════════════════════════════════════════════════════════


def count_changes(worktree_path: Path) -> int:
    """Count files changed in the worktree."""
    result = _run_command(
        ["git", "status", "--porcelain"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return len([line for line in result.stdout.strip().split("\n") if line.strip()])


def _is_sensitive_file(filepath: str) -> bool:
    """Check if a file matches sensitive patterns that should never be committed."""
    import fnmatch

    name = Path(filepath).name
    for pattern in SENSITIVE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def _filter_and_stage(worktree_path: Path) -> list[str]:
    """Stage changes, excluding sensitive files. Returns list of blocked files."""
    result = _run_command(
        ["git", "status", "--porcelain"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    blocked: list[str] = []
    safe_files: list[str] = []

    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        # porcelain format: XY filename (or XY old -> new for renames)
        filepath = line[3:].strip().split(" -> ")[-1]
        if _is_sensitive_file(filepath):
            blocked.append(filepath)
        else:
            safe_files.append(filepath)

    if safe_files:
        _run_command(
            ["git", "add", "--"] + safe_files,
            cwd=worktree_path,
            capture_output=True,
            timeout=15,
        )

    return blocked


def commit_and_push(
    worktree_path: Path,
    branch_name: str,
    title: str,
    task_type: str,
) -> bool:
    """Stage, commit, and push changes from worktree.

    Filters out sensitive files (secrets, keys, credentials) before staging.

    Returns:
        True if changes were committed and pushed.
    """
    # Check if there are changes
    if count_changes(worktree_path) == 0:
        return False

    # Stage changes, filtering out sensitive files
    _ = _filter_and_stage(worktree_path)

    # Commit
    commit_msg = f"auto({task_type}): {title}\n\nAutonomous execution by headless_runner.py"
    result = _run_command(
        ["git", "commit", "-m", commit_msg],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return False

    # Push
    result = _run_command(
        ["git", "push", "-u", "origin", branch_name],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode == 0


def create_draft_pr(
    branch_name: str,
    title: str,
    task_type: str,
    body: str,
    stdout_summary: str,
) -> tuple[str | None, int | None]:
    """Create a draft pull request via gh CLI.

    Returns:
        (pr_url, pr_number) or (None, None) on failure.
    """
    pr_body = f"""## Auto-generated PR

**Task type**: `{task_type}`
**Branch**: `{branch_name}`
**Generated by**: `headless_runner.py`

### Task Description

{body[:1500]}

### Execution Summary

```
{stdout_summary[:2000]}
```

---
*This PR was created autonomously. Please review before merging.*
"""

    result = _run_command(
        [
            "gh",
            "pr",
            "create",
            "--draft",
            "--title",
            f"auto({task_type}): {title}",
            "--body",
            pr_body,
            "--base",
            "main",
            "--head",
            branch_name,
            "--label",
            f"auto/{task_type}" if task_type else "auto",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        # Labels might not exist — retry without label
        result = _run_command(
            [
                "gh",
                "pr",
                "create",
                "--draft",
                "--title",
                f"auto({task_type}): {title}",
                "--body",
                pr_body,
                "--base",
                "main",
                "--head",
                branch_name,
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

    if result.returncode == 0:
        pr_url = result.stdout.strip()
        # Extract PR number from URL
        try:
            pr_number = int(pr_url.rstrip("/").split("/")[-1])
        except (ValueError, IndexError):
            pr_number = None
        return pr_url, pr_number

    return None, None


# ═══════════════════════════════════════════════════════════════════════════════
# TASK STATUS UPDATES
# ═══════════════════════════════════════════════════════════════════════════════


def claim_task(task_path: Path, frontmatter: dict[str, Any], body: str) -> bool:
    """Atomically claim a task using file-level locking.

    Returns True if the claim succeeded (task was still available).
    Returns False if another executor already claimed it.
    """
    from task_utils import is_task_available

    with task_lock(task_path):
        # Re-read the task under lock to check if still available
        fresh_fm, fresh_body = read_task(task_path)
        if not is_task_available(fresh_fm):
            return False

        # Mark as claimed
        execution = dict(fresh_fm.get("execution") or {})
        execution["status"] = "claimed"
        execution["claimed_at"] = datetime.now().isoformat()
        fresh_fm["execution"] = execution
        write_task(task_path, fresh_fm, fresh_body)

    # Update the caller's frontmatter to reflect the claim
    frontmatter["execution"] = fresh_fm["execution"]
    return True


def update_task_status(
    task_path: Path,
    frontmatter: dict[str, Any],
    body: str,
    status: str,
    pr_url: str | None = None,
    error: str | None = None,
) -> None:
    """Update task frontmatter with execution result.

    Uses file-level locking to prevent concurrent writes. Updates both the
    execution sub-dict and the top-level status field to prevent the task
    from being picked up again by is_task_available().
    """
    with task_lock(task_path):
        execution = dict(frontmatter.get("execution") or {})
        now = datetime.now().isoformat()

        execution["status"] = status
        execution["completed_at"] = now

        if pr_url:
            execution["pr_url"] = pr_url
        if error:
            execution["error"] = error[:500]

        frontmatter["execution"] = execution

        # Update top-level status so is_task_available() won't pick this up again
        if status == "completed":
            frontmatter["status"] = "completed"
        elif status == "failed":
            frontmatter["status"] = "failed"

        write_task(task_path, frontmatter, body)


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════


def write_run_log(result: RunResult) -> Path:
    """Write execution result to a JSON log file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"run-{result.task_id}-{timestamp}.json"
    log_path.write_text(
        json.dumps(asdict(result), indent=2, default=str),
        encoding="utf-8",
    )
    return log_path


def truncate(text: str, max_len: int = 3000) -> str:
    """Truncate text to max_len, keeping the tail (most recent output)."""
    if len(text) <= max_len:
        return text
    return "...[truncated]...\n" + text[-max_len:]


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════


def execute_task(
    task_path: Path,
    model: str = "sonnet",
    timeout: int = DEFAULT_TIMEOUT,
    max_budget: float = DEFAULT_MAX_BUDGET,
    dry_run: bool = False,
) -> RunResult:
    """Execute a single backlog task autonomously.

    1. Parse task
    2. Create worktree
    3. Run Claude Code
    4. Commit + PR if changes
    5. Update task status
    6. Cleanup
    """
    start_time = time.time()
    started_at = datetime.now().isoformat()

    # Parse task
    frontmatter, body, task_id, title = parse_task(task_path)
    task_type = str(frontmatter.get("type", "unknown")).strip()

    result = RunResult(
        task_id=task_id,
        task_path=str(task_path),
        task_title=title,
        task_type=task_type,
        success=False,
        branch_name="",
        worktree_path="",
        started_at=started_at,
        model=model,
        dry_run=dry_run,
    )

    if dry_run:
        prompt = build_prompt(frontmatter, body, title)
        result.success = True
        result.stdout_tail = f"[DRY RUN] Would execute with model={model}:\n{prompt[:500]}"
        result.completed_at = datetime.now().isoformat()
        result.duration_seconds = time.time() - start_time
        write_run_log(result)
        return result

    # Atomically claim the task (prevents parallel executors from double-running)
    if not claim_task(task_path, frontmatter, body):
        result.error = "Task already claimed by another executor"
        result.completed_at = datetime.now().isoformat()
        result.duration_seconds = time.time() - start_time
        write_run_log(result)
        return result

    worktree_path = None
    branch_name = ""

    try:
        # Create isolated worktree
        worktree_path, branch_name = create_worktree(task_id)
        result.branch_name = branch_name
        result.worktree_path = str(worktree_path)

        # Build prompt
        prompt = build_prompt(frontmatter, body, title)

        # Execute Claude Code
        exit_code, stdout, stderr = run_claude(
            prompt=prompt,
            worktree_path=worktree_path,
            model=model,
            timeout=timeout,
            max_budget=max_budget,
        )

        result.exit_code = exit_code
        result.stdout_tail = truncate(stdout)
        result.stderr_tail = truncate(stderr)

        if exit_code != 0:
            result.error = f"Claude Code exited with code {exit_code}"
            update_task_status(task_path, frontmatter, body, "failed", error=result.error)
            return result

        # Check for changes
        files_changed = count_changes(worktree_path)
        result.files_changed = files_changed

        if files_changed == 0:
            result.success = True
            result.error = "No file changes produced"
            update_task_status(task_path, frontmatter, body, "completed")
            return result

        # Commit and push
        pushed = commit_and_push(worktree_path, branch_name, title, task_type)
        if not pushed:
            result.error = "Failed to commit and push changes"
            update_task_status(task_path, frontmatter, body, "failed", error=result.error)
            return result

        # Create draft PR
        pr_url, pr_number = create_draft_pr(
            branch_name=branch_name,
            title=title,
            task_type=task_type,
            body=body,
            stdout_summary=truncate(stdout, 2000),
        )

        result.pr_url = pr_url
        result.pr_number = pr_number
        result.success = True

        update_task_status(task_path, frontmatter, body, "completed", pr_url=pr_url)

    except Exception as e:
        result.error = str(e)
        try:
            update_task_status(task_path, frontmatter, body, "failed", error=str(e))
        except Exception as update_error:
            _out(f"headless_runner: failed to update task status ({update_error})", file=sys.stderr)

    finally:
        result.completed_at = datetime.now().isoformat()
        result.duration_seconds = time.time() - start_time

        # Cleanup worktree (keep branch for PR)
        if worktree_path and worktree_path.exists():
            active = active_ai_processes_for_path(worktree_path)
            if active:
                # Never remove a worktree a live AI/client session still owns.
                for proc in active:
                    _out(
                        f"headless_runner: deferring worktree removal — {worktree_path} "
                        f"is owned by a live AI/client process pid={proc.pid} "
                        f"({proc.command})",
                        file=sys.stderr,
                    )
            else:
                try:
                    _run_command(
                        ["git", "worktree", "remove", str(worktree_path), "--force"],
                        cwd=PROJECT_ROOT,
                        capture_output=True,
                        timeout=15,
                    )
                except Exception:
                    shutil.rmtree(worktree_path, ignore_errors=True)
                    _run_command(
                        ["git", "worktree", "prune"],
                        cwd=PROJECT_ROOT,
                        capture_output=True,
                        timeout=10,
                    )

        write_run_log(result)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Headless task runner for Augur autonomous execution")
    parser.add_argument("--task", type=str, required=True, help="Path to the backlog task markdown file")
    parser.add_argument("--model", type=str, default="sonnet", help="Claude model tier (haiku, sonnet, opus)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Execution timeout in seconds")
    parser.add_argument("--max-budget", type=float, default=DEFAULT_MAX_BUDGET, help="Max USD budget per task")
    parser.add_argument("--dry-run", action="store_true", help="Parse task and show prompt without executing")
    args = parser.parse_args()

    task_path = Path(args.task).resolve()
    if not task_path.exists():
        _out(f"headless_runner: task file not found: {task_path}")
        return 1

    result = execute_task(
        task_path=task_path,
        model=args.model,
        timeout=args.timeout,
        max_budget=args.max_budget,
        dry_run=args.dry_run,
    )

    # Print summary
    status = "SUCCESS" if result.success else "FAILED"
    _out(f"headless_runner: {status} | task={result.task_id} | model={result.model}")
    _out(f"  duration={result.duration_seconds:.1f}s | files_changed={result.files_changed}")
    if result.pr_url:
        _out(f"  pr={result.pr_url}")
    if result.error:
        _out(f"  error={result.error}")

    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
