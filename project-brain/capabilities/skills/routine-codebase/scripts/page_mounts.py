"""auto-page-mounts: Verify contributions.pages source files exist.

Extracted from HardeningLoop._scan_page_mounts and _write_report (ADR-200).
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
from pathlib import Path

import yaml

from src.config.paths import get_all_client_skill_dirs
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.ops_protocol import (
    CANONICAL_BLOCK_TYPES, FixResult, OpsContext, ScanResult, clear_report, find_page_routes, report_only_fix,
)

name = "auto-page-mounts"


def _iter_skill_dirs(
    project_root: Path,
    shared_snapshot: dict | None = None,
) -> list[Path]:
    """Return discovered skill directories from shared snapshot or filesystem."""
    root_resolved = project_root.resolve()
    if shared_snapshot:
        skill_roots = shared_snapshot.get("skill_roots")
        if isinstance(skill_roots, list):
            skill_dirs = [
                Path(skill_root)
                for skill_root in skill_roots
                if isinstance(skill_root, str)
            ]
            return sorted(
                path for path in skill_dirs
                if path.is_dir() and _is_under_project_root(path, root_resolved)
            )

    results: list[Path] = []
    seen: set[Path] = set()
    plugins_dir = project_root / "plugins"
    if plugins_dir.is_dir():
        for skills_dir in sorted(plugins_dir.glob("*/skills")):
            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue
                resolved = skill_dir.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                results.append(skill_dir)
    for skills_dir in get_all_client_skill_dirs(project_root):
        if not _is_under_project_root(skills_dir, root_resolved):
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                resolved = skill_dir.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                results.append(skill_dir)
    return results


def _is_under_project_root(path: Path, root_resolved: Path) -> bool:
    try:
        path.resolve().relative_to(root_resolved)
        return True
    except ValueError:
        return False


def _load_skill_config(skill_dir: Path) -> tuple[str | None, dict]:
    """Load hub id + config from SKILL.md frontmatter or sidecar config file."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None, {}

    try:
        frontmatter, _body = parse_frontmatter(skill_md)
    except Exception:
        return None, {}
    if not isinstance(frontmatter, dict):
        return None, {}

    hub_id = frontmatter.get("x-augur-hub")
    if not isinstance(hub_id, str) or not hub_id:
        return None, {}

    config = frontmatter.get("x-augur-config")
    if isinstance(config, dict):
        return hub_id, config

    config_file = frontmatter.get("x-augur-config-file")
    if isinstance(config_file, str) and config_file:
        sidecar_path = skill_dir / config_file
        try:
            parsed = yaml.safe_load(sidecar_path.read_text())
        except Exception:
            return hub_id, {}
        if isinstance(parsed, dict):
            return hub_id, parsed

    return hub_id, {}


def _has_dashboard_page_source(
    project_root: Path,
    skill_dir: Path,
    hub_id: str,
    skill_name: str,
    page_id: str,
) -> bool:
    """Check whether a declared page is backed by a custom page source."""
    if not page_id:
        return False

    candidates = [
        skill_dir / "augur" / "dashboard" / page_id / "page.tsx",
        skill_dir / "augur" / "dashboard" / "page.tsx" if page_id in {skill_name, "overview"} else None,
        project_root / "plugins" / "ui" / "pages" / hub_id / skill_name / page_id / "page.tsx",
        project_root / "plugins" / "ui" / "pages" / hub_id / skill_name / "page.tsx" if page_id in {skill_name, "overview"} else None,
    ]
    return any(path.exists() for path in candidates if path is not None)


def scan(ctx: OpsContext) -> ScanResult:
    """Walk skill metadata and verify page/block mount wiring."""
    skill_dirs = get_all_client_skill_dirs(ctx.project_root)
    if not skill_dirs:
        return ScanResult(issues=[], summary="No skill directories found", severity="info")

    page_routes = find_page_routes(ctx.project_root, ctx.shared_snapshot)
    issues: list[dict] = []
    items_scanned = 0
    for skill_dir in _iter_skill_dirs(ctx.project_root, ctx.shared_snapshot):
        hub_id, data = _load_skill_config(skill_dir)
        if not hub_id:
            continue
        if not isinstance(data, dict):
            issues.append({
                "type": "invalid-augur-structure",
                "file": str((skill_dir / "SKILL.md").relative_to(ctx.project_root)),
                "detail": "x-augur-config top-level must be a mapping",
            })
            continue

        contributions = data.get("contributions") or {}
        if not isinstance(contributions, dict):
            issues.append({
                "type": "invalid-contributions-structure",
                "file": str((skill_dir / "SKILL.md").relative_to(ctx.project_root)),
                "detail": "contributions must be a mapping when present",
            })
            continue

        pages = contributions.get("pages") or []
        if not isinstance(pages, list):
            issues.append({
                "type": "invalid-pages-structure",
                "file": str((skill_dir / "SKILL.md").relative_to(ctx.project_root)),
                "detail": "contributions.pages must be a list when present",
            })
            continue
        items_scanned += len(pages)

        for page in pages:
            if not isinstance(page, dict):
                continue
            page_id = str(page.get("id", "")).strip()
            page_type = str(page.get("page_type", "custom") or "custom")
            if not page_id or page_type == "auto":
                continue
            if not _has_dashboard_page_source(ctx.project_root, skill_dir, hub_id, skill_dir.name, page_id):
                issues.append({
                    "type": "missing-page",
                    "file": str((skill_dir / "SKILL.md").relative_to(ctx.project_root)),
                    "detail": f"Custom page '{page_id}' has no dashboard page source for skill '{skill_dir.name}'",
                })

        # --- Block validation ---
        blocks = contributions.get("blocks") or []
        if isinstance(blocks, list):
            items_scanned += len(blocks)
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                block_id = block.get("id", "unknown")
                block_type = block.get("type", "")

                # Check canonical type
                if block_type and block_type not in CANONICAL_BLOCK_TYPES:
                    issues.append({
                        "type": "block-invalid-type",
                        "block_id": block_id,
                        "file": str((skill_dir / "SKILL.md").relative_to(ctx.project_root)),
                        "detail": f"Block '{block_id}' uses non-canonical type '{block_type}'",
                    })

                # Check expandTo route exists
                expand_to = block.get("expandTo", "")
                if expand_to and expand_to not in page_routes:
                    issues.append({
                        "type": "block-missing-expandto",
                        "block_id": block_id,
                        "file": str((skill_dir / "SKILL.md").relative_to(ctx.project_root)),
                        "detail": f"Block '{block_id}' expandTo '{expand_to}' has no page.tsx",
                    })

    if not issues:
        clear_report("page-mounts-latest.json")

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} mount issue(s) (pages + blocks)",
        severity="warning" if issues else "info",
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    return report_only_fix(ctx, "page-mounts-latest.json", issues, noun="mount issue")
