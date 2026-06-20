#!/usr/bin/env python3
"""
Repo hygiene validator.

Checks:
- Code repo: no data artifacts (audits, chain-executions, .backups), and no
  unexpected JSON artifacts outside allowlisted config files.
- Code repo: no references to deprecated data paths.
- Data repo: no tracked or staged runtime IPC/logs.
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path
from typing import Iterable

CODE_FORBIDDEN_GLOBS = (
    "**/chain-executions/**",
    "**/audits/**",
    "**/.backups/**",
)

DATA_FORBIDDEN_GLOBS = (
    "logs/**",
    "ipc/**",
)

JSON_ALLOW_GLOBS = (
    "**/package.json",
    "**/package-lock.json",
    "**/tsconfig*.json",
    "**/.eslintrc.json",
    "**/config/*.json",
    "**/data-template/*.json",
    "**/test_discovery_data/**/*.json",
    "**/_dev/**/*.json",
    "**/.agent/chains/_schema.json",
)

JSON_ALLOW_PATHS = {
    "package.json",
    "config/mcp_config.json",
    ".agent/chains/_schema.json",
    # Note: plugins have been migrated to augur repo
}

FORBIDDEN_PATH_SNIPPETS = (
    "~/augur",
    f"{str(Path.home())}/augur",
)

SNIPPET_EXCLUDE_PATHS = {
    ".github/scripts/audit_git_hygiene.py",
}


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git failed")
    return result.stdout


def parse_zlist(raw: str) -> list[str]:
    if not raw:
        return []
    items = raw.split("\0")
    return [item for item in items if item]


def collect_paths(repo_root: Path) -> tuple[set[str], set[str]]:
    tracked = set(parse_zlist(run_git(["ls-files", "-z"], repo_root)))
    staged = set(parse_zlist(run_git(["diff", "--name-only", "--cached", "-z"], repo_root)))
    unstaged = set(parse_zlist(run_git(["diff", "--name-only", "-z"], repo_root)))
    untracked = set(parse_zlist(run_git(["ls-files", "--others", "--exclude-standard", "-z"], repo_root)))
    all_paths = tracked | staged | unstaged | untracked
    return all_paths, tracked


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def is_allowed_json(path: str) -> bool:
    if path in JSON_ALLOW_PATHS:
        return True
    return matches_any(path, JSON_ALLOW_GLOBS)


def find_forbidden_paths(paths: Iterable[str], patterns: Iterable[str]) -> list[str]:
    return sorted({path for path in paths if matches_any(path, patterns)})


def find_forbidden_json(paths: Iterable[str]) -> list[str]:
    offenders = []
    for path in paths:
        if not path.endswith(".json"):
            continue
        if is_allowed_json(path):
            continue
        offenders.append(path)
    return sorted(set(offenders))


def find_forbidden_path_snippets(repo_root: Path, tracked: Iterable[str]) -> list[str]:
    offenders = []
    for rel_path in tracked:
        if rel_path in SNIPPET_EXCLUDE_PATHS:
            continue
        # Exclude archive
        if ".agent/archive" in rel_path:
            continue
        file_path = repo_root / rel_path
        if not file_path.is_file():
            continue
        try:
            data = file_path.read_bytes()
        except Exception:
            continue
        if b"\0" in data:
            continue
        if len(data) > 1_000_000:
            continue
        text = data.decode("utf-8", errors="ignore")
        for snippet in FORBIDDEN_PATH_SNIPPETS:
            if snippet in text:
                offenders.append(rel_path)
                break
    return sorted(set(offenders))


def validate_code_repo(repo_root: Path) -> int:
    all_paths, tracked = collect_paths(repo_root)
    errors: list[str] = []

    forbidden = find_forbidden_paths(all_paths, CODE_FORBIDDEN_GLOBS)
    if forbidden:
        errors.append("Data artifact paths detected in code repo:")
        errors.extend(f"  - {path}" for path in forbidden)

    json_offenders = find_forbidden_json(all_paths)
    if json_offenders:
        errors.append("Unexpected JSON artifacts detected in code repo:")
        errors.extend(f"  - {path}" for path in json_offenders)

    path_snippets = find_forbidden_path_snippets(repo_root, tracked)
    if path_snippets:
        errors.append("Forbidden data path references detected in code repo:")
        errors.extend(f"  - {path}" for path in path_snippets)

    if errors:
        print("\n".join(errors))
        return 1
    return 0


def validate_data_repo(repo_root: Path) -> int:
    all_paths, _ = collect_paths(repo_root)
    forbidden = find_forbidden_paths(all_paths, DATA_FORBIDDEN_GLOBS)
    if forbidden:
        print("Runtime IPC/log files should not be staged or tracked in data repo:")
        for path in forbidden:
            print(f"  - {path}")
        return 1
    return 0


def infer_repo_type(repo_root: Path) -> str:
    if (repo_root / "packages").exists():
        return "code"
    if (repo_root / "factory").exists():
        return "data"
    raise RuntimeError("Unable to infer repo type; pass --repo-type explicitly.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repo state for data hygiene.")
    parser.add_argument("--repo-type", choices=["auto", "code", "data"], default="auto")
    parser.add_argument("--repo-root", default=".", help="Repository root to validate.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    repo_type = args.repo_type
    if repo_type == "auto":
        repo_type = infer_repo_type(repo_root)

    if repo_type == "code":
        return validate_code_repo(repo_root)
    if repo_type == "data":
        return validate_data_repo(repo_root)

    raise RuntimeError(f"Unknown repo type: {repo_type}")


if __name__ == "__main__":
    sys.exit(main())
