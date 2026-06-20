#!/usr/bin/env python3
"""
CI Path Cleanup Script

Runs as part of CI to:
1. Validate all files are in correct category paths
2. Identify and clean stale runtime data
3. Detect misplaced files and suggest fixes
4. Check for size bloat

Usage:
    python src/lib/scripts/cleanup_paths.py --check        # Dry run, report issues
    python src/lib/scripts/cleanup_paths.py --fix         # Auto-fix what's possible
    python src/lib/scripts/cleanup_paths.py --clean-stale # Remove old runtime data
"""

import argparse
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from subprocess import CompletedProcess, SubprocessError, run as subprocess_run  # nosec B404
from typing import Any


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Force UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Add project root to path for imports
from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)
try:
    from src.config.paths import get_project_root
except ImportError:
    get_project_root = lambda: PROJECT_ROOT  # noqa: E731

# Stale file thresholds
STALE_LOG_DAYS = 7
STALE_CACHE_DAYS = 3
STALE_TEMP_HOURS = 24


def _resolve_command(command: list[str]) -> list[str]:
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


def _run_command(command: list[str], **kwargs: Any) -> CompletedProcess[str]:
    return subprocess_run(_resolve_command(command), **kwargs)  # nosec B603


# Directories whose contents are never "misplaced" by the core/data classifier.
# Build/vendor output is noise; skill dirs and in-repo ADRs are intentionally
# decentralized (CLAUDE.md rule 2, ADR-601 skill co-location, ADR-811 ADRs in-repo).
PLACEMENT_EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


# Top-level repo dirs that hold authoritative framework config/code, not user
# data. The legacy "data-shaped YAML -> move to vault" heuristic must not flag
# these: per CLAUDE.md rule 4 config lives in ``config/``, and ``apps/`` is
# framework dashboard code/assets (including shipped seed templates).
PLACEMENT_FRAMEWORK_DIRS = {
    "config",
    "apps",
}


def _is_decentralized_path(path: Path) -> bool:
    """Files that legitimately co-locate inside skill dirs or in-repo ADR dirs.

    Per CLAUDE.md rule 2 + ADR-601/ADR-811, skill-owned code, config, data, seeds,
    and assets live INSIDE ``capabilities/skills/{skill}/`` (both the shared
    project-brain tree and the private vault), and ADRs live in-repo under
    ``decisions/``. The legacy core/data classifier predates this layout, so it
    must not flag these locations as misplaced.
    """
    parts = path.parts
    for idx, part in enumerate(parts):
        if part == "skills" and idx > 0 and parts[idx - 1] == "capabilities":
            return True
        if part == "decisions":
            return True
    return False


def _is_framework_config_path(path: Path, core_root: Path) -> bool:
    """True when ``path`` lives in an authoritative framework dir under core root.

    Framework config (``config/``) and dashboard app code/assets (``apps/``)
    are not candidate user-data; their data-shaped YAML (system config, seed
    templates, questionnaires) is intentional product content, not misplaced
    vault data.
    """
    try:
        rel = path.resolve().relative_to(core_root.resolve())
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0] in PLACEMENT_FRAMEWORK_DIRS


def _skip_for_placement(path: Path) -> bool:
    """True when ``path`` should be ignored by the placement classifier."""
    if any(part in PLACEMENT_EXCLUDED_DIRS for part in path.parts):
        return True
    return _is_decentralized_path(path)


@dataclass
class PlacementIssue:
    file: Path
    current_category: str
    expected_category: str
    reason: str


@dataclass
class WrongPlacement:
    file: Path
    current: str
    should_be: str
    auto_fixable: bool = False
    fix_path: Path | None = None
    suggestion: str = ""


@dataclass
class SizeAlert:
    category: str
    level: str  # 'warning', 'critical', 'large_file'
    size_mb: float


@dataclass
class CleanupReport:
    files: list[tuple[Path, str, str]] = field(default_factory=list)
    total_size: int = 0

    def add(self, path: Path, category: str, reason: str):
        try:
            self.total_size += path.stat().st_size
        except OSError:
            pass
        self.files.append((path, category, reason))

    @property
    def total(self) -> int:
        return len(self.files)

    @property
    def total_size_mb(self) -> float:
        return self.total_size / (1024 * 1024)


def is_user_data_file(path: Path) -> bool:
    """Detect if file contains user data vs code config."""
    if not path.exists() or not path.is_file():
        return False

    if path.suffix not in [".yaml", ".json"]:
        return False

    try:
        content = path.read_text(encoding="utf-8")
        data_patterns = [
            r"created_at:",
            r"updated_at:",
            r"user_id:",
            r"entries:",
            r"^\s*-\s+id:",
            r"last_modified:",
            r"timestamp:",
        ]
        return any(re.search(p, content, re.MULTILINE) for p in data_patterns)
    except (OSError, UnicodeDecodeError):
        return False


def is_script_file(path: Path) -> bool:
    """Check if a Python file is a script (vs a module)."""
    if path.suffix != ".py":
        return False

    try:
        content = path.read_text(encoding="utf-8")
        return '__name__ == "__main__"' in content or "__name__ == '__main__'" in content
    except (OSError, UnicodeDecodeError):
        return False


def is_gitignored(path: Path, git_root: Path) -> bool:
    """Check if a path is gitignored."""
    if not git_root or not path.exists():
        return False

    try:
        result = _run_command(
            ["git", "check-ignore", "-q", str(path)],
            cwd=git_root,
            capture_output=True,
        )
        return result.returncode == 0
    except (SubprocessError, FileNotFoundError):
        return False


def calculate_directory_size(path: Path) -> float:
    """Calculate directory size in MB."""
    if not path.exists():
        return 0.0

    exclude = [".git", "node_modules", ".next", "__pycache__", ".venv"]
    total = 0

    try:
        for entry in path.rglob("*"):
            if any(exc in entry.parts for exc in exclude):
                continue
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass

    return total / (1024 * 1024)


def clean_stale_runtime(runtime_path: Path, dry_run: bool = True) -> CleanupReport:
    """Remove stale files from runtime folder."""
    report = CleanupReport()

    if not runtime_path.exists():
        return report

    now = datetime.now()

    # Clean old logs
    for log in runtime_path.glob("**/*.log"):
        try:
            age = now - datetime.fromtimestamp(log.stat().st_mtime)
            if age > timedelta(days=STALE_LOG_DAYS):
                report.add(log, "stale_log", f"{age.days} days old")
                if not dry_run:
                    log.unlink()
        except OSError:
            pass

    # Clean old cache
    for cache_dir in runtime_path.glob("**/cache"):
        if cache_dir.is_dir():
            for file in cache_dir.rglob("*"):
                if file.is_file():
                    try:
                        age = now - datetime.fromtimestamp(file.stat().st_mtime)
                        if age > timedelta(days=STALE_CACHE_DAYS):
                            report.add(file, "stale_cache", f"{age.days} days old")
                            if not dry_run:
                                file.unlink()
                    except OSError:
                        pass

    # Clean temp files
    for temp in runtime_path.glob("**/*.tmp"):
        try:
            age = now - datetime.fromtimestamp(temp.stat().st_mtime)
            if age > timedelta(hours=STALE_TEMP_HOURS):
                report.add(temp, "stale_temp", f"{age.total_seconds()/3600:.1f} hours old")
                if not dry_run:
                    temp.unlink()
        except OSError:
            pass

    return report


def detect_wrong_placements(config) -> list[WrongPlacement]:
    """Detect files in wrong category folders."""
    issues = []

    # Check for data files in CORE
    if config.core.path.exists():
        for yaml_file in config.core.path.rglob("*.yaml"):
            if _skip_for_placement(yaml_file) or _is_framework_config_path(yaml_file, config.core.path):
                continue
            # Skip known config files
            if yaml_file.name in [
                "dependencies.yaml",
                ".pre-commit-config.yaml",
                "augur.yaml",
                "SKILL.md",
            ]:
                continue

            if is_user_data_file(yaml_file):
                try:
                    rel_path = yaml_file.relative_to(config.core.path)
                    issues.append(
                        WrongPlacement(
                            file=yaml_file,
                            current="core",
                            should_be="data",
                            auto_fixable=True,
                            fix_path=config.data.path / rel_path,
                        )
                    )
                except ValueError:
                    pass

    # Check for runtime files not gitignored
    if config.runtime.path.exists() and config.runtime.git_root:
        for runtime_file in config.runtime.path.rglob("*"):
            if runtime_file.is_file() and not _skip_for_placement(runtime_file):
                if not is_gitignored(runtime_file, config.runtime.git_root):
                    issues.append(
                        WrongPlacement(
                            file=runtime_file,
                            current="runtime",
                            should_be="runtime (gitignored)",
                            auto_fixable=False,
                            suggestion="Add to .gitignore",
                        )
                    )

    # Check for code files in DATA (except scripts)
    if config.data.path.exists():
        for py_file in config.data.path.rglob("*.py"):
            if _skip_for_placement(py_file):
                continue
            if not is_script_file(py_file):
                issues.append(
                    WrongPlacement(
                        file=py_file,
                        current="data",
                        should_be="core or plugins",
                        auto_fixable=False,
                        suggestion="Move to appropriate code location",
                    )
                )

    return issues


def check_size_bloat(config) -> list[SizeAlert]:
    """Check for folders exceeding size thresholds."""
    alerts = []

    for category in config.categories:
        if not category.path.exists():
            continue

        size_mb = calculate_directory_size(category.path)

        if size_mb > config.alerts.critical_mb:
            alerts.append(SizeAlert(category.id, "critical", size_mb))
        elif size_mb > config.alerts.warning_mb:
            alerts.append(SizeAlert(category.id, "warning", size_mb))

        # Check for large individual files
        for file in category.path.rglob("*"):
            if file.is_file():
                try:
                    file_mb = file.stat().st_size / (1024 * 1024)
                    if file_mb > config.alerts.large_file_mb:
                        rel_path = file.relative_to(category.path)
                        alerts.append(SizeAlert(f"{category.id}/{rel_path}", "large_file", file_mb))
                except (OSError, ValueError):
                    pass

    return alerts


def main():
    parser = argparse.ArgumentParser(description="CI Path Cleanup")
    parser.add_argument("--check", action="store_true", help="Check for issues (dry run)")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    parser.add_argument("--clean-stale", action="store_true", help="Clean stale runtime data")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # Try to load config
    try:
        from src.config.path_config import get_path_config

        config = get_path_config()
    except ImportError as e:
        _out(f"⚠️  Could not load path config: {e}")
        _out("   Running in limited mode.")
        return 0

    exit_code = 0

    # 1. Check placements
    _out("Checking file placements...")
    placement_issues = detect_wrong_placements(config)
    if placement_issues:
        _out(f"Found {len(placement_issues)} placement issues:")
        for issue in placement_issues:
            _out(f"  {issue.file}: {issue.current} -> {issue.should_be}")
            if args.fix and issue.auto_fixable and issue.fix_path:
                try:
                    issue.fix_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(issue.file), str(issue.fix_path))
                    _out(f"    ✓ Moved to {issue.fix_path}")
                except OSError as e:
                    _out(f"    ✗ Failed to move: {e}")
            elif issue.suggestion:
                _out(f"    💡 {issue.suggestion}")
        exit_code = 1
    else:
        _out("  ✓ No placement issues found")

    # 2. Clean stale runtime
    if args.clean_stale or args.fix:
        _out("\nCleaning stale runtime data...")
        report = clean_stale_runtime(config.runtime.path, dry_run=not args.fix)
        action = "would be" if not args.fix else ""
        _out(f"  {report.total} files {action} removed")
        _out(f"  {report.total_size_mb:.1f} MB {action} freed")

    # 3. Check size bloat
    _out("\nChecking size thresholds...")
    config.refresh_sizes()
    alerts = check_size_bloat(config)

    if alerts:
        for alert in alerts:
            emoji = "🔴" if alert.level == "critical" else "🟡" if alert.level == "warning" else "📁"
            _out(f"  {emoji} {alert.category}: {alert.size_mb:.1f} MB")
            if alert.level in ["critical", "warning"]:
                exit_code = 1
    else:
        _out("  ✓ All sizes within thresholds")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
