"""Git signal collector for agent-digest.

Scans recent git commits for anti-patterns defined in violation-patterns.yaml.
Yields events for each matched violation.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml


def load_patterns(patterns_path: Path) -> list[dict]:
    """Load violation patterns from YAML config."""
    with patterns_path.open() as f:
        data = yaml.safe_load(f)
    return data.get("patterns", [])


def match_patterns(
    diff_line: str,
    file_path: str,
    patterns: list[dict],
) -> list[dict]:
    """Match a single added diff line against violation patterns.

    Only matches lines starting with '+' (additions, not removals).
    Returns list of matched pattern dicts.
    """
    if not diff_line.startswith("+"):
        return []
    content = diff_line[1:]
    matches = []
    for pattern in patterns:
        scope = pattern.get("scope")
        if scope and not file_path.startswith(scope):
            continue
        if re.search(pattern["regex"], content):
            matches.append(pattern)
    return matches


def parse_git_diff_files(diff_output: str | None) -> dict[str, list[str]]:
    """Parse git diff output into {file_path: [added_lines]}."""
    if not diff_output:
        return {}
    files: dict[str, list[str]] = {}
    current_file = None
    for line in diff_output.split("\n"):
        if line.startswith("+++ b/"):
            current_file = line[6:]
            files.setdefault(current_file, [])
        elif line.startswith("+") and not line.startswith("+++") and current_file:
            files[current_file].append(line)
    return files


def _read_last_scanned_commit(state_path: Path) -> str | None:
    """Read the last scanned commit SHA from state file."""
    if state_path.exists():
        sha = state_path.read_text().strip()
        return sha if sha else None
    return None


def _write_last_scanned_commit(state_path: Path, sha: str) -> None:
    """Persist the last scanned commit SHA."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(sha + "\n")


def _line_existed_in_parent(
    project_root: Path, commit: str, file_path: str, line_content: str,
) -> bool:
    """Check if a line existed in the parent commit's version of the file.

    If the line was already present before this commit, it's a moved/reformatted
    line, not a genuinely new violation.
    """
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}~1:{file_path}"],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode != 0:
            return False  # file didn't exist in parent — line is genuinely new
        return line_content in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def collect(
    project_root: Path,
    patterns_path: Path,
    since_hours: int = 24,
    state_dir: Path | None = None,
) -> list[dict]:
    """Collect git violation events from recent commits.

    If state_dir is provided, tracks the last scanned commit to avoid
    re-scanning the same commits on subsequent runs.
    Only flags genuinely new lines (not moved/reformatted from parent).
    """
    patterns = load_patterns(patterns_path)

    # Determine scan range
    last_sha = None
    state_path = state_dir / "last-scanned-commit" if state_dir else None
    if state_path:
        last_sha = _read_last_scanned_commit(state_path)

    if last_sha:
        # Only scan commits after the last scanned one
        git_log_cmd = ["git", "log", f"{last_sha}..HEAD", "--format=%H"]
    else:
        git_log_cmd = ["git", "log", f"--since={since_hours} hours ago", "--format=%H"]

    try:
        result = subprocess.run(
            git_log_cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        commits = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    if not commits:
        return []

    events = []
    now = datetime.now(timezone.utc).isoformat()

    for commit in commits:
        try:
            diff_result = subprocess.run(
                ["git", "diff", f"{commit}~1", commit, "--unified=0"],
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            continue

        file_lines = parse_git_diff_files(diff_result.stdout)
        for file_path, added_lines in file_lines.items():
            for line in added_lines:
                matches = match_patterns(line, file_path, patterns)
                if not matches:
                    continue
                # Skip lines that existed in the parent (moved/reformatted, not new)
                line_content = line[1:]  # strip leading '+'
                if _line_existed_in_parent(project_root, commit, file_path, line_content):
                    continue
                for match in matches:
                    events.append({
                        "ts": now,
                        "source": "git",
                        "type": "pattern_violation",
                        "rule": match["directive"],
                        "evidence": f"commit {commit[:7]} added '{line_content.strip()[:80]}' in {file_path}",
                        "commit": commit[:7],
                    })

    # Persist the newest commit as last-scanned
    if state_path and commits:
        _write_last_scanned_commit(state_path, commits[0])

    return events
