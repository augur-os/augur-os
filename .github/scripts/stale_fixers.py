"""
Phase 7: Auto-fix and reporting for the stale path scanner.

Applies safe substitutions and prints human-readable or JSON reports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from .stale_config import (
        KNOWN_RENAMES,
        ScanResult,
        StaleFinding,
    )
except ImportError:
    from stale_config import (
        KNOWN_RENAMES,
        ScanResult,
        StaleFinding,
    )


def apply_fixes(
    project_root: Path,
    findings: list[StaleFinding],
    rename_map: dict[str, str],
    dry_run: bool = False,
) -> dict[str, int]:
    """
    Apply auto-fixes for findings where auto_fixable=True and external=False.

    Returns:
        Dict with counts: {fixed, skipped, errors}
    """
    stats = {"fixed": 0, "skipped": 0, "errors": 0}

    fixable = [f for f in findings if f.auto_fixable and not f.external]
    files_to_fix: dict[str, list[StaleFinding]] = {}
    for f in fixable:
        files_to_fix.setdefault(f.file, []).append(f)

    for rel_file, file_findings in files_to_fix.items():
        abs_path = project_root / rel_file
        if not abs_path.exists():
            stats["skipped"] += len(file_findings)
            continue

        try:
            content = abs_path.read_text(encoding="utf-8")
            original = content

            for old_path, new_path in rename_map.items():
                old_str = old_path.rstrip("/")
                new_str = new_path.rstrip("/")
                new_abs = project_root / new_str
                if not new_abs.exists() and not new_str.startswith("runtime"):
                    continue
                content = content.replace(old_str, new_str)

            if content != original:
                if dry_run:
                    print(f"  [DRY-RUN] Would fix: {rel_file}")
                else:
                    abs_path.write_text(content, encoding="utf-8")
                    print(f"  [FIXED] {rel_file}")
                stats["fixed"] += 1
            else:
                stats["skipped"] += 1

        except (OSError, UnicodeDecodeError) as e:
            print(f"  [ERROR] {rel_file}: {e}", file=sys.stderr)
            stats["errors"] += 1

    return stats


def print_report(result: ScanResult) -> None:
    """Print human-readable report."""
    print("Augur Stale Path Scanner")
    print("=" * 60)
    print()

    print(f"Phase 1: Git History -- {result.git_renames_detected} directory renames detected via git")
    print(f"         Known renames: {len(KNOWN_RENAMES)} hardcoded")
    print(f"         Total rename map: {len(result.rename_map)} entries")
    print()

    if not result.findings:
        print("No stale path references found.")
        return

    print(f"Phase 2-6: Scan Results -- {len(result.findings)} stale references")
    print()

    by_category: dict[str, list[StaleFinding]] = {}
    for f in result.findings:
        key = f"{f.risk.upper()} ({f.category})"
        by_category.setdefault(key, []).append(f)

    for risk_level in ["high", "medium", "low"]:
        for key, items in sorted(by_category.items()):
            if not key.startswith(risk_level.upper()):
                continue

            fixable_count = sum(1 for i in items if i.auto_fixable and not i.external)
            ext_count = sum(1 for i in items if i.external)
            label_parts = []
            if fixable_count:
                label_parts.append(f"{fixable_count} auto-fixable")
            if ext_count:
                label_parts.append(f"{ext_count} external")
            review_count = len(items) - fixable_count - ext_count
            if review_count > 0:
                label_parts.append(f"{review_count} review")

            print(f"  {key}: {len(items)} findings ({', '.join(label_parts)})")
            print(f"  {'-' * 56}")

            by_replacement: dict[str, list[StaleFinding]] = {}
            for item in items:
                by_replacement.setdefault(item.replacement, []).append(item)

            for replacement, group in by_replacement.items():
                print(f"    {replacement}  ({len(group)} refs)")
                for item in group[:5]:
                    tag = "[EXT]" if item.external else ""
                    print(f"      {tag} {item.file}:{item.line}")
                if len(group) > 5:
                    print(f"      ... and {len(group) - 5} more")
            print()

    total = len(result.findings)
    auto = len(result.auto_fixable)
    ext = len(result.external_findings)
    review = len(result.review_needed)
    print(f"Summary: {total} stale, {auto} auto-fixable, {review} review, {ext} external")
    print("Run with --fix to auto-repair. Run with --dry-run to preview.")


def print_external_report(result: ScanResult) -> None:
    """Print only external findings with manual fix instructions."""
    ext = result.external_findings
    if not ext:
        print("No stale references in external configs.")
        return

    print("External Config Stale Paths")
    print("=" * 60)
    print()

    for f in ext:
        print(f"  {f.file}:{f.line}")
        print(f"    Found: {f.match[:100]}")
        print(f"    Fix:   {f.replacement}")
        print()

    print(f"Total: {len(ext)} external references (manual fix required)")


def print_json_report(result: ScanResult) -> None:
    """Print machine-readable JSON report."""
    output = {
        "rename_map": result.rename_map,
        "git_renames_detected": result.git_renames_detected,
        "findings": [f.to_dict() for f in result.findings],
        "summary": {
            "total": len(result.findings),
            "auto_fixable": len(result.auto_fixable),
            "review_needed": len(result.review_needed),
            "external": len(result.external_findings),
            "high_risk": len(result.high_risk),
        },
    }
    print(json.dumps(output, indent=2))
