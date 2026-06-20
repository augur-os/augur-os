#!/usr/bin/env python3
"""
Skill Exporter - Generate export packages from Augur skills.

Supports exporting from ANY bundle (crew, services, apps, orchestrator)
to multiple target formats. Uses # @augur markers for structured stripping
of Augur-specific extensions (ADR-040).

Export targets:
    claude-code    -> .claude-plugin/ directory (Claude Code plugin)
    mcp-server     -> Standalone MCP server with server.py
    python-package -> pyproject.toml + src/ layout

Usage:
    python skill_exporter.py project-brain/capabilities/skills/platform-admin/
    python skill_exporter.py project-brain/capabilities/skills/knowledge/ --target mcp-server
    python skill_exporter.py --batch devops architect --target claude-code
    python skill_exporter.py --all --target claude-code

Sub-modules:
    skill_exporter_parse   -- SKILL.md parsing, marker stripping, content generation
    skill_exporter_targets -- export target implementations (claude-code, mcp-server, etc.)
"""

import argparse
import json
import sys
from pathlib import Path


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Resolve project root
try:
    from src.config.paths import get_project_root
    PROJECT_ROOT = get_project_root()
except ImportError:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent  # fallback

# Valid export targets
VALID_TARGETS = {"claude-code", "mcp-server", "python-package", "tarball"}

# Re-export commonly used symbols for backward compatibility
from skill_exporter_parse import (  # noqa: E402, F401
    parse_skill_md,
    strip_augur_markers_from_frontmatter,
    strip_augur_references_from_body,
    generate_standard_frontmatter,
    generate_exported_skill_md,
    generate_agent_md,
    generate_tier_agents,
    generate_commands,
)

from skill_exporter_targets import (  # noqa: E402, F401
    copy_layer1_resources,
    detect_bundle,
    read_dashboard_yaml,
    generate_plugin_json,
    export_claude_code,
    export_mcp_server,
    export_python_package,
    export_tarball,
)

# Augur extension directories (Layer 2 -- stripped on export)
AUGUR_EXTENSION_DIRS = {
    "dashboard",
    "chains",
    "modules",
    "references",
    "mcp",
    "api",
    "schemas",
    "backlog",
    "lib",
    "config",
}

# Augur extension files (Layer 2 -- stripped on export)
AUGUR_EXTENSION_FILES = {
    "dashboard.yaml",
    "version.yaml",
    "package.json",
}


def export_skill(
    skill_path: Path,
    output_base: Path,
    target: str = "claude-code",
) -> Path:
    """Export a single Augur skill as an external package.

    Args:
        skill_path: Path to the Augur skill directory
        output_base: Base directory for exported plugins
        target: Export target format (claude-code, mcp-server, python-package)

    Returns:
        Path to the exported package directory
    """
    skill_path = Path(skill_path).resolve()
    output_base = Path(output_base)
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill directory not found: {skill_path}")

    if target not in VALID_TARGETS:
        raise ValueError(f"Invalid target: {target}. Must be one of: {VALID_TARGETS}")

    parsed = parse_skill_md(skill_path)

    if target == "claude-code":
        return export_claude_code(skill_path, parsed, output_base)
    elif target == "mcp-server":
        return export_mcp_server(skill_path, parsed, output_base)
    elif target == "python-package":
        return export_python_package(skill_path, parsed, output_base)
    elif target == "tarball":
        return export_tarball(skill_path, parsed, output_base)
    else:
        raise ValueError(f"Unknown target: {target}")


def discover_all_skills(exclude_dir: Path | None = None) -> list[tuple[str, str, Path]]:
    """Discover all skills from the canonical project-brain/capabilities/skills/ directory.

    Args:
        exclude_dir: If set, skip any skills found under this directory.

    Returns:
        List of (hub, skill_name, skill_path) tuples
    """
    try:
        from src.config.paths import _read_skill_frontmatter
    except ImportError:
        _read_skill_frontmatter = None

    skills = []
    skills_dir = PROJECT_ROOT / "project-brain" / "capabilities" / "skills"

    if not skills_dir.exists():
        return skills

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        if exclude_dir and skill_dir.is_relative_to(exclude_dir):
            continue
        if not (skill_dir / "SKILL.md").exists():
            continue
        hub = "unknown"
        if _read_skill_frontmatter:
            fm = _read_skill_frontmatter(skill_dir)
            if fm:
                hub = fm.get("x-augur-hub", "unknown")
        skills.append((hub, skill_dir.name, skill_dir))

    return skills


def main(params: dict | None = None):
    """CLI entry point and MCP script entry point."""
    if params and isinstance(params, dict):
        # Called from MCP as script module
        skill_path = params.get("skill_path", "")
        output = params.get("output")
        if not output:
            return {"error": "output is required"}
        target = params.get("target", "claude-code")
        if not skill_path:
            return {"error": "skill_path is required"}
        try:
            result_path = export_skill(Path(skill_path), Path(output), target)
            return {"success": True, "plugin_path": str(result_path), "target": target}
        except Exception as e:
            return {"error": str(e)}

    parser = argparse.ArgumentParser(description="Export Augur skills as external packages (ADR-040)")
    parser.add_argument("skill_path", nargs="?", help="Path to Augur skill directory")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output directory for exported plugins (required for --all)",
    )
    parser.add_argument(
        "--target",
        "-t",
        default="claude-code",
        choices=sorted(VALID_TARGETS),
        help="Export target format (default: claude-code)",
    )
    parser.add_argument(
        "--batch",
        nargs="+",
        help="Export multiple skills by name (searches all bundles)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Export ALL skills from all bundles",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON results")

    args = parser.parse_args()

    if args.all and not args.output:
        parser.error("--output is required when using --all")

    # Discover all skills for batch/all operations
    output_path = Path(args.output) if args.output else None
    all_skills = discover_all_skills(exclude_dir=output_path)

    if args.all:
        results = []
        for bundle, skill_name, skill_dir in all_skills:
            try:
                plugin_path = export_skill(skill_dir, Path(args.output), args.target)
                results.append(
                    {
                        "skill": skill_name,
                        "bundle": bundle,
                        "success": True,
                        "path": str(plugin_path),
                        "target": args.target,
                    }
                )
                if not args.json:
                    _out(f"  Exported {bundle}/{skill_name} -> {plugin_path}")
            except Exception as e:
                results.append(
                    {
                        "skill": skill_name,
                        "bundle": bundle,
                        "success": False,
                        "error": str(e),
                    }
                )
                if not args.json:
                    _out(f"  FAILED {bundle}/{skill_name}: {e}")

        if args.json:
            _out(json.dumps(results, indent=2))
        else:
            ok = sum(1 for r in results if r["success"])
            _out(f"\nExported {ok}/{len(results)} skills as {args.target}")
        return 0

    if args.batch:
        results = []
        for skill_name in args.batch:
            # Search across all bundles
            found = [(b, n, p) for b, n, p in all_skills if n == skill_name]
            if not found:
                results.append(
                    {
                        "skill": skill_name,
                        "success": False,
                        "error": "Skill not found in any bundle",
                    }
                )
                if not args.json:
                    _out(f"  NOT FOUND: {skill_name}")
                continue

            bundle, name, skill_dir = found[0]
            try:
                plugin_path = export_skill(skill_dir, Path(args.output), args.target)
                results.append(
                    {
                        "skill": skill_name,
                        "bundle": bundle,
                        "success": True,
                        "path": str(plugin_path),
                        "target": args.target,
                    }
                )
                if not args.json:
                    _out(f"  Exported {bundle}/{skill_name} -> {plugin_path}")
            except Exception as e:
                results.append(
                    {
                        "skill": skill_name,
                        "bundle": bundle,
                        "success": False,
                        "error": str(e),
                    }
                )
                if not args.json:
                    _out(f"  FAILED {skill_name}: {e}")

        if args.json:
            _out(json.dumps(results, indent=2))
        else:
            ok = sum(1 for r in results if r["success"])
            _out(f"\nExported {ok}/{len(results)} skills as {args.target}")
        return 0

    if args.skill_path:
        try:
            plugin_path = export_skill(Path(args.skill_path), Path(args.output), args.target)
            if args.json:
                _out(
                    json.dumps(
                        {
                            "success": True,
                            "path": str(plugin_path),
                            "target": args.target,
                        },
                        indent=2,
                    )
                )
            else:
                _out(f"Exported to: {plugin_path} (target: {args.target})")
                for f in sorted(plugin_path.rglob("*")):
                    if f.is_file():
                        rel = f.relative_to(plugin_path)
                        _out(f"  {rel}")
            return 0
        except Exception as e:
            if args.json:
                _out(json.dumps({"success": False, "error": str(e)}, indent=2))
            else:
                _out(f"ERROR: {e}")
            return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
