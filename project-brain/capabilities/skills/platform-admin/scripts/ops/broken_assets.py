"""auto-broken-assets: Detect referenced images/assets that don't exist on disk.

Scans dashboard .tsx and .ts files for image references (src="/...",
import from asset files) and verifies the referenced files exist.

Scan:
  - difficulty 0: check /public/ references (src="/..." patterns)
  - difficulty 1+: also check import references for asset files
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

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-broken-assets"

DIFFICULTY_SPEC = {
    0: "Surface check — verify /public/ asset references exist",
    1: "Content check — also check import-based asset references",
    2: "Deep check — same as d1",
    3: "Exhaustive — same as d1",
    4: "Expert — same as d1",
}

# Match src="/something" or src='/something' (public directory references)
_PUBLIC_SRC_PATTERN = re.compile(
    r'''src\s*=\s*["'](/[^"'\s]+\.(?:png|jpg|jpeg|svg|gif|ico|webp))["']''',
    re.IGNORECASE,
)

# Match import ... from "....(png|jpg|svg|gif|ico|webp)"
_IMPORT_ASSET_PATTERN = re.compile(
    r'''(?:import|require)\s*(?:\(?\s*["']|.*?from\s+["'])([^"']+\.(?:png|jpg|jpeg|svg|gif|ico|webp))["']''',
    re.IGNORECASE,
)

_ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".gif", ".ico", ".webp"}
_SKIP_DIRS = {"node_modules", ".next", "__pycache__"}


def _find_source_files(dashboard_dir: Path) -> list[Path]:
    """Find all .tsx and .ts files under the dashboard directory."""
    files: list[Path] = []
    if not dashboard_dir.is_dir():
        return files
    for ext in ("*.tsx", "*.ts"):
        for f in dashboard_dir.rglob(ext):
            if any(skip in f.parts for skip in _SKIP_DIRS):
                continue
            files.append(f)
    return sorted(files)


def _check_public_refs(
    content: str,
    lines: list[str],
    public_dir: Path,
    source_file: Path,
    project_root: Path,
) -> list[dict]:
    """Check src="/..." references against the public directory."""
    issues: list[dict] = []
    for line_num, line in enumerate(lines, 1):
        for match in _PUBLIC_SRC_PATTERN.finditer(line):
            ref_path = match.group(1)
            # Remove leading slash — public dir serves from root
            asset_path = public_dir / ref_path.lstrip("/")
            if not asset_path.exists():
                rel_file = str(source_file.relative_to(project_root))
                issues.append({
                    "fingerprint": f"broken-asset:{rel_file}:{line_num}:{ref_path}",
                    "severity": "warning",
                    "message": f"Referenced asset not found: {ref_path}",
                    "file": rel_file,
                    "line": line_num,
                    "asset": ref_path,
                    "fixability": "manual",
                })
    return issues


def _check_import_refs(
    content: str,
    lines: list[str],
    source_file: Path,
    project_root: Path,
) -> list[dict]:
    """Check import/require asset references."""
    issues: list[dict] = []
    for line_num, line in enumerate(lines, 1):
        for match in _IMPORT_ASSET_PATTERN.finditer(line):
            ref_path = match.group(1)
            # Skip external URLs and package imports
            if ref_path.startswith("http") or not ref_path.startswith((".", "/")):
                continue
            # Resolve relative to the source file's directory
            if ref_path.startswith("/"):
                # Absolute from project root
                asset_path = project_root / ref_path.lstrip("/")
            else:
                asset_path = (source_file.parent / ref_path).resolve()
            if not asset_path.exists():
                rel_file = str(source_file.relative_to(project_root))
                issues.append({
                    "fingerprint": f"broken-asset:{rel_file}:{line_num}:{ref_path}",
                    "severity": "warning",
                    "message": f"Imported asset not found: {ref_path}",
                    "file": rel_file,
                    "line": line_num,
                    "asset": ref_path,
                    "fixability": "manual",
                })
    return issues


def scan(ctx: OpsContext) -> ScanResult:
    """Detect broken asset references in dashboard source files."""
    dashboard_dir = ctx.project_root / "apps" / "dashboard"
    if not dashboard_dir.is_dir():
        return ScanResult(
            issues=[],
            summary="No dashboard directory found",
            severity="info",
        )

    public_dir = dashboard_dir / "public"
    source_files = _find_source_files(dashboard_dir)
    if not source_files:
        return ScanResult(
            issues=[],
            summary="No .tsx/.ts files found in dashboard",
            severity="info",
            items_scanned=0,
        )

    issues: list[dict] = []
    files_checked = 0

    for source_file in source_files:
        try:
            content = source_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        files_checked += 1
        lines = content.splitlines()

        # Always check public references
        issues.extend(
            _check_public_refs(content, lines, public_dir, source_file, ctx.project_root)
        )

        # At difficulty >= 1, also check import references
        if ctx.difficulty >= 1:
            issues.extend(
                _check_import_refs(content, lines, source_file, ctx.project_root)
            )

    if not issues:
        return ScanResult(
            issues=[],
            summary=f"All asset references valid across {files_checked} files",
            severity="info",
            items_scanned=files_checked,
        )

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} broken asset reference(s) in {files_checked} files",
        severity="warning",
        items_scanned=files_checked,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Report-only: asset fixes require file-specific source decisions."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would report {len(issues)} broken asset reference(s)",
            fix_type="report",
        )

    return FixResult(
        success=True,
        summary=f"{len(issues)} broken asset reference(s) require manual remediation",
        fix_type="report",
    )
