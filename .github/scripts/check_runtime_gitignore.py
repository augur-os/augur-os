#!/usr/bin/env python3
"""
Check Runtime Gitignore Script

Pre-commit hook that ensures runtime folder contents are gitignored.
Runtime files (logs, temp, cache) should never be committed.

Usage:
    python3 check_runtime_gitignore.py
"""

import subprocess
import sys
from pathlib import Path
from src.config.paths import get_project_root, get_runtime_dir

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def is_gitignored(path: Path, git_root: Path) -> bool:
    """Check if a path is gitignored."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            cwd=git_root,
            capture_output=True,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_runtime_path():
    """Get runtime path from config or default."""
    try:
        from src.config.path_config import get_path_config

        config = get_path_config()
        return config.runtime.path, config.runtime.git_root
    except ImportError:
        # Fallback
        return get_runtime_dir(), get_project_root()


def check_runtime_gitignored() -> tuple[bool, list[Path]]:
    """
    Check if runtime folder is properly gitignored.

    Returns:
        Tuple of (all_ok, list_of_unignored_files)
    """
    runtime_path, git_root = get_runtime_path()

    if not runtime_path.exists():
        return True, []

    if not git_root:
        return True, []  # Can't check

    # Check if the runtime directory itself is gitignored
    if is_gitignored(runtime_path, git_root):
        return True, []

    # Check individual files
    unignored = []
    for file in runtime_path.rglob("*"):
        if file.is_file() and not is_gitignored(file, git_root):
            unignored.append(file)

    return len(unignored) == 0, unignored


def main():
    all_ok, unignored = check_runtime_gitignored()

    if all_ok:
        print("✅ Runtime folder is properly gitignored")
        return 0

    print("\n❌ Runtime files should be gitignored:")
    print("=" * 60)

    for file in unignored[:20]:  # Limit output
        print(f"  📄 {file}")

    if len(unignored) > 20:
        print(f"  ... and {len(unignored) - 20} more")

    print("\n💡 Add this to your .gitignore:")
    runtime_path, _ = get_runtime_path()
    print(f"   {runtime_path.name}/")

    print(f"\n⚠️  Found {len(unignored)} runtime files that should be gitignored")
    return 1


if __name__ == "__main__":
    sys.exit(main())
