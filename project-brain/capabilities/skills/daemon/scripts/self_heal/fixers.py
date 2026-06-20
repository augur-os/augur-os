"""Fix implementations — headless debug sessions, fix lock, context gathering."""

from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ai_self_healer import RegistryEntry


FIX_PROMPT = """AUTONOMOUS SELF-HEAL MODE — No user interaction available.
You MUST fix this issue and commit. Do NOT just analyze — produce a working fix.

Severity: {severity} — {severity_instruction}

Error: {message}
Source log: {file}
Stack trace: {stack_trace}
Category: {category}
Suggested approach: {suggested_approach}

Log context (lines around the error):
```
{log_context}
```
{retry_context}
STEP 1 — ASSESS (1 turn max)
  If the error involves MCP tool registration, API schema validation across
  multiple services, or architectural changes across 3+ files, output ABORT_COMPLEX.
  If complexity > {complexity_threshold}/10, output ABORT_COMPLEX.

STEP 2 — READ & DIAGNOSE (2-3 turns)
  Read the source file referenced in the error. Read the log context.
  State the root cause in one sentence.

STEP 3 — FIX (2-4 turns)
  Edit the source file(s). Apply the smallest correct fix.
  Do NOT modify more than {max_files} files.
  Do NOT install new dependencies.
  Do NOT modify tests to make them pass — fix the source code.

STEP 4 — COMMIT (1 turn)
  Run: git add <changed files> && git commit -m "{commit_prefix} <description>"
  The fix is NOT complete until a commit exists.

OUTPUT EXACTLY ONE OF:
  - ABORT_COMPLEX (if too complex for automated fix)
  - COMMIT: <hash> (if fix committed successfully)
  - FAILED: <reason> (if fix could not be applied)
"""

RETRY_CONTEXT_TEMPLATE = """
PREVIOUS ATTEMPT FAILED — Attempt {attempt} of {max_attempts}.
Previous output: {prev_output}
The previous attempt did NOT produce a commit. You MUST go deeper:
- Re-read the source files and understand the full context
- Try a different approach than before
- The fix MUST result in a git commit with prefix "{commit_prefix}"
"""

SEVERITY_INSTRUCTIONS = {
    "critical": "System is DOWN. This is the highest priority. Investigate thoroughly, fix immediately, commit.",
    "high": "Feature is BROKEN with user-visible impact. Debug in depth, fix and commit.",
    "medium": "Non-critical issue but worth fixing now. Investigate, apply a focused fix, commit.",
}


def _pid_alive(pid: int) -> bool:
    """Check if a process is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def acquire_fix_lock(issue_key: str) -> bool:
    """Acquire the fix lock. Returns True if acquired."""
    import ai_self_healer as _healer

    _healer.FIX_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    if _healer.FIX_LOCK_FILE.exists():
        try:
            lock_data = json.loads(_healer.FIX_LOCK_FILE.read_text())
            started = datetime.fromisoformat(lock_data.get("started", ""))
            lock_pid = lock_data.get("pid", 0)
            age_s = (datetime.now() - started).total_seconds()
            # Stale lock: older than 10 minutes OR owning PID is dead
            if age_s > 600 or (lock_pid and not _pid_alive(lock_pid)):
                reason = f"age={age_s:.0f}s" if age_s > 600 else f"pid {lock_pid} dead"
                _healer.logger.warning("Removing stale fix lock (%s)", reason)
                _healer.FIX_LOCK_FILE.unlink()
            else:
                return False
        except Exception:
            _healer.FIX_LOCK_FILE.unlink(missing_ok=True)

    lock_data = {
        "issue_key": issue_key,
        "started": datetime.now().isoformat(),
        "pid": os.getpid(),
    }
    _healer.FIX_LOCK_FILE.write_text(json.dumps(lock_data))
    return True


def release_fix_lock() -> None:
    """Release the fix lock."""
    import ai_self_healer as _healer
    _healer.FIX_LOCK_FILE.unlink(missing_ok=True)


def _gather_log_context(entry: "RegistryEntry", config: dict) -> str:
    """Read lines around the error from the source log file."""
    import ai_self_healer as _healer

    context_lines = config.get("fix", {}).get("log_context_lines", 30)
    half = context_lines // 2

    # Find the actual log file
    # entry.file is stored as a project-relative path (e.g. logs/daemon.stderr.log)
    log_path = _healer.PROJECT_ROOT / entry.file
    if not log_path.exists():
        # Fallback: treat as filename only under LOGS_DIR
        log_path = _healer.LOGS_DIR / Path(entry.file).name
    if not log_path.exists():
        # Try globbing — file might be in a subdirectory
        candidates = list(_healer.LOGS_DIR.rglob(Path(entry.file).name))
        if not candidates:
            return f"(log file {entry.file} not found)"
        log_path = candidates[0]

    try:
        lines = log_path.read_text(errors="replace").splitlines()
    except Exception:
        return f"(could not read {entry.file})"

    # Find the error line
    search_term = entry.message[:80]
    target_idx = None
    for i, line in enumerate(lines):
        if search_term in line:
            target_idx = i
            break

    if target_idx is None:
        # Return last N lines as fallback
        return "\n".join(lines[-context_lines:])

    start = max(0, target_idx - half)
    end = min(len(lines), target_idx + half)
    context = lines[start:end]
    return "\n".join(f"{start + i + 1}: {line}" for i, line in enumerate(context))


def _get_severity_profile(entry: "RegistryEntry", config: dict) -> dict:
    """Get severity-scaled fix parameters."""
    fix_conf = config.get("fix", {})
    profiles = fix_conf.get("severity_profiles", {})
    severity = entry.severity.lower()

    # Use profile if available, otherwise defaults
    profile = profiles.get(severity, {})
    return {
        "max_turns": profile.get("max_turns", 10),
        "max_files": profile.get("max_files_modified", 3),
        "complexity_threshold": profile.get("complexity_abort_threshold", 7),
        "timeout": profile.get("timeout_s", 300),
    }


def _get_head_hash() -> Optional[str]:
    """Return the current HEAD short hash."""
    import ai_self_healer as _healer
    try:
        proc = _healer.subprocess.Popen(  # nosec B603,B607
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_healer.PROJECT_ROOT),
            stdout=_healer.subprocess.PIPE,
            stderr=_healer.subprocess.PIPE,
            text=True,
        )
        stdout, _ = proc.communicate(timeout=10)
        if proc.returncode != 0:
            return None
        return stdout.strip() or None
    except Exception:
        return None


def _check_for_fix_commit(commit_prefix: str, before_hash: Optional[str]) -> Optional[str]:
    """Check if a NEW self-heal commit was produced since before_hash. Returns hash or None."""
    import ai_self_healer as _healer
    try:
        proc = _healer.subprocess.Popen(  # nosec B603,B607
            ["git", "log", "--oneline", "-1"],
            cwd=str(_healer.PROJECT_ROOT),
            stdout=_healer.subprocess.PIPE,
            stderr=_healer.subprocess.PIPE,
            text=True,
        )
        stdout, _ = proc.communicate(timeout=10)
        if proc.returncode != 0:
            return None
        latest = stdout.strip()
        if commit_prefix in latest:
            match = re.search(r"^([0-9a-f]{7,40})", latest)
            if match:
                new_hash = match.group(1)
                # Only count as success if HEAD actually changed
                if before_hash and new_hash == before_hash:
                    return None
                return new_hash
    except Exception:
        pass
    return None


def execute_shell_action(
    entry: "RegistryEntry",
    cmd: list[str],
    description: str,
) -> dict:
    """Execute a shell command to fix a known issue pattern.

    Returns dict with keys: success, output, shell_action.
    """
    import ai_self_healer as _healer

    _healer.logger.info(f"Shell action for {entry.dedup_key}: {description}")
    try:
        result = _healer.subprocess.run(  # nosec B603
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(_healer.PROJECT_ROOT),
        )
        output = result.stdout[:1000]
        if result.returncode != 0:
            err = result.stderr[:500]
            _healer.logger.warning(f"Shell action failed (rc={result.returncode}): {err}")
            return {"success": False, "output": f"rc={result.returncode}: {err}", "shell_action": description}
        _healer.logger.info(f"Shell action succeeded: {description}")
        return {"success": True, "output": output, "shell_action": description}
    except _healer.subprocess.TimeoutExpired:
        _healer.logger.warning(f"Shell action timed out: {description}")
        return {"success": False, "output": "timed out after 120s", "shell_action": description}
    except Exception as e:
        _healer.logger.warning(f"Shell action error: {e}")
        return {"success": False, "output": str(e), "shell_action": description}


def invoke_headless_fix(
    entry: "RegistryEntry",
    config: dict,
    cli_path: Optional[str] = None,
) -> dict:
    """Spawn CLI debug sessions to fix the issue with retry loop.

    For critical/high: gathers log context, uses severity-scaled parameters,
    retries with feedback if first attempt doesn't produce a commit.

    Returns dict with keys: success, aborted, output, commit.
    """
    import ai_self_healer as _healer

    if cli_path is None:
        # Look up through _healer so tests can patch ai_self_healer.resolve_cli
        cli_path = _healer.resolve_cli(config)

    if not cli_path:
        return {"success": False, "aborted": False, "output": "No CLI available"}

    from src.lib.llm_retry import build_headless_cmd

    fix_conf = config.get("fix", {})
    llm_conf = config.get("llm", {})
    commit_prefix = fix_conf.get("commit_prefix", "fix(self-heal):")
    max_attempts = fix_conf.get("max_fix_attempts", 3)
    fix_model = llm_conf.get("fix_model", "sonnet")
    fix_tools = llm_conf.get("fix_allowed_tools", "Read,Edit,Bash,Grep,Glob,Write")

    # Severity-scaled parameters
    profile = _get_severity_profile(entry, config)

    # Gather context — use _healer so tests can patch ai_self_healer._gather_log_context
    log_context = _healer._gather_log_context(entry, config)
    severity_instruction = SEVERITY_INSTRUCTIONS.get(
        entry.severity.lower(),
        "Fix and commit.",
    )

    all_outputs: list[str] = []

    for attempt in range(1, max_attempts + 1):
        retry_context = ""
        if attempt > 1:
            retry_context = RETRY_CONTEXT_TEMPLATE.format(
                attempt=attempt,
                max_attempts=max_attempts,
                prev_output=all_outputs[-1][:500] if all_outputs else "N/A",
                commit_prefix=commit_prefix,
            )

        prompt = FIX_PROMPT.format(
            message=entry.message[:500],
            severity=entry.severity.upper(),
            severity_instruction=severity_instruction,
            file=entry.file,
            stack_trace=entry.stack_trace or "N/A",
            category=entry.category,
            suggested_approach=entry.suggested_approach or "Investigate the error and apply minimal fix",
            log_context=log_context[:2000],
            retry_context=retry_context,
            max_files=profile["max_files"],
            complexity_threshold=profile["complexity_threshold"],
            commit_prefix=commit_prefix,
        )

        _healer.logger.info(f"Fix attempt {attempt}/{max_attempts} for {entry.dedup_key} (severity={entry.severity})")

        # Snapshot HEAD before the attempt so we can detect new commits
        head_before = _healer._get_head_hash()

        try:
            cmd = build_headless_cmd(
                cli_path, prompt,
                model=fix_model,
                max_turns=profile["max_turns"],
                allowed_tools=fix_tools,
                bypass_approvals=True,
            )
            # Clear CLAUDECODE env var to prevent "nested session" blocking
            # when daemon was started from a Claude Code session
            fix_env = os.environ.copy()
            fix_env.pop("CLAUDECODE", None)
            fix_env.pop("CLAUDE_CODE", None)
            # Use _healer.subprocess so tests can patch ai_self_healer.subprocess.run
            result = _healer.subprocess.run(  # nosec B603
                cmd,
                capture_output=True,
                text=True,
                timeout=profile["timeout"],
                cwd=str(_healer.PROJECT_ROOT),
                env=fix_env,
            )

            output = result.stdout[:3000]
            if not output and result.stderr:
                _healer.logger.warning(f"Attempt {attempt}: empty stdout, stderr: {result.stderr[:500]}")
            all_outputs.append(output)

            if "ABORT_COMPLEX" in output:
                return {"success": False, "aborted": True, "output": output}

            # Check if a NEW self-heal commit was actually made
            commit_hash = _healer._check_for_fix_commit(commit_prefix, head_before)
            if commit_hash:
                _healer.logger.info(f"Fix committed: {commit_hash} (attempt {attempt})")
                return {
                    "success": True,
                    "aborted": False,
                    "output": output,
                    "commit": commit_hash,
                }

            # No commit — check for stagnation before retrying
            _healer.logger.warning(f"Attempt {attempt}: CLI exited 0 but no commit produced")

            # Early exit: if output is substantially the same as previous attempt,
            # the LLM is stuck and retrying won't help
            if len(all_outputs) >= 2:
                prev = all_outputs[-2][:500]
                curr = output[:500]
                if prev and curr and prev == curr:
                    _healer.logger.warning(f"Output stagnation detected at attempt {attempt} — aborting early")
                    combined = "\n---\n".join(all_outputs)
                    return {
                        "success": False,
                        "aborted": True,
                        "output": f"Stagnant output after {attempt} attempts.\n{combined[:2000]}",
                    }

        except _healer.subprocess.TimeoutExpired:
            all_outputs.append(f"Attempt {attempt} timed out after {profile['timeout']}s")
            _healer.logger.warning(f"Attempt {attempt} timed out")
        except Exception as e:
            all_outputs.append(str(e))
            _healer.logger.warning(f"Attempt {attempt} error: {e}")
            return {"success": False, "aborted": False, "output": str(e)}

    # All attempts exhausted
    combined = "\n---\n".join(all_outputs)
    return {
        "success": False,
        "aborted": False,
        "output": f"All {max_attempts} attempts failed.\n{combined[:2000]}",
    }
