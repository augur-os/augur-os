#!/usr/bin/env python3
"""
Generate Route Map

Scans apps/dashboard/app/ for page.tsx files and outputs
docs/generated/route-map.md with route-to-source file mapping.

Usage:
    python3 .github/scripts/generate_route_map.py
"""

import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT = PROJECT_ROOT / "docs" / "generated" / "route-map.md"
APP_DIR = PROJECT_ROOT / "apps" / "dashboard" / "app"


def scan_routes() -> list[dict]:
    """Scan app directory for page.tsx files and derive routes."""
    routes = []
    if not APP_DIR.exists():
        return routes

    for page_file in sorted(APP_DIR.rglob("page.tsx")):
        rel = page_file.relative_to(APP_DIR)
        # Derive route from file path
        # e.g. career/interview/page.tsx -> /career/interview
        parts = list(rel.parts[:-1])  # Remove page.tsx
        route = "/" + "/".join(parts) if parts else "/"
        source = str(page_file.relative_to(PROJECT_ROOT))

        # Check if this is a mounted plugin file (has auto-generated header)
        plugin_source = None
        try:
            first_lines = page_file.read_text(encoding="utf-8")[:500]
            if "AUTO-GENERATED" in first_lines and "Source:" in first_lines:
                for line in first_lines.splitlines():
                    if line.strip().startswith("Source:"):
                        plugin_source = line.strip().replace("Source:", "").strip()
                        break
        except OSError:
            pass

        routes.append({
            "route": route,
            "source": source,
            "plugin_source": plugin_source,
        })
    return routes


def generate_markdown(routes: list[dict]) -> str:
    """Generate the route map markdown."""
    lines = [
        "# Dashboard Route Map",
        "",
        f"> Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}. Do not hand-edit.",
        "",
        f"**{len(routes)} routes** in `apps/dashboard/app/`.",
        "",
        "| Route | Source | Plugin Source |",
        "|-------|--------|--------------|",
    ]
    for r in routes:
        plugin = f"`{r['plugin_source']}`" if r["plugin_source"] else "-"
        lines.append(f"| `{r['route']}` | `{r['source']}` | {plugin} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    routes = scan_routes()
    if not routes:
        print("No routes found.", file=sys.stderr)
        return 1

    content = generate_markdown(routes)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(PROJECT_ROOT)} ({len(routes)} routes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
