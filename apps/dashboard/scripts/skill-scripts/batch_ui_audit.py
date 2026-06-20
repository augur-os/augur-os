#!/usr/bin/env python3
"""
Batch UI Audit Script
Discovers all static pages in the dashboard and executes the 'ui_quality_audit' chain for each.
"""

import importlib.util
import time
from pathlib import Path

import sys
from src.lib.ops_protocol import OpsContext


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Configuration
# Path: apps/dashboard/scripts/skill-scripts/batch_ui_audit.py
# Go up 5 levels to reach project root
REPO_ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_APP_DIR = REPO_ROOT / "apps/dashboard/app"
UI_QUALITY_SCRIPT = REPO_ROOT / "project-brain/capabilities/skills/loop-quality/scripts/ui_quality.py"
BENCHMARK_PAGE = "http://localhost:3000/agents"


def get_static_routes(app_dir: Path) -> list[str]:
    """Find all static page routes (excluding dynamic [param] routes)."""
    routes = []

    for page_file in app_dir.rglob("page.tsx"):
        # Get relative path from app dir
        rel_path = page_file.relative_to(app_dir)
        parent = rel_path.parent

        # Convert to route string
        if str(parent) == ".":
            route = "/"
        else:
            route = f"/{parent}"

        # exclude dynamic routes
        if "[" in route or "]" in route:
            # print(f"⚠️  Skipping dynamic route: {route}")
            continue

        routes.append(route)

    return sorted(routes)


def run_audit(route: str, index: int, total: int):
    """Run the audit chain for a specific route."""
    _out(f"\n[{index}/{total}] 🔍 Auditing Route: {route}")
    _out("=" * 60)

    route_key = route.lstrip("/")
    page_file = REPO_ROOT / "apps" / "dashboard" / "features" / "pages" / route_key / "page.tsx"
    if not page_file.exists():
        _out(f"⚠️  Skipping {route}: no matching features page at {page_file}")
        return

    spec = importlib.util.spec_from_file_location("batch_ui_quality", str(UI_QUALITY_SCRIPT))
    if spec is None or spec.loader is None:
        _out(f"⚠️  UI quality module not found at {UI_QUALITY_SCRIPT}")
        return

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_find_page_files = module._find_page_files
    module._find_page_files = lambda _root: {route_key: page_file}

    try:
        result = module.scan(OpsContext(project_root=REPO_ROOT, difficulty=1, dry_run=True))
        _out(f"✅ Audit Complete for {route}: {result.summary}")
    except Exception as e:
        _out(f"❌ Error running audit for {route}: {e}")
    finally:
        module._find_page_files = original_find_page_files


def main():
    _out("🚀 Starting Batch UI Quality Audit")
    _out(f"   Target: {DASHBOARD_APP_DIR}")
    _out(f"   Benchmark: {BENCHMARK_PAGE}")
    _out("-" * 60)

    routes = get_static_routes(DASHBOARD_APP_DIR)

    _out(f"📋 Found {len(routes)} static routes to audit.")
    time.sleep(2)  # Give user a chance to read

    for i, route in enumerate(routes, 1):
        run_audit(route, i, len(routes))
        time.sleep(1)  # Brief pause between chains

    _out("\n🎉 Batch Audit Completed.")


if __name__ == "__main__":
    main()
