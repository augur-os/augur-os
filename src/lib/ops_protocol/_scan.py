"""
ops_protocol._scan — Shared scanning utilities used by multiple auto-* modules.

collect_all_block_ids, find_page_routes, find_api_routes, check_http_route.

Internal use by the ops_protocol package; do not import directly from outside.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.config.paths import get_project_brain_skills_dir
from src.lib.frontmatter_utils import parse_frontmatter

# Import OpsContext directly from _core to avoid circular imports via __init__

CANONICAL_BLOCK_TYPES = {
    "stat-card",
    "stat-grid",
    "data-list",
    "data-table",
    "action-bar",
    "card-grid",
    "chart",
    "markdown",
    "calendar",
    "activity-feed",
    "notes",
    "embed",
    "ops-board",
    "progress",
    "tabbed",
}


def collect_all_block_ids(project_root: Path) -> set[str]:
    """Collect all block IDs from skill frontmatter contributions.blocks."""
    all_ids: set[str] = set()
    skill_files: list[Path] = []
    plugins_dir = project_root / "plugins"
    if plugins_dir.is_dir():
        skill_files = list(plugins_dir.glob("*/skills/*/SKILL.md"))
    skills_dir = get_project_brain_skills_dir(project_root)
    if skills_dir.is_dir():
        skill_files.extend(skills_dir.glob("*/SKILL.md"))
    for skill_file in sorted(set(skill_files)):
        try:
            frontmatter, _body = parse_frontmatter(skill_file)
        except Exception:
            continue
        if not isinstance(frontmatter, dict):
            continue
        config = frontmatter.get("x-augur-config", {})
        if not isinstance(config, dict):
            config = {}
        contributions = config.get("contributions")
        if not isinstance(contributions, dict):
            continue
        blocks = contributions.get("blocks", [])
        if not isinstance(blocks, list):
            continue
        skill_name = frontmatter.get("name") or skill_file.parent.name
        for block in blocks:
            if isinstance(block, dict) and block.get("id"):
                block_id = block["id"]
                all_ids.add(block_id)
                all_ids.add(f"{skill_name}:{block_id}")

    generated_registry = project_root / "apps" / "dashboard" / "lib" / "blocks" / "generated-block-registry.ts"
    if generated_registry.is_file():
        try:
            content = generated_registry.read_text(encoding="utf-8")
            all_ids.update(re.findall(r"'([A-Za-z0-9_-]+:[A-Za-z0-9_-]+)'\s*:", content))
        except Exception:
            pass
    return all_ids


def _dashboard_app_root(project_root: Path) -> Path:
    """Return the canonical dashboard app root."""
    return project_root / "apps" / "dashboard" / "app"


_REGISTRY_KEY_RE = re.compile(r"'([^']+)'\s*:")


def _collect_page_routes_from_root(root: Path) -> set[str]:
    """Collect page routes from a concrete filesystem root."""
    routes: set[str] = set()
    if not root.exists():
        return routes
    for page in root.glob("**/page.tsx"):
        rel = page.parent.relative_to(root)
        rel_str = str(rel).replace("\\", "/")
        if "[[" in rel_str:
            route = "/" + rel_str
            routes.add(route)
            registry = page.parent / "registry.ts"
            if registry.is_file():
                routes.update(_parse_catchall_registry(registry, root))
        else:
            route = "/" if rel_str == "." else "/" + rel_str
            routes.add(route)
    return routes


def _parse_catchall_registry(registry_path: Path, app_root: Path) -> set[str]:
    """Parse a catch-all registry.ts and return the full page routes it defines."""
    routes: set[str] = set()
    try:
        content = registry_path.read_text(encoding="utf-8")
    except Exception:
        return routes
    catchall_dir = registry_path.parent
    hub_dir = catchall_dir.parent
    try:
        hub_prefix = "/" + str(hub_dir.relative_to(app_root)).replace("\\", "/")
    except ValueError:
        return routes
    for m in _REGISTRY_KEY_RE.finditer(content):
        sub_path = m.group(1)
        routes.add(f"{hub_prefix}/{sub_path}")
    return routes


def find_page_routes(
    project_root: Path,
    shared_snapshot: dict | None = None,
) -> set[str]:
    """Collect all valid page routes from dashboard."""
    if shared_snapshot:
        routes = shared_snapshot.get("page_routes")
        if isinstance(routes, list):
            return {route for route in routes if isinstance(route, str)}

    routes: set[str] = set()
    for root in (
        _dashboard_app_root(project_root),
        project_root / "apps" / "dashboard" / "lib" / "plugin-pages",
        project_root / "plugins" / "ui" / "pages",
    ):
        routes.update(_collect_page_routes_from_root(root))
    return routes


def find_api_routes(
    project_root: Path,
    shared_snapshot: dict | None = None,
) -> set[str]:
    """Collect all valid API route paths."""
    if shared_snapshot:
        routes = shared_snapshot.get("api_routes")
        if isinstance(routes, list):
            return {route for route in routes if isinstance(route, str)}

    routes: set[str] = set()
    api_dir = _dashboard_app_root(project_root) / "api"
    if not api_dir.exists():
        return routes
    for route_file in api_dir.glob("**/route.ts"):
        rel = route_file.parent.relative_to(_dashboard_app_root(project_root))
        route = "/" + str(rel).replace("\\", "/")
        routes.add(route)
    return routes


def check_http_route(url: str, timeout: int = 10) -> dict:
    """Check a single HTTP route and return result dict."""
    import urllib.error
    import urllib.request

    if not url.lower().startswith(("http://", "https://")):
        return {"ok": False, "error": f"Refusing non-HTTP URL scheme: {url!r}"}
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # nosec B310
            return {"ok": resp.status == 200, "status": resp.status}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "error": str(e)}
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        return {"ok": False, "error": str(e)}
