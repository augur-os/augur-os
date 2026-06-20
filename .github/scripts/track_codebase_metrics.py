#!/usr/bin/env python3
"""
Codebase Metrics Tracker

Tracks the growth of the core codebase by counting files, folders, and lines of code.
Excludes plugins, data, and auto-generated files.

Usage:
    python3 .github/scripts/track_codebase_metrics.py [--json] [--save]

Options:
    --json    Output as JSON (for CI integration)
    --save    Save metrics to the persistent state metrics directory

Output includes:
    - Files, folders, and lines of code by category
    - Comparison with previous run (if --save used before)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_runtime_dir


class CategoryMetrics(TypedDict):
    files: int
    folders: int
    lines: int


class Metrics(TypedDict):
    timestamp: str
    total: CategoryMetrics
    categories: dict[str, CategoryMetrics]


# Directories to exclude (auto-generated, dependencies, runtime)
EXCLUDED_DIRS = {
    '.git',
    '.venv',
    '.venv-test',
    'node_modules',
    '.next',
    '__pycache__',
    '.pytest_cache',
    '.mypy_cache',
    '.ruff_cache',
    '.coverage',
    'coverage',
    'dist',
    'build',
    '.egg-info',
    'htmlcov',
    # Plugin directories (tracked separately)
    'plugins',
    # Legacy data monorepo path
    'data',
}

# File patterns to exclude (auto-generated files)
EXCLUDED_FILE_PATTERNS = {
    '.pyc',
    '.pyo',
    '.so',
    '.egg',
    '.whl',
    '.DS_Store',
    'package-lock.json',
    'yarn.lock',
    'pnpm-lock.yaml',
    'uv.lock',
    '.tsbuildinfo',
}

# Files that are auto-generated (by name)
EXCLUDED_FILES = {
    'generated-registry.ts',  # Tab registry
    'next-env.d.ts',
    'lists.ts',  # Generated list registry (7000+ lines)
}

# Directories that contain only auto-generated files
EXCLUDED_GENERATED_DIRS = {
    'generated',  # lib/generated/
}

# Categories to track with their paths
CATEGORIES = {
    'apps/dashboard': 'apps/dashboard',
    'src/config': 'src/config',
    'shared': 'shared',
    'packages': 'packages',
    'docs': 'docs',
    'tests': 'tests',
    '.github': '.github',
    'config': 'config',
    'root_files': None,  # Special: root-level files only
}


def get_project_root() -> Path:
    """Get the project root directory."""
    return PROJECT_ROOT


def should_exclude_dir(dir_name: str) -> bool:
    """Check if a directory should be excluded."""
    return (dir_name in EXCLUDED_DIRS or
            dir_name in EXCLUDED_GENERATED_DIRS or
            dir_name.startswith('.'))


def should_exclude_file(file_path: Path) -> bool:
    """Check if a file should be excluded."""
    name = file_path.name

    # Check exact file names
    if name in EXCLUDED_FILES:
        return True

    # Check patterns
    for pattern in EXCLUDED_FILE_PATTERNS:
        if name.endswith(pattern):
            return True

    return False


def count_lines(file_path: Path) -> int:
    """Count lines in a file, handling encoding errors."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for _ in f)
    except (OSError, IOError):
        return 0


def collect_metrics(root: Path, category_path: str | None) -> CategoryMetrics:
    """Collect metrics for a category."""
    files = 0
    folders = 0
    lines = 0

    if category_path is None:
        # Root files only
        for item in root.iterdir():
            if item.is_file() and not should_exclude_file(item):
                files += 1
                lines += count_lines(item)
        return {'files': files, 'folders': 0, 'lines': lines}

    target_dir = root / category_path
    if not target_dir.exists():
        return {'files': 0, 'folders': 0, 'lines': 0}

    for dirpath, dirnames, filenames in os.walk(target_dir):
        # Filter out excluded directories
        dirnames[:] = [d for d in dirnames if not should_exclude_dir(d)]

        folders += len(dirnames)

        for filename in filenames:
            file_path = Path(dirpath) / filename
            if not should_exclude_file(file_path):
                files += 1
                lines += count_lines(file_path)

    return {'files': files, 'folders': folders, 'lines': lines}


def count_test_files(root: Path) -> dict[str, int]:
    """Count test files by type."""
    python_tests = 0
    ts_tests = 0

    # Count Python test files
    for test_dir in [root / 'tests', root / 'plugins']:
        if test_dir.exists():
            for f in test_dir.rglob('test_*.py'):
                if '.venv' not in str(f) and 'node_modules' not in str(f):
                    python_tests += 1

    # Count TypeScript test files
    for test_dir in [root / 'tests']:
        if test_dir.exists():
            for pattern in ['**/*.test.ts', '**/*.test.tsx']:
                for f in test_dir.rglob(pattern.replace('**/', '')):
                    if 'node_modules' not in str(f):
                        ts_tests += 1

    return {'python': python_tests, 'typescript': ts_tests, 'total': python_tests + ts_tests}


def collect_all_metrics(root: Path) -> Metrics:
    """Collect metrics for all categories."""
    categories: dict[str, CategoryMetrics] = {}
    total_files = 0
    total_folders = 0
    total_lines = 0

    for name, path in CATEGORIES.items():
        metrics = collect_metrics(root, path)
        categories[name] = metrics
        total_files += metrics['files']
        total_folders += metrics['folders']
        total_lines += metrics['lines']

    result: Metrics = {
        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'total': {
            'files': total_files,
            'folders': total_folders,
            'lines': total_lines,
        },
        'categories': categories,
    }

    # Add test counts
    result['test_counts'] = count_test_files(root)  # type: ignore[typeddict-unknown-key]

    return result


def load_previous_metrics(metrics_file: Path) -> Metrics | None:
    """Load previous metrics for comparison."""
    if not metrics_file.exists():
        return None
    try:
        with open(metrics_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_metrics(metrics: Metrics, metrics_file: Path) -> None:
    """Save metrics to file."""
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)


def format_delta(current: int, previous: int | None) -> str:
    """Format a delta value."""
    if previous is None:
        return ''
    delta = current - previous
    if delta == 0:
        return ''
    sign = '+' if delta > 0 else ''
    return f' ({sign}{delta})'


def print_table(metrics: Metrics, previous: Metrics | None = None) -> None:
    """Print metrics as a formatted table."""
    print("\n" + "=" * 70)
    print("CODEBASE METRICS")
    print(f"Generated: {metrics['timestamp']}")
    print("=" * 70)

    prev_cats = previous['categories'] if previous else {}

    # Header
    print(f"\n{'Category':<25} {'Files':>10} {'Folders':>10} {'Lines':>12}")
    print("-" * 60)

    # Categories
    for name, cat_metrics in metrics['categories'].items():
        prev = prev_cats.get(name)

        files_delta = format_delta(cat_metrics['files'], prev['files'] if prev else None)
        folders_delta = format_delta(cat_metrics['folders'], prev['folders'] if prev else None)
        lines_delta = format_delta(cat_metrics['lines'], prev['lines'] if prev else None)

        print(f"{name:<25} {cat_metrics['files']:>10}{files_delta:<8} "
              f"{cat_metrics['folders']:>10}{folders_delta:<8} "
              f"{cat_metrics['lines']:>10}{lines_delta}")

    # Total
    print("-" * 60)
    total = metrics['total']
    prev_total = previous['total'] if previous else None

    files_delta = format_delta(total['files'], prev_total['files'] if prev_total else None)
    folders_delta = format_delta(total['folders'], prev_total['folders'] if prev_total else None)
    lines_delta = format_delta(total['lines'], prev_total['lines'] if prev_total else None)

    print(f"{'TOTAL':<25} {total['files']:>10}{files_delta:<8} "
          f"{total['folders']:>10}{folders_delta:<8} "
          f"{total['lines']:>10}{lines_delta}")

    print("\n")


def main() -> int:
    """Main entry point."""
    root = get_project_root()
    metrics_file = get_runtime_dir() / 'metrics' / 'codebase_metrics.json'

    # Parse arguments
    output_json = '--json' in sys.argv
    save = '--save' in sys.argv

    # Collect metrics
    metrics = collect_all_metrics(root)

    # Load previous for comparison
    previous = load_previous_metrics(metrics_file) if save or metrics_file.exists() else None

    if output_json:
        print(json.dumps(metrics, indent=2))
    else:
        print_table(metrics, previous)

    # Save if requested
    if save:
        save_metrics(metrics, metrics_file)
        if not output_json:
            print(f"Metrics saved to: {metrics_file}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
