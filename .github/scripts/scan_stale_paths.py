#!/usr/bin/env python3
"""
Deep Stale Path Scanner & Auto-Fixer for Augur.

Scans the codebase, external shell configs, LaunchAgents, and IDE configs
for references to renamed/moved directories.  Optionally auto-fixes safe
substitutions or prints manual instructions for external files.

Phases:
  1. Build rename map from git history + hardcoded fallback
  2. Scan codebase for stale references (ripgrep)
  3. Scan external configs (shell, plist, IDE, git hooks)
  4. Detect fragile path patterns that should use src.config.paths
  5. Auto-fix (--fix) or preview (--dry-run)

Usage:
  python3 .github/scripts/scan_stale_paths.py              # Full report
  python3 .github/scripts/scan_stale_paths.py --fix         # Auto-fix + report
  python3 .github/scripts/scan_stale_paths.py --dry-run     # Preview fixes
  python3 .github/scripts/scan_stale_paths.py --json        # Machine-readable
  python3 .github/scripts/scan_stale_paths.py --category hub_rename
  python3 .github/scripts/scan_stale_paths.py --external    # Only external configs
  python3 .github/scripts/scan_stale_paths.py --ci          # Exit 1 if high-risk found
  python3 .github/scripts/scan_stale_paths.py --quick --ci  # Only staged files (pre-commit)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Sub-modules (same directory, imported as siblings)
# When run as __main__, need direct imports; when imported as package, use relative.
try:
    from .stale_config import (
        NO_AUTOFIX_PREFIXES,
        ScanResult,
        StaleFinding,
    )
    from .stale_rename_map import build_rename_map, get_project_root
    from .stale_scanners import (
        scan_codebase,
        scan_data_segments,
        scan_external_configs,
        scan_fragile_paths,
        scan_phantom_paths,
    )
    from .stale_fixers import (
        apply_fixes,
        print_external_report,
        print_json_report,
        print_report,
    )
except ImportError:
    from stale_config import (
        NO_AUTOFIX_PREFIXES,
        ScanResult,
        StaleFinding,
    )
    from stale_rename_map import build_rename_map, get_project_root
    from stale_scanners import (
        scan_codebase,
        scan_data_segments,
        scan_external_configs,
        scan_fragile_paths,
        scan_phantom_paths,
    )
    from stale_fixers import (
        apply_fixes,
        print_external_report,
        print_json_report,
        print_report,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# QUICK MODE (staged files only)
# ═══════════════════════════════════════════════════════════════════════════════


def _get_staged_files(project_root: Path) -> list[str]:
    """Get list of staged files (relative paths) from git index."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=project_root,
        )
        return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def _scan_staged_file_for_renames(
    project_root: Path,
    file_path: str,
    rename_map: dict[str, str],
) -> list[StaleFinding]:
    """Scan a single staged file for stale path references."""
    findings: list[StaleFinding] = []
    abs_path = project_root / file_path

    if not abs_path.exists():
        return findings

    try:
        content = abs_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return findings

    for old_path, new_path in rename_map.items():
        stripped = old_path.rstrip("/")
        path_token = old_path if "/" not in stripped else stripped
        escaped_token = re.escape(path_token)
        pattern = rf"(?:^|[\s\"'`(\[{{=]){escaped_token}"
        replacement_hint = f"{old_path.rstrip('/')} -> {new_path.rstrip('/')}"

        is_data_rename = old_path.startswith("data/")
        category = "data_structure" if is_data_rename else "hub_rename"

        for line_num, line in enumerate(content.split("\n"), start=1):
            if re.search(pattern, line):
                is_historical_doc = any(
                    file_path.startswith(p) for p in NO_AUTOFIX_PREFIXES
                )
                finding_risk = "low" if is_historical_doc else "high"
                is_fixable = not is_historical_doc

                findings.append(StaleFinding(
                    file=file_path,
                    line=line_num,
                    match=line.strip(),
                    replacement=replacement_hint,
                    category=category,
                    risk=finding_risk,
                    auto_fixable=is_fixable,
                ))

    return findings


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════════════════


def run_scan(
    project_root: Path,
    category_filter: Optional[str] = None,
    external_only: bool = False,
    quick: bool = False,
) -> ScanResult:
    """Execute all scan phases and return aggregated results."""
    rename_map, git_count = build_rename_map(project_root)

    result = ScanResult(
        rename_map=rename_map,
        git_renames_detected=git_count,
    )

    if external_only:
        result.findings = scan_external_configs(project_root, rename_map)
        return result

    if quick:
        staged_files = _get_staged_files(project_root)
        for staged_file in staged_files:
            result.findings.extend(
                _scan_staged_file_for_renames(project_root, staged_file, rename_map)
            )
        if category_filter:
            result.findings = [f for f in result.findings if f.category == category_filter]
        return result

    if not category_filter or category_filter in ("hub_rename", "data_structure"):
        result.findings.extend(scan_codebase(project_root, rename_map))

    result.findings.extend(scan_external_configs(project_root, rename_map))

    if not category_filter or category_filter == "fragile_path":
        result.findings.extend(scan_fragile_paths(project_root))

    if not category_filter or category_filter == "phantom_path":
        result.findings.extend(scan_phantom_paths(project_root, rename_map))

    if not category_filter or category_filter == "data_segment":
        result.findings.extend(scan_data_segments(project_root))

    if category_filter:
        result.findings = [f for f in result.findings if f.category == category_filter]

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan for stale path references after directory renames"
    )
    parser.add_argument("--fix", action="store_true",
                        help="Auto-fix safe substitutions")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview fixes without writing")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    parser.add_argument("--ci", action="store_true",
                        help="CI mode: exit 1 if high-risk found")
    parser.add_argument("--category", type=str,
                        choices=["hub_rename", "data_structure", "fragile_path", "phantom_path", "data_segment"],
                        help="Filter to specific category")
    parser.add_argument("--external", action="store_true",
                        help="Only scan external configs")
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: only scan staged files (for pre-commit hooks)")
    parser.add_argument("--path", type=str,
                        help="Project root path (default: auto-detect)")
    args = parser.parse_args()

    project_root = Path(args.path) if args.path else get_project_root()
    result = run_scan(project_root, args.category, args.external, quick=args.quick)

    if args.fix or args.dry_run:
        stats = apply_fixes(
            project_root, result.findings, result.rename_map,
            dry_run=args.dry_run,
        )
        print()
        print(f"Fix stats: {stats['fixed']} fixed, {stats['skipped']} skipped, {stats['errors']} errors")
        print()

    if args.json:
        print_json_report(result)
    elif args.external:
        print_external_report(result)
    else:
        print_report(result)

    if args.ci and result.high_risk:
        print(
            f"\nCI FAILURE: {len(result.high_risk)} high-risk stale path(s) found",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
