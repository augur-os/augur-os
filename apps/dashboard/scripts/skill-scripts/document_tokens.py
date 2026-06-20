#!/usr/bin/env python3
"""
Design Token Documentation for Frontend Design Agent.

Documents design tokens:
- Colors
- Typography
- Spacing
- Components
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def get_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def extract_css_variables(css_path: Path) -> list[dict[str, str]]:
    """Extract CSS custom properties from a file."""
    variables = []

    if not css_path.exists():
        return variables

    content = css_path.read_text(encoding="utf-8")

    # Match --variable-name: value;
    pattern = r"--([a-zA-Z0-9-]+):\s*([^;]+);"

    for match in re.finditer(pattern, content):
        variables.append(
            {
                "name": f"--{match.group(1)}",
                "value": match.group(2).strip(),
            }
        )

    return variables


def categorize_tokens(variables: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """Categorize tokens by type."""
    categories = {
        "colors": [],
        "typography": [],
        "spacing": [],
        "borders": [],
        "shadows": [],
        "other": [],
    }

    for var in variables:
        name = var["name"].lower()
        value = var["value"].lower()

        if any(kw in name for kw in ["color", "bg", "text", "border-color"]) or any(
            kw in value for kw in ["#", "rgb", "hsl"]
        ):
            categories["colors"].append(var)
        elif any(kw in name for kw in ["font", "text", "line-height", "letter"]):
            categories["typography"].append(var)
        elif any(kw in name for kw in ["space", "gap", "margin", "padding"]):
            categories["spacing"].append(var)
        elif any(kw in name for kw in ["border", "radius"]):
            categories["borders"].append(var)
        elif any(kw in name for kw in ["shadow"]):
            categories["shadows"].append(var)
        else:
            categories["other"].append(var)

    return categories


def find_css_files(repo: Path) -> list[Path]:
    """Find CSS files in the dashboard."""
    dashboard = repo / "apps" / "dashboard"
    css_files = []

    if dashboard.exists():
        css_files.extend(dashboard.rglob("*.css"))

    return css_files


def generate_documentation(categories: dict[str, list], source_files: list[Path]) -> str:
    """Generate design token documentation."""
    total = sum(len(v) for v in categories.values())

    lines = [
        "# Design Tokens",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Source files**: {len(source_files)}",
        f"**Total tokens**: {total}",
        "",
    ]

    for category, tokens in categories.items():
        if not tokens:
            continue

        lines.append(f"## {category.title()} ({len(tokens)})")
        lines.append("")
        lines.append("| Token | Value |")
        lines.append("|-------|-------|")

        for token in tokens[:30]:
            value = token["value"][:40] + "..." if len(token["value"]) > 40 else token["value"]
            lines.append(f"| `{token['name']}` | `{value}` |")

        if len(tokens) > 30:
            lines.append(f"| ... | ({len(tokens) - 30} more) |")

        lines.append("")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Design Token Documentation")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--save", action="store_true", help="Save documentation")
    args = parser.parse_args()

    repo = get_repo_root()

    _out("🎨 Extracting design tokens...\n")

    css_files = find_css_files(repo)
    _out(f"   Found {len(css_files)} CSS files")

    all_variables = []
    for css_file in css_files:
        all_variables.extend(extract_css_variables(css_file))

    _out(f"   Extracted {len(all_variables)} tokens")

    categories = categorize_tokens(all_variables)

    if args.json:
        _out(json.dumps(categories, indent=2))
        return 0

    doc = generate_documentation(categories, css_files)

    if args.save:
        output_path = repo / "apps" / "dashboard" / "DESIGN_TOKENS.md"
        output_path.write_text(doc, encoding="utf-8")
        _out(f"Saved to: {output_path}\n")

    _out(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
