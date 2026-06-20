"""Shared repo/runtime snapshot for adaptive loop cycles.

Phase 3 of ADR-412: build one low-cost inventory per cycle and pass it through
OpsContext so categories can opt into reusing shared discovery state.
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
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.paths import (
    get_all_client_skill_dirs,
    get_cache_dir,
    get_documents_dir,
    get_logs_dir,
    get_runtime_dir,
    get_vault_dir,
)
from src.lib.ops_protocol import find_page_routes

SNAPSHOT_VERSION = 1
IGNORED_PARTS = {".git", "node_modules", "__pycache__", ".next", "dist", "build"}


def _safe_git_dirty_files(project_root: Path, limit: int = 200) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    files: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        files.append(line[3:])
        if len(files) >= limit:
            break
    return files


def _discover_skill_roots(project_root: Path) -> list[str]:
    skills: list[str] = []
    root_resolved = project_root.resolve()
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
                skills.append(str(skill_dir))
    for skills_dir in get_all_client_skill_dirs(project_root):
        try:
            skills_dir.resolve().relative_to(root_resolved)
        except ValueError:
            continue
        if not skills_dir.exists():
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                resolved = skill_dir.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                skills.append(str(skill_dir))
    return skills


def _discover_api_routes(project_root: Path, limit: int = 500) -> list[str]:
    api_root = project_root / "apps" / "dashboard" / "app" / "api"
    routes: list[str] = []
    if not api_root.exists():
        return routes
    for path in sorted(api_root.rglob("route.ts")):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        routes.append(str(path.relative_to(project_root)))
        if len(routes) >= limit:
            break
    return routes


def _discover_page_routes(project_root: Path, limit: int = 500) -> list[str]:
    return sorted(find_page_routes(project_root))[:limit]


def _api_route_urls(route_paths: list[str]) -> list[str]:
    routes: list[str] = []
    prefix = "apps/dashboard/app"
    for route_path in route_paths:
        if not route_path.startswith(prefix):
            continue
        rel = route_path[len(prefix):].strip("/")
        if not rel.endswith("route.ts"):
            continue
        route_dir = rel[: -len("route.ts")].rstrip("/")
        if not route_dir:
            continue
        routes.append(f"/{route_dir}")
    return routes


def build_shared_snapshot(project_root: Path) -> dict[str, Any]:
    """Build a low-cost shared snapshot for one adaptive cycle."""
    apps_dashboard_root = project_root / "apps" / "dashboard"
    next_dev_lock = apps_dashboard_root / ".next" / "dev" / "lock"
    route_paths = _discover_api_routes(project_root)
    page_routes = _discover_page_routes(project_root)
    skill_roots = _discover_skill_roots(project_root)

    return {
        "version": SNAPSHOT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "dashboard_roots": [
            str(path)
            for path in (
                project_root / "apps" / "dashboard",
                project_root / "src" / "app",
            )
            if path.exists()
        ],
        "skill_roots": skill_roots,
        "skill_count": len(skill_roots),
        "api_route_paths": route_paths,
        "api_routes": _api_route_urls(route_paths),
        "api_route_count": len(route_paths),
        "page_routes": page_routes,
        "page_count": len(page_routes),
        "runtime": {
            "next_dev_lock_present": next_dev_lock.exists(),
            "vault_dir": str(get_vault_dir()),
            "documents_dir": str(get_documents_dir()),
            "runtime_dir": str(get_runtime_dir()),
            "logs_dir": str(get_logs_dir()),
            "cache_dir": str(get_cache_dir()),
        },
        "git_dirty_files": _safe_git_dirty_files(project_root),
        # ADR-412 Phase 3: aggregated hotspot data
        # Populated by engine after scan cycle via update_snapshot_hotspots()
        "hotspots": {},
    }


def update_snapshot_hotspots(
    shared_snapshot: dict[str, Any],
    categories: dict[str, Any],
) -> None:
    """Aggregate hotspot data from all category states into the shared snapshot.

    Args:
        shared_snapshot: The mutable snapshot dict built by build_shared_snapshot().
        categories: The loop_state.categories dict (name -> CategoryState).
    """
    hotspots: dict[str, Any] = {}
    for name, cs in categories.items():
        if not getattr(cs, "enabled", True):
            continue
        hot_paths = getattr(cs, "hot_paths", None) or []
        hot_patterns = getattr(cs, "hot_patterns", None) or []
        dominant = getattr(cs, "dominant_root_cause", "") or ""
        if hot_paths or hot_patterns or dominant:
            hotspots[name] = {
                "hot_paths": list(hot_paths),
                "hot_patterns": list(hot_patterns),
                "dominant_root_cause": str(dominant),
            }
    shared_snapshot["hotspots"] = hotspots
