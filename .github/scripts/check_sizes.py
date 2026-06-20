#!/usr/bin/env python3
"""
Check Sizes Script

Pre-commit hook that warns about large files being committed.
This is a warning-only check that doesn't block commits.

Usage:
    python3 check_sizes.py              # Check staged files
    python3 check_sizes.py file1 file2  # Check specific files
"""

import subprocess
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Default threshold (MB)
LARGE_FILE_THRESHOLD_MB = 50


def get_threshold_mb() -> float:
    """Get large file threshold from config."""
    try:
        from src.config.path_config import get_path_config

        config = get_path_config()
        return config.alerts.large_file_mb
    except ImportError:
        return LARGE_FILE_THRESHOLD_MB


def get_staged_files() -> list[Path]:
    """Get list of staged files from git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode == 0:
            return [PROJECT_ROOT / f for f in result.stdout.strip().split("\n") if f]
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return []


def format_size(bytes_size: int) -> str:
    """Format size in human-readable form."""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"


def check_file_sizes(files: list[Path], threshold_mb: float) -> list[tuple[Path, int]]:
    """
    Check files for size violations.

    Returns:
        List of (path, size_bytes) for files over threshold
    """
    large_files = []
    threshold_bytes = threshold_mb * 1024 * 1024

    for file in files:
        if not file.exists() or not file.is_file():
            continue

        try:
            size = file.stat().st_size
            if size > threshold_bytes:
                large_files.append((file, size))
        except OSError:
            pass

    return large_files


def main():
    # Get files to check
    if len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:]]
    else:
        files = get_staged_files()

    if not files:
        return 0

    threshold = get_threshold_mb()
    large_files = check_file_sizes(files, threshold)

    if not large_files:
        return 0

    # Warning only - don't block
    print(f"\n⚠️  Large files detected (>{threshold:.0f} MB):")
    print("=" * 60)

    for file, size in sorted(large_files, key=lambda x: x[1], reverse=True):
        try:
            rel_path = file.relative_to(PROJECT_ROOT)
        except ValueError:
            rel_path = file

        print(f"  📦 {rel_path}: {format_size(size)}")

    print("\n💡 Consider:")
    print("   - Using Git LFS for large binary files")
    print("   - Moving data files to the DATA folder")
    print("   - Adding to .gitignore if not needed in version control")

    # Return 0 - this is warning only
    return 0


if __name__ == "__main__":
    sys.exit(main())
