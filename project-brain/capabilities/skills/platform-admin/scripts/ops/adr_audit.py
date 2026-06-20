"""auto-adr-audit: Scan recently-implemented ADRs for quality gaps.

Checks ADRs marked Implemented for:
- Missing files/modules referenced in the ADR
- Non-canonical status formatting
- TODO/FIXME markers in files the ADR touches
- Duplicate ADR numbers
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
import re
from pathlib import Path

from src.lib.adr_utils import (
    detect_stale_status,
    find_duplicate_adrs,
    get_adr_dir,
    normalize_adr_status,
    scan_adrs,
)
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_issue

name = "auto-adr-audit"

MAX_ADRS = 15


def scan(ctx: OpsContext) -> ScanResult:
    decisions_dir = get_adr_dir()
    if not decisions_dir.exists():
        return ScanResult(issues=[], summary=f"No ADR directory: {decisions_dir}", severity="info")

    adrs = scan_adrs(decisions_dir)
    if not adrs:
        return ScanResult(issues=[], summary="No ADRs found", severity="info")

    issues: list[dict] = []

    # 1. Duplicate numbers
    dupes = find_duplicate_adrs(decisions_dir)
    for num, files in dupes.items():
        issues.append(
            make_issue(
                category=name,
                kind="manual",
                root_cause_type="manual_debt",
                fixability="manual",
                detail=f"ADR-{num:03d} has {len(files)} files: {', '.join(f.name for f in files)}",
                files=[str(f) for f in files],
                type="duplicate",
                severity="high",
                message=f"ADR-{num:03d} has {len(files)} files: {', '.join(f.name for f in files)}",
            )
        )

    # 2. Status formatting issues on recent implemented ADRs
    recent = sorted(adrs, key=lambda a: a.get("number", 0), reverse=True)[:MAX_ADRS]
    implemented = [a for a in recent if normalize_adr_status(a.get("status", "")) == "Implemented"]

    for adr in recent:
        raw = adr.get("status", "")
        canonical = normalize_adr_status(raw)
        if raw and raw != canonical:
            adr_path = str(adr.get("path", ""))
            issues.append(
                make_issue(
                    category=name,
                    kind="maintenance",
                    root_cause_type="generated_artifact",
                    fixability="automatic",
                    detail=f"ADR-{adr['number']:03d} status \"{raw}\" should be \"{canonical}\"",
                    path=adr_path,
                    type="status_format",
                    severity="low",
                    message=f"ADR-{adr['number']:03d} status \"{raw}\" should be \"{canonical}\"",
                    file=adr_path,
                )
            )

    # 3. Check implemented ADRs for referenced files that don't exist
    for adr in implemented:
        adr_path = adr.get("path")
        if not adr_path:
            continue
        content = Path(adr_path).read_text(errors="replace")
        missing = _check_referenced_paths(content, ctx.project_root)
        for path in missing[:5]:
            issues.append(
                make_issue(
                    category=name,
                    kind="manual",
                    root_cause_type="manual_debt",
                    fixability="manual",
                    detail=f"ADR-{adr['number']:03d} references missing path: {path}",
                    path=str(adr_path),
                    type="missing_file",
                    severity="medium",
                    message=f"ADR-{adr['number']:03d} references missing path: {path}",
                    file=str(adr_path),
                )
            )

    # 4. Stale status detection
    stale = detect_stale_status(adrs, days=60, decisions_dir=decisions_dir)
    for entry in stale:
        adr_path = str(entry.get("path", ""))
        issues.append(
            make_issue(
                category=name,
                kind="manual",
                root_cause_type="manual_debt",
                fixability="manual",
                detail=entry.get("message", f"ADR-{entry.get('number', '?')} has stale status"),
                path=adr_path,
                type="stale_status",
                severity="low",
                message=entry.get("message", f"ADR-{entry.get('number', '?')} has stale status"),
                file=adr_path,
            )
        )

    severity = "info"
    if any(i["severity"] == "high" for i in issues):
        severity = "error"
    elif any(i["severity"] == "medium" for i in issues):
        severity = "warning"

    return ScanResult(
        issues=issues,
        summary=f"Scanned {len(recent)} recent ADRs ({len(implemented)} implemented): {len(issues)} issues",
        severity=severity,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    from src.lib.adr_utils import load_adrs_index, write_adrs_index

    decisions_dir = get_adr_dir()
    if not decisions_dir.exists():
        return FixResult(success=True, summary="Nothing to fix")

    adrs = scan_adrs(decisions_dir)
    recent = sorted(adrs, key=lambda a: a.get("number", 0), reverse=True)[:MAX_ADRS]
    changes: list[str] = []

    # ADR-642: live entries no longer have on-disk .md files. Status normalization
    # rewrites the central JSON entry; legacy on-disk files are still rewritten
    # in-place when they exist (used only by tests/migration tooling).
    central_records = {r.get("adr_number"): r for r in load_adrs_index(decisions_dir)}
    central_dirty = False

    for adr in recent:
        raw = adr.get("status", "")
        canonical = normalize_adr_status(raw)
        if raw and raw != canonical:
            on_disk_path = adr.get("path") or ""
            if on_disk_path:
                path = Path(on_disk_path)
                text = path.read_text()
                updated = re.sub(
                    r"(\*\*Status\*\*[:\*]*\s*)" + re.escape(raw),
                    f"**Status**: {canonical}",
                    text,
                    count=1,
                )
                if updated != text:
                    path.write_text(updated)
                    changes.append(f"ADR-{adr['number']:03d}: \"{raw}\" -> \"{canonical}\"")
            else:
                key = f"ADR-{adr['number']:03d}"
                record = central_records.get(key)
                if record:
                    record["status"] = canonical
                    central_dirty = True
                    changes.append(f"ADR-{adr['number']:03d}: \"{raw}\" -> \"{canonical}\"")

    if central_dirty:
        write_adrs_index(decisions_dir, list(central_records.values()))

    return FixResult(
        success=True,
        changes=changes,
        summary=f"Fixed {len(changes)} status formatting issues" if changes else "No fixes needed",
    )


def _check_referenced_paths(content: str, project_root: Path) -> list[str]:
    """Extract file paths from ADR content and check which ones are missing."""
    patterns = [
        r'`((?:src|plugins|config|docs)/[a-zA-Z0-9_\-/.]+\.\w+)`',
        r'`((?:src|plugins|config|docs)/[a-zA-Z0-9_\-/.]+/)`',
    ]
    missing = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, content):
            ref = match.group(1).rstrip("/")
            if ref in seen:
                continue
            seen.add(ref)
            candidate = project_root / ref
            if not candidate.exists():
                missing.append(ref)
    return missing
