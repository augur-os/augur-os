#!/usr/bin/env python3
"""
Skill Maintenance Process for Augur.

Performs routine maintenance:
- Log rotation
- Cache cleanup
- Stale file detection
- Skill health checks
"""


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
import sys
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from src.config.paths import get_project_root


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

MAX_LOG_AGE_DAYS = 30
MAX_CACHE_SIZE_MB = 100
MAX_BACKUP_AGE_DAYS = 7

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def get_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def get_data_dir() -> Path:
    paths = [
        get_project_root(),
        get_project_root(),
    ]
    for p in paths:
        if p.exists():
            return p
    return paths[0]


def get_size_mb(path: Path) -> float:
    total = 0
    if path.is_file():
        return path.stat().st_size / (1024 * 1024)
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total / (1024 * 1024)


# ═══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE TASKS
# ═══════════════════════════════════════════════════════════════════════════════


def rotate_logs(data_dir: Path) -> dict[str, Any]:
    """Rotate old log files."""
    result = {"rotated": 0, "freed_mb": 0.0}
    cutoff = datetime.now() - timedelta(days=MAX_LOG_AGE_DAYS)

    log_patterns = ["*.log", "**/*.log", "**/logs/*.log"]

    for pattern in log_patterns:
        for log_file in data_dir.glob(pattern):
            if log_file.is_file():
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff:
                    size = log_file.stat().st_size / (1024 * 1024)
                    log_file.unlink()
                    result["rotated"] += 1
                    result["freed_mb"] += size

    return result


def cleanup_cache(repo_root: Path) -> dict[str, Any]:
    """Clean up cache directories."""
    result = {"cleaned": 0, "freed_mb": 0.0}

    cache_dirs = [
        repo_root / ".pytest_cache",
        repo_root / ".mypy_cache",
        repo_root / "__pycache__",
    ]

    for cache_dir in cache_dirs:
        if cache_dir.exists():
            size = get_size_mb(cache_dir)
            if size > MAX_CACHE_SIZE_MB:
                shutil.rmtree(cache_dir)
                result["cleaned"] += 1
                result["freed_mb"] += size

    # Recursively clean __pycache__
    for pycache in repo_root.rglob("__pycache__"):
        if pycache.is_dir():
            size = get_size_mb(pycache)
            shutil.rmtree(pycache)
            result["cleaned"] += 1
            result["freed_mb"] += size

    return result


def cleanup_backups(data_dir: Path) -> dict[str, Any]:
    """Clean old backups."""
    result = {"cleaned": 0, "freed_mb": 0.0}
    cutoff = datetime.now() - timedelta(days=MAX_BACKUP_AGE_DAYS)

    backup_dirs = list(data_dir.rglob("backups"))

    for backup_dir in backup_dirs:
        if backup_dir.is_dir():
            for backup in backup_dir.iterdir():
                if backup.is_file():
                    mtime = datetime.fromtimestamp(backup.stat().st_mtime)
                    if mtime < cutoff:
                        size = backup.stat().st_size / (1024 * 1024)
                        backup.unlink()
                        result["cleaned"] += 1
                        result["freed_mb"] += size

    return result


def check_skill_health(repo_root: Path) -> dict[str, Any]:
    """Check health of all skills."""
    result = {"total": 0, "healthy": 0, "issues": []}

    skill_dirs = [
        repo_root / "plugins" / "factory",
        repo_root / "plugins" / "horizontal",
        repo_root / "plugins" / "vertical",
    ]

    for skill_dir in skill_dirs:
        if not skill_dir.exists():
            continue

        for skill_path in skill_dir.iterdir():
            if not skill_path.is_dir():
                continue

            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                continue

            result["total"] += 1
            issues = []

            # Check for required files
            if not (skill_path / "augur" / "version.yaml").exists():
                issues.append("missing augur/version.yaml")

            # Check SKILL.md size (should be reasonable)
            size = skill_md.stat().st_size
            if size < 100:
                issues.append("SKILL.md too small")
            elif size > 20000:
                issues.append("SKILL.md too large (optimize tokens)")

            if issues:
                result["issues"].append(
                    {
                        "skill": skill_path.name,
                        "layer": skill_dir.name,
                        "issues": issues,
                    }
                )
            else:
                result["healthy"] += 1

    return result


def generate_report(results: dict[str, Any]) -> str:
    """Generate maintenance report."""
    lines = [
        "# Skill Maintenance Report",
        f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "\n## Summary",
    ]

    total_freed = 0.0

    if "logs" in results:
        lines.append(f"- Log rotation: {results['logs']['rotated']} files ({results['logs']['freed_mb']:.1f} MB)")
        total_freed += results['logs']['freed_mb']

    if "cache" in results:
        lines.append(f"- Cache cleanup: {results['cache']['cleaned']} dirs ({results['cache']['freed_mb']:.1f} MB)")
        total_freed += results['cache']['freed_mb']

    if "backups" in results:
        lines.append(
            f"- Backup cleanup: {results['backups']['cleaned']} files ({results['backups']['freed_mb']:.1f} MB)"
        )
        total_freed += results['backups']['freed_mb']

    lines.append(f"\n**Total freed**: {total_freed:.1f} MB")

    if "health" in results:
        h = results["health"]
        lines.append("\n## Skill Health")
        lines.append(f"- Total skills: {h['total']}")
        lines.append(f"- Healthy: {h['healthy']}")
        lines.append(f"- With issues: {len(h['issues'])}")

        if h["issues"]:
            lines.append("\n### Issues")
            for issue in h["issues"]:
                lines.append(f"- **{issue['skill']}** ({issue['layer']}): {', '.join(issue['issues'])}")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Skill Maintenance")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    repo_root = get_repo_root()
    data_dir = get_data_dir()

    _out("🔧 Running Skill Maintenance...\n")

    if args.dry_run:
        _out("DRY RUN - no changes will be made\n")

    results = {}

    # Log rotation
    _out("Rotating logs...")
    if not args.dry_run:
        results["logs"] = rotate_logs(data_dir)
    else:
        results["logs"] = {"rotated": 0, "freed_mb": 0.0}

    # Cache cleanup
    _out("Cleaning caches...")
    if not args.dry_run:
        results["cache"] = cleanup_cache(repo_root)
    else:
        results["cache"] = {"cleaned": 0, "freed_mb": 0.0}

    # Backup cleanup
    _out("Cleaning old backups...")
    if not args.dry_run:
        results["backups"] = cleanup_backups(data_dir)
    else:
        results["backups"] = {"cleaned": 0, "freed_mb": 0.0}

    # Health check (always runs)
    _out("Checking skill health...")
    results["health"] = check_skill_health(repo_root)

    _out()

    if args.json:
        _out(json.dumps(results, indent=2))
    else:
        _out(generate_report(results))

    return 0


if __name__ == "__main__":
    sys.exit(main())
