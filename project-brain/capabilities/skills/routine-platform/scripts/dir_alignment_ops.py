"""Auto-loop scan/fix for directory alignment to skill names.

Spec: docs/superpowers/specs/2026-03-23-dir-alignment-design.md
"""

from __future__ import annotations


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
import logging
import shutil
from pathlib import Path

from src.lib.dir_alignment import (
    ManagedLocation,
    classify_violation,
    find_closest_skill,
    get_managed_locations,
    get_skill_names,
    validate_dir_name,
)
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
)

name = "auto-dir-alignment"

DIFFICULTY_SPEC = {
    0: "Report — list violations with classification",
    1: "Auto-fix — rename trivial-rename dirs",
    2: "Scaffold — create skills for new-skill-candidate dirs",
    3: "Interactive — prompt user for unknown dirs",
}

logger = logging.getLogger(__name__)


def _get_locations() -> list[ManagedLocation]:
    """Wrapper for testability."""
    return get_managed_locations()


def scan(ctx: OpsContext) -> ScanResult:
    """Scan managed locations for directory alignment violations."""
    locations = _get_locations()
    if not locations:
        return ScanResult(
            issues=[],
            summary="No managed locations configured",
            severity="info",
            health="verified",
        )

    issues: list[dict] = []
    dirs_scanned = 0
    all_dir_names: set[str] = set()

    for loc in locations:
        if not loc.path.is_dir():
            continue
        for entry in sorted(loc.path.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            dirs_scanned += 1
            all_dir_names.add(entry.name)
            if not validate_dir_name(loc, entry.name):
                closest = find_closest_skill(entry.name)
                classification = "trivial-rename" if closest else classify_violation(loc, entry.name)
                detail = f"{entry.name} in {loc.path.name}"
                if closest:
                    detail += f" (closest: {closest[0]}, score: {closest[1]:.2f})"

                if classification == "trivial-rename" and ctx.difficulty >= 1:
                    kind = "actionable"
                elif classification == "trivial-rename":
                    kind = "maintenance"
                elif ctx.difficulty < 2:
                    kind = "maintenance"
                else:
                    kind = "manual"

                issues.append(make_issue(
                    category="dir-alignment",
                    detail=detail,
                    path=str(entry),
                    kind=kind,
                    root_cause_type="manual_debt",
                    fixability="auto" if classification == "trivial-rename" else "manual",
                    classification=classification,
                    dir_name=entry.name,
                    closest_skill=closest[0] if closest else None,
                    location=str(loc.path),
                ))

    # Evolution gaps at max difficulty
    if not issues and ctx.difficulty >= max(DIFFICULTY_SPEC.keys()):
        skills = get_skill_names()
        missing = skills - all_dir_names
        if missing:
            issues.append(evolution_gap(
                f"All aligned, but {len(missing)} skills have no vault/docs dir yet"
            ))

    severity = "error" if any(i.get("kind") == "actionable" for i in issues) else "info"
    health = "degraded" if issues and any(i.get("kind") != "maintenance" for i in issues) else "verified"

    return ScanResult(
        issues=issues,
        summary=f"Scanned {dirs_scanned} dirs, {len(issues)} violation(s)",
        severity=severity,
        health=health,
        items_scanned=dirs_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix directory alignment violations based on difficulty level.

    d0: Report summary only.
    d1+: Rename trivial-rename dirs to closest skill name.
    d2+: Add non-skill dirs to .augur-reserved so they are not re-flagged.
          Report orphan dirs (new-skill-candidate, unknown) for manual review.
    """
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issue(s) found")

    if not issues:
        return FixResult(success=True, summary="No issues to fix")

    if ctx.difficulty < 1:
        return FixResult(
            success=True,
            summary=f"{len(issues)} alignment issue(s) found (report only at d0)",
            fix_type="report",
        )

    actions: list[dict] = []
    changes: list[str] = []

    # Collect dirs to add to .augur-reserved, grouped by location
    reserved_additions: dict[str, list[str]] = {}  # location_path -> [dir_names]

    for issue in issues:
        classification = issue.get("classification")

        if classification == "trivial-rename" and ctx.difficulty >= 1:
            src_path = Path(issue["path"])
            closest = issue.get("closest_skill")
            if closest and src_path.is_dir():
                dst_path = src_path.parent / closest
                if not dst_path.exists():
                    try:
                        shutil.move(str(src_path), str(dst_path))
                        actions.append({"action": "rename", "from": src_path.name, "to": closest})
                        changes.append(str(dst_path))
                    except OSError as e:
                        logger.warning("Failed to rename %s -> %s: %s", src_path, dst_path, e)

        elif classification in ("new-skill-candidate", "unknown") and ctx.difficulty >= 2:
            # Add to .augur-reserved so the dir is not re-flagged each cycle
            location = issue.get("location", "")
            dir_name = issue.get("dir_name", "")
            if location and dir_name:
                reserved_additions.setdefault(location, []).append(dir_name)
                actions.append({
                    "action": "reserve",
                    "dir": dir_name,
                    "location": location,
                    "classification": classification,
                })

    # Write .augur-reserved additions
    for location_path, dir_names in reserved_additions.items():
        reserved_file = Path(location_path) / ".augur-reserved"
        try:
            existing: set[str] = set()
            if reserved_file.exists():
                for line in reserved_file.read_text(encoding="utf-8").splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        existing.add(stripped)

            new_names = sorted(set(dir_names) - existing)
            if new_names:
                with open(reserved_file, "a", encoding="utf-8") as f:
                    if not existing and not reserved_file.exists():
                        f.write("# Augur-reserved directory names (not skills)\n")
                    for name_ in new_names:
                        f.write(f"{name_}\n")
                changes.append(
                    f"Added {len(new_names)} dir(s) to {reserved_file}: {', '.join(new_names)}"
                )
        except OSError as e:
            logger.warning("Failed to update %s: %s", reserved_file, e)

    summary_parts = []
    rename_count = sum(1 for a in actions if a.get("action") == "rename")
    reserve_count = sum(1 for a in actions if a.get("action") == "reserve")
    if rename_count:
        summary_parts.append(f"Renamed {rename_count} dir(s)")
    if reserve_count:
        summary_parts.append(f"Reserved {reserve_count} dir(s)")
    summary = "; ".join(summary_parts) if summary_parts else "No actionable fixes at this difficulty"

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if changes else "report",
    )
