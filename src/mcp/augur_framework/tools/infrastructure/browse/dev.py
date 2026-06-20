"""Dev/test listing tools: tests, API routes."""

import json
import re

from src.config.paths import get_project_root, get_skills_dir


async def list_tests_impl() -> str:
    """List all test files across skills, dashboard, and Python tests."""
    project_root = get_project_root()
    items = []
    # 1. Skill tests
    skills_dir = get_skills_dir()
    if skills_dir.exists():
        for test_file in sorted(skills_dir.glob("*/augur/tests/**/*")):
            if not test_file.is_file():
                continue
            parts = test_file.relative_to(skills_dir).parts
            skill = parts[0]
            ext = test_file.suffix
            test_type = "pytest" if ext == ".py" else "jest" if ext in (".ts", ".tsx") else "unknown"
            items.append(
                {
                    "id": f"{skill}/tests/{test_file.name}",
                    "title": test_file.stem,
                    "description": f"{test_type} test for {skill}",
                    "hub": "dev",
                    "skill": skill,
                    "path": str(test_file),
                    "test_type": test_type,
                }
            )
    # 2. Dashboard tests
    dashboard_dir = project_root / "apps" / "dashboard"
    if dashboard_dir.exists():
        for test_file in sorted(dashboard_dir.rglob("*.test.*")):
            if not test_file.is_file():
                continue
            items.append(
                {
                    "id": f"dashboard/{test_file.relative_to(dashboard_dir)}",
                    "title": test_file.stem.replace(".test", ""),
                    "description": "Dashboard test",
                    "hub": "dev",
                    "path": str(test_file),
                    "test_type": "jest",
                }
            )
    # 3. Python tests
    tests_dir = project_root / "tests"
    if tests_dir.exists():
        for test_file in sorted(tests_dir.rglob("test_*.py")):
            if not test_file.is_file():
                continue
            items.append(
                {
                    "id": f"tests/{test_file.relative_to(tests_dir)}",
                    "title": test_file.stem,
                    "description": "Python test",
                    "hub": "dev",
                    "path": str(test_file),
                    "test_type": "pytest",
                }
            )
    return json.dumps({"items": items, "count": len(items)})


async def list_api_routes_impl() -> str:
    """List all API routes from the dashboard."""
    project_root = get_project_root()
    api_dir = project_root / "apps" / "dashboard" / "app" / "api"
    items = []
    if not api_dir.exists():
        return json.dumps({"items": [], "count": 0})
    for route_file in sorted(api_dir.rglob("route.ts")):
        rel = route_file.relative_to(api_dir)
        route_path = "/api/" + str(rel.parent).replace("\\", "/")
        route_path = re.sub(r"\(.*?\)/", "", route_path)
        content = route_file.read_text(errors="ignore")
        methods = []
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            if f"export const {method}" in content or f"export async function {method}" in content:
                methods.append(method)
        hub = "system"
        # Route path segments are matched against discovered skill names.
        # (Hubs were retired in ADR-802; skill names are the only valid
        # path segments — e.g. /rag maps to the rag skill.)
        hub_names: set[str] = set()
        try:
            from src.mcp.augur_shared.plugin_tools import _collect_skill_dirs

            for _plugin_id, skill_dir in _collect_skill_dirs(apply_exclusions=False):
                hub_names.add(skill_dir.name)
        except Exception:
            # Conservative fallback if registry unavailable: empty set means
            # all routes default to hub="system".
            pass
        for part in route_path.split("/"):
            if part in hub_names:
                hub = part
                break
        items.append(
            {
                "id": route_path,
                "title": route_path,
                "description": f"{', '.join(methods) or 'GET'} endpoint",
                "hub": hub,
                "path": str(route_file),
                "methods": methods or ["GET"],
            }
        )
    return json.dumps({"items": items, "count": len(items)})
