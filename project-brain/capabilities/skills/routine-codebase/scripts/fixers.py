"""d2 safe auto-fixes and git safety net."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


# ── d2 safe fixes ────────────────────────────────────────────────


def fix_cursor_pointer(content: str) -> str:
    """Add cursor-pointer to onClick elements missing it.

    Only modifies lines where onClick AND className appear on the same line.
    Multi-line JSX (onClick on one line, className on another) is not modified
    to avoid breaking formatting — those are left for LLM-assisted fixes at d3+.
    """
    lines = content.splitlines(keepends=True)
    result = []
    for line in lines:
        if (
            re.search(r"onClick\s*=", line)
            and "cursor-pointer" not in line
            and "cursor-not-allowed" not in line
            and "className" in line  # Only fix when className is on the same line
        ):
            # Insert cursor-pointer at start of className value
            line = re.sub(
                r'className="',
                'className="cursor-pointer ',
                line,
            )
            # Handle template literal classNames
            line = re.sub(
                r"className=\{`",
                "className={`cursor-pointer ",
                line,
            )
        result.append(line)
    return "".join(result)


def fix_transition_duration(content: str) -> str:
    """Fix transition durations outside 150-300ms to 200ms.

    Uses regex substitution directly on content to preserve all whitespace.
    """
    def replace_duration(m: re.Match) -> str:
        ms = int(m.group(1))
        if ms == 0:
            return m.group(0)  # duration-0 is intentional
        if ms < 150 or ms > 300:
            return "duration-200"
        return m.group(0)

    return re.sub(r"duration-(\d+)", replace_duration, content)


def apply_safe_fixes(
    content: str, page_path: str
) -> tuple[str, list[str]]:
    """Apply all safe d2 fixes. Returns (fixed_content, list_of_change_descriptions)."""
    changes: list[str] = []

    # Fix cursor-pointer
    fixed = fix_cursor_pointer(content)
    if fixed != content:
        changes.append("added cursor-pointer to onClick elements")
        content = fixed

    # Fix transition durations
    fixed = fix_transition_duration(content)
    if fixed != content:
        changes.append("fixed transition durations to 150-300ms range")
        content = fixed

    return content, changes


# ── Git safety net ───────────────────────────────────────────────


def verify_build(project_root: Path, verify_command: str | None = None) -> bool:
    """Run the engine verify_command. Returns True if build passes.

    When verify_command is None, runs the safe default (npx tsc --noEmit)
    with cwd=apps/dashboard and shell=False — avoids shell injection surface.
    When a caller supplies an explicit string verify_command, that string is
    treated as operator-trusted and runs with shell=True for compatibility
    with shell pipelines.
    """
    try:
        if verify_command is None:
            result = subprocess.run(
                ["npx", "tsc", "--noEmit"],
                cwd=str(project_root / "apps" / "dashboard"),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        else:
            result = subprocess.run(
                verify_command, shell=True, capture_output=True,  # nosec B602  # operator-supplied trusted config (SKILL.md frontmatter / engine verify config), not attacker-controllable input
                cwd=str(project_root),
                text=True,
                timeout=120,
                check=False,
            )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def git_commit(project_root: Path, message: str, files: list[str]) -> bool:
    """Stage files and commit. Returns True on success."""
    try:
        subprocess.run(
            ["git", "add"] + files,
            cwd=str(project_root),
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(project_root),
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def git_revert(project_root: Path) -> bool:
    """Revert the last commit. Returns True on success."""
    try:
        subprocess.run(
            ["git", "revert", "--no-edit", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def safe_fix_page(
    project_root: Path,
    page_path: str,
    page_file: Path,
    score_before: float,
    score_fn,
    verify_command: str | None = None,
    baseline_build_ok: bool | None = None,
) -> dict:
    """Apply safe fixes to a page with git safety net.

    1. Read and fix content
    2. Write fixed file
    3. Commit
    4. Verify build (skip if baseline already broken)
    5. Re-score — revert on regression

    Returns action dict with results.
    """
    content = page_file.read_text()
    fixed_content, changes = apply_safe_fixes(content, page_path)

    if not changes:
        return {"page": page_path, "action": "skip", "reason": "no fixable issues"}

    # Write fix
    page_file.write_text(fixed_content)

    # Commit
    commit_msg = f"fix(auto-ui-quality): improve {page_path} — {', '.join(changes[:3])}"
    if not git_commit(project_root, commit_msg, [str(page_file)]):
        # Restore original
        page_file.write_text(content)
        return {"page": page_path, "action": "skip", "reason": "git commit failed"}

    # Verify build — skip if baseline was already broken (pre-existing errors)
    if baseline_build_ok is True or baseline_build_ok is None:
        if not verify_build(project_root, verify_command):
            if baseline_build_ok is None:
                # First call — check if baseline is also broken
                git_revert(project_root)
                return {"page": page_path, "action": "reverted", "reason": "build failure"}
            else:
                git_revert(project_root)
                return {"page": page_path, "action": "reverted", "reason": "build failure (new errors)"}

    # Re-score
    score_after = score_fn(page_path)
    if score_after < score_before:
        git_revert(project_root)
        return {
            "page": page_path,
            "action": "reverted",
            "reason": f"score regression {score_before:.0f} → {score_after:.0f}",
        }

    return {
        "page": page_path,
        "action": "fixed",
        "changes": changes,
        "score_before": score_before,
        "score_after": score_after,
    }
