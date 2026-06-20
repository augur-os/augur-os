#!/usr/bin/env python3
"""
Pre-commit hook: Cleanup temporary files with memory preservation.

This hook:
1. Detects temporary files created during AI-assisted development
2. Saves a brief memory about what was worked on
3. Deletes the temporary files before commit

Temporary file patterns:
- scratch*.md, scratch*.py, scratch*.ts
- temp*.md, temp*.py, temp*.ts
- .claude-*, .cursor-*, .copilot-*
- *_backup.*, *_old.*, *_tmp.*
- CLAUDE_*.md, AI_*.md

Memory is saved to: get_memory_dir()/daily/YYYY-MM-DD.md (resolved from project.yaml)
"""

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Project root detection
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# Add shared config to path
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.config.paths import get_memory_dir
    MEMORY_DIR = get_memory_dir()
except ImportError:
    # Fallback: read vault path from project.yaml, never hardcode or write into repo
    _vault = None
    try:
        import yaml as _yaml
        _proj_yaml = PROJECT_ROOT / "project.yaml"
        if _proj_yaml.exists():
            _data = _yaml.safe_load(_proj_yaml.read_text(encoding="utf-8"))
            _vault_raw = (_data or {}).get("paths", {}).get("vault")
            if _vault_raw:
                _vault = Path(os.path.expanduser(_vault_raw)).resolve() / "memory"
    except Exception:
        pass
    MEMORY_DIR = _vault or (Path.home() / "Library" / "Application Support" / "Augur" / "state" / "memory")

# Temporary file patterns to detect and clean.
# Broad name-based patterns only apply at repo root so tracked/generated
# subtrees such as `.codex/prompts/` are not deleted by accident.
ROOT_ONLY_TEMP_PATTERNS = [
    # Scratch files (AI-generated during sessions)
    r"^scratch[_\-]?.*\.(md|py|ts|tsx|js|jsx|txt)$",
    r"^temp[_\-]?.*\.(md|py|ts|tsx|js|jsx|txt)$",
    r"^tmp[_\-]?.*\.(md|py|ts|tsx|js|jsx|txt)$",
    # AI tool markers
    r"^\.claude[-_].*",
    r"^\.cursor[-_].*",
    r"^\.copilot[-_].*",
    r"^CLAUDE_.*\.md$",
    r"^AI_.*\.md$",
    r"^claude[-_].*\.(md|txt)$",
    # Backup/old files
    r".*_backup\.(md|py|ts|tsx|js|jsx)$",
    r".*_old\.(md|py|ts|tsx|js|jsx)$",
    r".*_tmp\.(md|py|ts|tsx|js|jsx)$",
    # Draft/notes files
    r"^draft[_\-]?.*\.(md|py|ts|tsx)$",
    r"^notes[_\-]?.*\.md$",
    r"^TODO[_\-].*\.md$",
    # Test output files that shouldn't be committed
    r"^test_output.*\.(md|txt|json)$",
    r"^debug[_\-]?.*\.(md|txt|log)$",
]

ANYWHERE_TEMP_PATTERNS = [
    r"^\.DS_Store$",
    r".*\.bak$",
    r".*\.orig$",
    r".*\.log$",
    r".*\.pid$",
    r".*\.pyc$",
    r".*\.pyo$",
]

# Root-level junk directories that should never live in the repo.
ROOT_CLEAN_DIRS = {
    "build",
    "output",
    "tmp",
    "temp",
    "results",
    "exports",
    "scratch",
}

# Root-level binary artifacts commonly produced during dashboard/browser work.
ROOT_BINARY_TEMP_PATTERN = re.compile(
    r"^(tmp|screenshot|capture|debug|test-output|test_output)[\-_].*\.(png|jpg|jpeg|gif|bmp|webp|pdf)$",
    re.IGNORECASE,
)

# Directories to skip entirely during search
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    ".venv",
    "venv",
    ".tox",
    "coverage",
    "htmlcov",
}

# Directories to clean entirely (remove with all contents)
CLEAN_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage_html",
}

# Compile patterns for efficiency
ROOT_ONLY_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in ROOT_ONLY_TEMP_PATTERNS]
ANYWHERE_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in ANYWHERE_TEMP_PATTERNS]
_TRACKED_PATH_CACHE: dict[Path, set[str]] = {}


def is_temp_file(filename: str, *, at_root: bool) -> bool:
    """Check if a filename matches temporary file patterns."""
    patterns = list(ANYWHERE_COMPILED_PATTERNS)
    if at_root:
        patterns.extend(ROOT_ONLY_COMPILED_PATTERNS)
    for pattern in patterns:
        if pattern.match(filename):
            return True
    return False


def _get_tracked_paths(root_dir: Path) -> set[str]:
    """Return the cached set of git-tracked repo-relative paths."""
    git_dir = root_dir / ".git"
    if not git_dir.exists():
        return set()

    cached = _TRACKED_PATH_CACHE.get(root_dir)
    if cached is not None:
        return cached

    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root_dir,
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return set()

    tracked = {
        entry.decode("utf-8", errors="ignore")
        for entry in result.stdout.split(b"\0")
        if entry
    }
    _TRACKED_PATH_CACHE[root_dir] = tracked
    return tracked


def is_git_tracked(path: Path, root_dir: Path) -> bool:
    """Return whether a file or directory is tracked by git."""
    try:
        rel_path = path.relative_to(root_dir)
    except ValueError:
        return False

    rel_str = str(rel_path)
    tracked = _get_tracked_paths(root_dir)
    if path.is_dir():
        prefix = f"{rel_str}/"
        return any(item == rel_str or item.startswith(prefix) for item in tracked)
    return rel_str in tracked


def find_temp_files(root_dir: Path) -> tuple[list[Path], list[Path]]:
    """Find all temporary files and directories in the project.

    Returns:
        Tuple of (temp_files, temp_dirs)
    """
    temp_files = []
    temp_dirs = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        current_dir = Path(dirpath)

        # Check for directories to clean entirely
        dirs_to_remove = []
        if current_dir == root_dir:
            for dirname in dirnames:
                dirpath = current_dir / dirname
                if dirname in ROOT_CLEAN_DIRS and not is_git_tracked(dirpath, root_dir):
                    temp_dirs.append(dirpath)
                    dirs_to_remove.append(dirname)
        for dirname in dirnames:
            dirpath = current_dir / dirname
            if dirname in CLEAN_DIRS and not is_git_tracked(dirpath, root_dir):
                temp_dirs.append(dirpath)
                dirs_to_remove.append(dirname)

        # Skip ignored directories and already-marked-for-removal dirs
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and d not in dirs_to_remove
        ]

        for filename in filenames:
            filepath = current_dir / filename
            if is_git_tracked(filepath, root_dir):
                continue
            if current_dir == root_dir and ROOT_BINARY_TEMP_PATTERN.match(filename):
                temp_files.append(filepath)
                continue
            if is_temp_file(filename, at_root=current_dir == root_dir):
                temp_files.append(filepath)

    return temp_files, temp_dirs


def get_file_summary(filepath: Path, max_lines: int = 5) -> str:
    """Get a brief summary of file contents."""
    try:
        content = filepath.read_text(errors="ignore")
        lines = content.split("\n")[:max_lines]

        # Extract meaningful content (skip empty lines, get first non-empty)
        meaningful_lines = [line.strip() for line in lines if line.strip()]

        if not meaningful_lines:
            return "(empty file)"

        # Return first meaningful line, truncated
        first_line = meaningful_lines[0][:100]
        if len(meaningful_lines) > 1:
            return f"{first_line}... (+{len(meaningful_lines)-1} more lines)"
        return first_line

    except Exception as e:
        return f"(could not read: {e})"


def save_cleanup_memory(cleaned_files: list[dict]) -> Path:
    """Save memory about cleaned files to daily log."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    daily_dir = MEMORY_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now()
    daily_file = daily_dir / f"{today.strftime('%Y-%m-%d')}.md"

    # Create or append to daily log
    if not daily_file.exists():
        header = f"# Session Log: {today.strftime('%Y-%m-%d')}\n\n"
        daily_file.write_text(header)

    # Format the cleanup event
    time_str = today.strftime("%H:%M")
    event_lines = [
        f"\n## {time_str} - Pre-Commit Cleanup\n",
        "**Event**: Temporary files cleaned before commit\n",
        f"**Files cleaned**: {len(cleaned_files)}\n",
        "\n### Cleaned Files:\n",
    ]

    for file_info in cleaned_files:
        event_lines.append(
            f"- `{file_info['path']}`: {file_info['summary']}\n"
        )

    event_lines.append("\n")

    # Append to daily log
    with open(daily_file, "a") as f:
        f.writelines(event_lines)

    return daily_file


def cleanup_temp_files(dry_run: bool = False) -> tuple[int, list[dict]]:
    """
    Find and clean temporary files and directories.

    Args:
        dry_run: If True, only report files without deleting

    Returns:
        Tuple of (items_cleaned, item_info_list)
    """
    import shutil

    temp_files, temp_dirs = find_temp_files(PROJECT_ROOT)

    if not temp_files and not temp_dirs:
        return 0, []

    cleaned = []

    # Clean files
    for filepath in temp_files:
        rel_path = filepath.relative_to(PROJECT_ROOT)
        summary = get_file_summary(filepath)

        file_info = {
            "path": str(rel_path),
            "type": "file",
            "summary": summary,
            "size": filepath.stat().st_size if filepath.exists() else 0,
        }

        if not dry_run:
            try:
                filepath.unlink()
                file_info["deleted"] = True
            except Exception as e:
                file_info["deleted"] = False
                file_info["error"] = str(e)
        else:
            file_info["deleted"] = False
            file_info["dry_run"] = True

        cleaned.append(file_info)

    # Clean directories
    for dirpath in temp_dirs:
        rel_path = dirpath.relative_to(PROJECT_ROOT)

        # Count files in directory
        try:
            file_count = sum(1 for _ in dirpath.rglob("*") if _.is_file())
            size = sum(f.stat().st_size for f in dirpath.rglob("*") if f.is_file())
        except Exception:
            file_count = 0
            size = 0

        dir_info = {
            "path": str(rel_path),
            "type": "directory",
            "summary": f"({file_count} files)",
            "size": size,
        }

        if not dry_run:
            try:
                shutil.rmtree(dirpath)
                dir_info["deleted"] = True
            except Exception as e:
                dir_info["deleted"] = False
                dir_info["error"] = str(e)
        else:
            dir_info["deleted"] = False
            dir_info["dry_run"] = True

        cleaned.append(dir_info)

    return len(cleaned), cleaned


def main():
    """Main entry point for pre-commit hook."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Clean up temporary files before commit"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned without deleting",
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Skip saving memory about cleaned files",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output",
    )

    args = parser.parse_args()

    # Find and clean temp files
    count, cleaned_files = cleanup_temp_files(dry_run=args.dry_run)

    if count == 0:
        if not args.quiet:
            print("No temporary files to clean.")
        return 0

    # Report what was found/cleaned
    if not args.quiet:
        action = "Would clean" if args.dry_run else "Cleaned"
        print(f"\n{action} {count} temporary file(s):")
        for file_info in cleaned_files:
            status = "[DRY RUN]" if args.dry_run else "[DELETED]"
            if file_info.get("error"):
                status = f"[ERROR: {file_info['error']}]"
            print(f"  {status} {file_info['path']}")
            print(f"          Summary: {file_info['summary'][:60]}...")

    # Save memory about cleanup
    if not args.dry_run and not args.no_memory:
        daily_file = save_cleanup_memory(cleaned_files)
        if not args.quiet:
            print(f"\nMemory saved to: {daily_file}")

    # Return success (pre-commit hooks should return 0 for pass)
    return 0


if __name__ == "__main__":
    sys.exit(main())
