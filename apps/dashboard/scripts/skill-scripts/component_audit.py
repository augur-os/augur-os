#!/usr/bin/env python3
"""
Component Audit Script
Analyzes the design system for consistency and usage patterns.

Usage:
    python component_audit.py [--unused] [--duplicates]
"""

import argparse
import os
import re
import sys
from pathlib import Path
from datetime import datetime


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _get_operations_dir() -> Path:
    env_base = os.environ.get("AUGUR_ROOT")
    if env_base:
        base = Path(os.path.expanduser(env_base)).expanduser().resolve()
        return base.parent / "plugins" / "dev" / "skills"

    try:
        repo_root = Path(__file__).resolve().parents[3]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from src.config.paths import get_operations_dir, get_project_root  # type: ignore

        return get_operations_dir()
    except Exception:
        return get_project_root() / "plugins" / "dev" / "skills"


def get_dashboard_root() -> Path:
    """Find the dashboard directory."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        dashboard = parent / "apps" / "dashboard"
        if dashboard.exists():
            return dashboard
    return Path(__file__).resolve().parents[2]  # apps/dashboard


def find_components(dashboard_root: Path) -> list[dict]:
    """Find all UI components in the components directory."""
    components = []
    components_dir = dashboard_root / "components"

    if not components_dir.exists():
        return components

    for tsx_file in components_dir.rglob("*.tsx"):
        if tsx_file.name.startswith("_") or ".test." in tsx_file.name:
            continue

        content = tsx_file.read_text(errors="ignore")

        # Check if it's a component (has export default or export function)
        is_component = bool(re.search(r"export\s+(default\s+)?function\s+\w+", content))

        # Count lines
        line_count = len(content.split("\n"))

        # Check for 'use client'
        is_client = "'use client'" in content or '"use client"' in content

        # Find imports
        imports = re.findall(r"from\s+['\"]([^'\"]+)['\"]", content)

        components.append(
            {
                "name": tsx_file.stem,
                "path": str(tsx_file.relative_to(dashboard_root)),
                "lines": line_count,
                "is_client": is_client,
                "is_component": is_component,
                "imports": imports,
            }
        )

    return components


def find_component_usage(dashboard_root: Path, component_names: set) -> dict[str, int]:
    """Count how many times each component is used."""
    usage = {name: 0 for name in component_names}

    for tsx_file in dashboard_root.rglob("*.tsx"):
        if "node_modules" in str(tsx_file):
            continue

        content = tsx_file.read_text(errors="ignore")

        for name in component_names:
            # Count JSX usage like <ComponentName
            count = len(re.findall(rf"<{name}[\s>/]", content))
            usage[name] += count

    return usage


def check_design_tokens(dashboard_root: Path) -> list[dict]:
    """Find hardcoded values that should use design tokens."""
    issues = []

    # Patterns that suggest hardcoded values
    bad_patterns = [
        (r"bg-white(?!/)", "Use bg-card or bg-background instead"),
        (r"text-\[#[0-9a-fA-F]+\]", "Use text-foreground or theme colors"),
        (r"bg-\[#[0-9a-fA-F]+\]", "Use theme background colors"),
        (r"border-\[#[0-9a-fA-F]+\]", "Use theme border colors"),
        (r"w-\[\d+px\]", "Use Tailwind spacing tokens"),
        (r"h-\[\d+px\]", "Use Tailwind spacing tokens"),
    ]

    for tsx_file in (dashboard_root / "app").rglob("*.tsx"):
        content = tsx_file.read_text(errors="ignore")

        for pattern, suggestion in bad_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                issues.append(
                    {
                        "file": str(tsx_file.relative_to(dashboard_root)),
                        "pattern": match,
                        "suggestion": suggestion,
                    }
                )

    return issues


def check_table_structure(dashboard_root: Path) -> list[dict]:
    """Check for table accessibility and layout stability."""
    issues = []

    for tsx_file in (dashboard_root / "app").rglob("*.tsx"):
        content = tsx_file.read_text(errors="ignore")

        # Simple regex to find <th> tags
        # If file has <th> but none of them have width classes (w-*, min-w-*, max-w-*), flag it.
        if "<th>" in content or "<th " in content:
            th_tags = re.findall(r"<th\s+([^>]*)>", content)
            if th_tags:
                has_width = any("w-" in attrs or "width" in attrs for attrs in th_tags)
                if not has_width:
                    issues.append(
                        {
                            "file": str(tsx_file.relative_to(dashboard_root)),
                            "pattern": "<th> without width",
                            "suggestion": "Add explicit width (w-[%], w-*) classes to <th> for stable numeric/grid layouts",
                        }
                    )

    return issues


def generate_report(components: list, usage: dict, token_issues: list, output_path: Path):
    """Generate audit report."""
    unused = [c for c in components if usage.get(c["name"], 0) == 0 and c["is_component"]]
    client_components = [c for c in components if c["is_client"]]

    report = f"""# Design System Audit Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

| Metric | Count |
|--------|-------|
| Total Components | {len(components)} |
| Client Components | {len(client_components)} |
| Potentially Unused | {len(unused)} |
| Design Token Issues | {len(token_issues)} |

## Potentially Unused Components

These components have 0 detected usages (may still be used dynamically):

"""

    for comp in unused[:15]:
        report += f"- `{comp['path']}` ({comp['lines']} lines)\n"

    if len(unused) > 15:
        report += f"\n*...and {len(unused) - 15} more*\n"

    report += "\n## Design Token Issues\n\n"

    if token_issues:
        for issue in token_issues[:20]:
            report += f"- `{issue['file']}`: `{issue['pattern']}` → {issue['suggestion']}\n"
    else:
        report += "No hardcoded values detected ✅\n"

    report += """
## Recommendations

1. **Consolidate unused components** - Remove or merge components with 0 usage
2. **Prefer Server Components** - Convert client components where possible
3. **Use design tokens** - Replace hardcoded colors and sizes with theme values
"""

    output_path.write_text(report, encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="Audit design system components")
    parser.add_argument("--unused", action="store_true", help="Show only unused components")
    parser.add_argument("--tokens", action="store_true", help="Check design token usage")
    parser.parse_args()

    dashboard_root = get_dashboard_root()
    _out(f"🎨 Component Audit - {dashboard_root}")
    _out("=" * 50)

    _out("\n📦 Finding components...")
    components = find_components(dashboard_root)
    _out(f"   Found {len(components)} components")

    _out("\n🔍 Analyzing usage...")
    component_names = {c["name"] for c in components}
    usage = find_component_usage(dashboard_root, component_names)

    unused_count = sum(1 for c in components if usage.get(c["name"], 0) == 0 and c["is_component"])
    _out(f"   {unused_count} potentially unused")

    _out("\n🎨 Checking design tokens...")
    token_issues = check_design_tokens(dashboard_root)
    _out(f"   {len(token_issues)} token issues found")

    _out("\n📐 Checking table structure...")
    table_issues = check_table_structure(dashboard_root)
    _out(f"   {len(table_issues)} table structure issues found")

    # Save report
    data_dir = _get_operations_dir() / "frontend" / "audits"
    data_dir.mkdir(parents=True, exist_ok=True)

    report_path = data_dir / f"component_audit_{datetime.now().strftime('%Y%m%d')}.md"
    generate_report(components, usage, token_issues + table_issues, report_path)

    _out(f"\n📄 Report saved to: {report_path}")
    _out("✅ Audit complete")

    return 0


if __name__ == "__main__":
    sys.exit(main())
