"""Data loaders for platform-admin dashboard tools — read from vault/filesystem."""

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
from datetime import datetime, timezone
from typing import Any

import yaml

from src.config.paths import get_project_brain_skills_dir
from src.lib.skill_paths import get_own_data_dir

from ._shared import logger, get_project_root


def _load_refactor_report() -> dict[str, Any]:
    """Load the latest refactor report and expiry from YAML data files."""
    reports_dir = get_own_data_dir(__file__) / "reports"

    report_data: dict[str, Any] | None = None
    if reports_dir.is_dir():
        report_files = sorted(
            reports_dir.glob("ops-refactor-[0-9]*.yaml"),
            reverse=True,
        )
        for report_file in report_files:
            try:
                report_data = yaml.safe_load(report_file.read_text(encoding="utf-8"))
                break
            except Exception:
                logger.warning("Failed to parse report file: %s", report_file)
                continue

    expiry_data: dict[str, Any] | None = None
    expiry_file = reports_dir / "ops-refactor-expiry.yaml"
    if expiry_file.is_file():
        try:
            raw_expiry = yaml.safe_load(expiry_file.read_text(encoding="utf-8")) or {}
            now = datetime.now(timezone.utc)
            expires_at_str = raw_expiry.get("expires_at", "")
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                is_expired = now > expires_at
                days_until_expiry = (expires_at - now).days
            except (ValueError, AttributeError):
                is_expired = True
                days_until_expiry = 0

            expiry_data = {
                "expires_at": raw_expiry.get("expires_at", ""),
                "last_run": raw_expiry.get("last_run", ""),
                "is_expired": is_expired,
                "days_until_expiry": days_until_expiry,
            }
        except Exception:
            logger.warning("Failed to parse expiry file: %s", expiry_file)

    return {
        "report": report_data,
        "expiry": expiry_data,
    }


def _load_adaptive_growth() -> dict[str, Any]:
    """Load adaptive growth data from the platform-admin vault."""
    growth_dir = get_own_data_dir(__file__) / "adaptive-growth"
    if not growth_dir.is_dir():
        return {"success": True, "data": None, "message": "No adaptive growth data found"}

    items: list[dict[str, Any]] = []
    for f in sorted(growth_dir.iterdir()):
        if f.suffix in (".yaml", ".yml"):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if data:
                    items.append({"file": f.name, "data": data})
            except Exception:
                logger.warning("Failed to parse growth file: %s", f)
        elif f.suffix == ".md":
            items.append({"file": f.name, "type": "markdown", "preview": f.read_text(encoding="utf-8")[:500]})

    return {"success": True, "items": items, "count": len(items)}


def _load_dependencies() -> dict[str, Any]:
    """Load dependency graph from the platform-admin vault."""
    dep_file = get_own_data_dir(__file__) / "dependencies.yaml"
    if not dep_file.is_file():
        return {"success": True, "data": None, "message": "No dependency data found"}

    try:
        data = yaml.safe_load(dep_file.read_text(encoding="utf-8"))
        nodes = data.get("nodes", []) if isinstance(data, dict) else []
        return {
            "success": True,
            "version": data.get("version", "unknown") if isinstance(data, dict) else "unknown",
            "total_nodes": len(nodes),
            "data": data,
        }
    except Exception as exc:
        logger.warning("Failed to load dependencies: %s", exc)
        return {"success": False, "error": str(exc)}


def _load_nightly_checks() -> dict[str, Any]:
    """Load the latest nightly check results from the platform-admin vault."""
    night_dir = get_own_data_dir(__file__) / "night-shift"
    if not night_dir.is_dir():
        return {"success": True, "data": None, "message": "No nightly check data found"}

    handoff_files = sorted(night_dir.glob("handoff-*.md"), reverse=True)
    if not handoff_files:
        return {"success": True, "data": None, "message": "No nightly handoff reports found"}

    latest = handoff_files[0]
    try:
        content = latest.read_text(encoding="utf-8")
        return {
            "success": True,
            "file": latest.name,
            "date": latest.name.replace("handoff-", "").replace(".md", ""),
            "content": content[:2000],
            "total_reports": len(handoff_files),
        }
    except Exception as exc:
        logger.warning("Failed to read nightly check: %s", exc)
        return {"success": False, "error": str(exc)}


def _load_security_report() -> dict[str, Any]:
    """Load the latest security audit report from Documents/_augur/reports/security/."""
    from src.config.paths import get_documents_machine_dir

    security_dir = get_documents_machine_dir("reports") / "security"
    if not security_dir.is_dir():
        return {"status": "no_report", "message": "No security reports directory found"}

    audit_files = sorted(
        [f for f in security_dir.iterdir() if f.name.startswith("audit_") and f.suffix == ".json"],
    )
    if not audit_files:
        return {"status": "no_report", "message": "No audit reports found"}

    latest = audit_files[-1]
    try:
        import json as _json
        report = _json.loads(latest.read_text(encoding="utf-8"))
        return report
    except Exception as exc:
        logger.warning("Failed to read security report: %s", exc)
        return {"status": "error", "error": str(exc)}


def _verify_dashboard_mounts() -> dict[str, Any]:
    """Verify plugin dashboard page mounts have matching source files.

    Reads page contributions from project-brain/capabilities/skills/*/SKILL.md frontmatter
    (x-augur-config.contributions.pages) instead of legacy plugins/augur.yaml.
    """
    project_root = get_project_root()
    skills_dir = get_project_brain_skills_dir(project_root)
    dashboard_dir = project_root / "apps" / "dashboard" / "app"

    issues: list[dict[str, str]] = []
    total_checked = 0

    if not skills_dir.is_dir():
        return {"success": False, "error": "project-brain/capabilities/skills/ directory not found"}

    from src.lib.frontmatter_utils import parse_frontmatter

    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            meta, _body = parse_frontmatter(skill_md)
            if not meta:
                continue

            augur_config = meta.get("x-augur-config", {})
            if not isinstance(augur_config, dict):
                continue

            contributions = augur_config.get("contributions", {})
            if not isinstance(contributions, dict):
                continue

            pages = contributions.get("pages", [])
            if not isinstance(pages, list):
                continue

            skill_name = meta.get("name", skill_dir.name)
            hub = meta.get("x-augur-hub", augur_config.get("hub", "unknown"))

            for page in pages:
                if not isinstance(page, dict):
                    continue
                page_id = page.get("id", "")
                if not page_id:
                    continue
                total_checked += 1

                # Check both (views) and non-(views) paths
                mount_path = dashboard_dir / "(views)" / hub / skill_name / page_id
                mount_path_alt = dashboard_dir / hub / skill_name / page_id
                if not mount_path.is_dir() and not mount_path_alt.is_dir():
                    issues.append({
                        "skill": skill_name,
                        "hub": hub,
                        "page": page_id,
                        "expected_path": str(mount_path.relative_to(project_root)),
                    })
        except Exception:
            logger.warning("Failed to parse SKILL.md: %s", skill_md)
            continue

    return {
        "success": True,
        "total_checked": total_checked,
        "issues_found": len(issues),
        "issues": issues[:50],
    }
