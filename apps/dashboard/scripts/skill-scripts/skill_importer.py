#!/usr/bin/env python3
"""
Skill Importer - Import external plugins into Augur.

Supports importing from:
    - Local directories (plugin folder structure)
    - Zip files (compressed plugins)
    - Hidden folders (.claude-plugins, .cursor/plugins, etc.)
    - Common agent directories (~/.claude/plugins, ~/.cursor/agents, etc.)

Usage:
    python skill_importer.py                           # Interactive mode
    python skill_importer.py /path/to/plugin           # Import from path
    python skill_importer.py plugin.zip                # Import from zip
    python skill_importer.py --scan                    # Scan for plugins to import
    python skill_importer.py --list-sources            # List common plugin sources
"""
# TODO_CLEANUP: This file is 829 lines — consider splitting into smaller modules

import argparse
import json
import os
import shutil
import sys
import tempfile
import warnings
import zipfile
from pathlib import Path
from typing import Any, Optional


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

# Common plugin source locations
COMMON_PLUGIN_SOURCES = [
    # Claude Code
    ("~/.claude/plugins", "Claude Code plugins"),
    ("~/.claude-plugins", "Claude Code hidden plugins"),
    # Cursor
    ("~/.cursor/plugins", "Cursor plugins"),
    ("~/.cursor/agents", "Cursor agents"),
    # VS Code
    ("~/.vscode/extensions", "VS Code extensions"),
    # Generic
    ("~/Desktop/plugins", "Desktop plugins folder"),
    ("~/Downloads", "Downloads folder (for zip imports)"),
    # Project-local
    (".claude-plugins", "Project-local Claude plugins"),
    (".cursor/plugins", "Project-local Cursor plugins"),
]

# Target bundle for imports (default).
# Track 3b: this is the plugin BUNDLE name (skill distribution group),
# NOT a hub id from config/system/hubs.yaml. Hubs live in the dashboard
# navigation surface; bundles group skills for plugin packaging.
# See apps/dashboard/scripts/skill-scripts/skill_generation/hubs_loader.py
# for hub-id resolution; this constant is unrelated.
DEFAULT_TARGET_BUNDLE = "lifestyle"


def expand_path(path: str) -> Path:
    """Expand ~ and environment variables in path."""
    return Path(os.path.expanduser(os.path.expandvars(path)))


def detect_plugin_type(source_path: Path) -> Optional[str]:
    """Detect the type of plugin at the given path.

    Returns:
        Plugin type: 'claude-code', 'mcp-server', 'python-package', 'skill-only', or None
    """
    if not source_path.exists():
        return None

    # Check for Claude Code plugin structure
    if (source_path / ".claude-plugin").is_dir():
        return "claude-code"
    if (source_path / ".claude-plugin" / "plugin.json").exists():
        return "claude-code"
    if (source_path / "plugin.json").exists():
        return "claude-code"

    # Check for MCP server
    if (source_path / "server.py").exists():
        return "mcp-server"

    # Check for Python package
    if (source_path / "pyproject.toml").exists():
        return "python-package"

    # Check for SKILL.md (raw skill)
    if (source_path / "SKILL.md").exists():
        return "skill-only"

    # Check for skills/ subdirectory with SKILL.md
    skills_dir = source_path / "skills"
    if skills_dir.is_dir():
        for skill_dir in skills_dir.iterdir():
            if (skill_dir / "SKILL.md").exists():
                return "claude-code"

    return None


def parse_plugin_manifest(source_path: Path) -> dict[str, Any]:
    """Parse plugin manifest to extract metadata."""
    manifest = {
        "name": source_path.name,
        "description": "",
        "version": "1.0.0",
        "author": "",
    }

    # Try .claude-plugin/plugin.json
    plugin_json = source_path / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        plugin_json = source_path / "plugin.json"

    if plugin_json.exists():
        try:
            data = json.loads(plugin_json.read_text(encoding="utf-8"))
            manifest["name"] = data.get("name", manifest["name"])
            manifest["description"] = data.get("description", "")
            manifest["version"] = data.get("version", "1.0.0")
            if isinstance(data.get("author"), dict):
                manifest["author"] = data["author"].get("name", "")
            else:
                manifest["author"] = data.get("author", "")
        except Exception as e:
            warnings.warn(
                f"Unable to parse plugin manifest {plugin_json}: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

    # Try SKILL.md for additional info
    skill_md = source_path / "SKILL.md"
    if not skill_md.exists():
        # Check in skills/ subdirectory
        skills_dir = source_path / "skills"
        if skills_dir.is_dir():
            for skill_dir in skills_dir.iterdir():
                if (skill_dir / "SKILL.md").exists():
                    skill_md = skill_dir / "SKILL.md"
                    break

    if skill_md.exists():
        try:
            content = skill_md.read_text(encoding="utf-8")
            if content.startswith("---"):
                import yaml

                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    if frontmatter:
                        manifest["name"] = frontmatter.get("name", manifest["name"])
                        manifest["description"] = frontmatter.get("description", manifest["description"])
                        manifest["version"] = frontmatter.get("version", manifest["version"])
        except Exception as e:
            warnings.warn(
                f"Unable to parse SKILL metadata from {skill_md}: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

    return manifest


def extract_zip(zip_path: Path, extract_to: Path) -> Path:
    """Extract zip file and return path to extracted content."""
    extract_to.mkdir(parents=True, exist_ok=True)
    extract_root = extract_to.resolve()

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            member_path = Path(member.filename)

            # Reject dangerous archive entries before extraction.
            if not member.filename or member_path.is_absolute() or member_path.drive or ".." in member_path.parts:
                raise ValueError(f"Unsafe ZIP member path: {member.filename!r}")

            # Reject symlinks in ZIP archives.
            mode = (member.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(f"ZIP symlink entries are not allowed: {member.filename!r}")

            target_path = (extract_root / member_path).resolve()
            if target_path != extract_root and extract_root not in target_path.parents:
                raise ValueError(f"ZIP member escapes extraction directory: {member.filename!r}")

            zf.extract(member, path=extract_root)

    # Find the actual plugin directory (might be nested)
    items = list(extract_to.iterdir())
    if len(items) == 1 and items[0].is_dir():
        return items[0]
    return extract_to


def convert_to_augur_skill(
    source_path: Path,
    plugin_type: str,
    manifest: dict[str, Any],
    target_bundle: str = DEFAULT_TARGET_BUNDLE,
) -> dict[str, Any]:
    """Convert external plugin to Augur skill structure.

    Returns dict with skill info and file mappings.
    """
    # Normalize name to kebab-case
    name = manifest["name"]
    if name.startswith("augur-"):
        name = name[6:]  # Remove augur- prefix
    name = name.lower().replace("_", "-").replace(" ", "-")

    # Target skill directory
    target_dir = PROJECT_ROOT / "plugins" / target_bundle / "skills" / name

    result = {
        "name": name,
        "source_type": plugin_type,
        "source_path": str(source_path),
        "target_path": str(target_dir),
        "manifest": manifest,
        "files_to_copy": [],
        "files_to_generate": [],
    }

    if plugin_type == "claude-code":
        # Map Claude Code plugin structure to Augur
        skills_dir = source_path / "skills"
        if skills_dir.is_dir():
            for skill_dir in skills_dir.iterdir():
                if (skill_dir / "SKILL.md").exists():
                    result["files_to_copy"].append(
                        {
                            "src": str(skill_dir / "SKILL.md"),
                            "dst": "SKILL.md",
                        }
                    )
                    # Copy scripts if present
                    if (skill_dir / "scripts").is_dir():
                        for script in (skill_dir / "scripts").glob("*.py"):
                            result["files_to_copy"].append(
                                {
                                    "src": str(script),
                                    "dst": f"scripts/{script.name}",
                                }
                            )
                    # Copy tests if present
                    if (skill_dir / "tests").is_dir():
                        for test in (skill_dir / "tests").glob("*.py"):
                            result["files_to_copy"].append(
                                {
                                    "src": str(test),
                                    "dst": f"tests/{test.name}",
                                }
                            )
                    # Copy resources (modules, references)
                    if (skill_dir / "resources").is_dir():
                        for res_type in ["modules", "references"]:
                            res_dir = skill_dir / "resources" / res_type
                            if res_dir.is_dir():
                                for md_file in res_dir.glob("*.md"):
                                    result["files_to_copy"].append(
                                        {
                                            "src": str(md_file),
                                            "dst": f"{res_type}/{md_file.name}",
                                        }
                                    )

        # Copy agents as reference
        agents_dir = source_path / "agents"
        if agents_dir.is_dir():
            for agent_file in agents_dir.glob("*.md"):
                result["files_to_copy"].append(
                    {
                        "src": str(agent_file),
                        "dst": f"references/{agent_file.name}",
                    }
                )

    elif plugin_type == "mcp-server":
        # MCP server - copy server.py to scripts
        if (source_path / "server.py").exists():
            result["files_to_copy"].append(
                {
                    "src": str(source_path / "server.py"),
                    "dst": "scripts/server.py",
                }
            )
        if (source_path / "SKILL.md").exists():
            result["files_to_copy"].append(
                {
                    "src": str(source_path / "SKILL.md"),
                    "dst": "SKILL.md",
                }
            )
        else:
            # Generate SKILL.md
            result["files_to_generate"].append(
                {
                    "dst": "SKILL.md",
                    "content": generate_skill_md(manifest),
                }
            )
        if (source_path / "requirements.txt").exists():
            result["files_to_copy"].append(
                {
                    "src": str(source_path / "requirements.txt"),
                    "dst": "requirements.txt",
                }
            )

    elif plugin_type == "python-package":
        # Python package - copy src/ to scripts/
        src_dir = source_path / "src"
        if src_dir.is_dir():
            for py_file in src_dir.rglob("*.py"):
                rel_path = py_file.relative_to(src_dir)
                result["files_to_copy"].append(
                    {
                        "src": str(py_file),
                        "dst": f"scripts/{rel_path}",
                    }
                )
        if (source_path / "SKILL.md").exists():
            result["files_to_copy"].append(
                {
                    "src": str(source_path / "SKILL.md"),
                    "dst": "SKILL.md",
                }
            )
        else:
            result["files_to_generate"].append(
                {
                    "dst": "SKILL.md",
                    "content": generate_skill_md(manifest),
                }
            )

    elif plugin_type == "skill-only":
        # Raw skill - just copy SKILL.md and any scripts
        result["files_to_copy"].append(
            {
                "src": str(source_path / "SKILL.md"),
                "dst": "SKILL.md",
            }
        )
        if (source_path / "scripts").is_dir():
            for script in (source_path / "scripts").glob("*.py"):
                result["files_to_copy"].append(
                    {
                        "src": str(script),
                        "dst": f"scripts/{script.name}",
                    }
                )

    # Always generate dashboard.yaml if not present
    result["files_to_generate"].append(
        {
            "dst": "dashboard.yaml",
            "content": generate_dashboard_yaml(name, manifest),
        }
    )

    return result


def generate_skill_md(manifest: dict[str, Any]) -> str:
    """Generate a SKILL.md from manifest data."""
    return f"""---
name: {manifest['name']}
version: {manifest['version']}
description: {manifest['description']}
category: imported
triggers: []
---

# {manifest['name'].replace('-', ' ').title()}

{manifest['description']}

## Overview

This skill was imported from an external plugin.

## Capabilities

- Imported functionality (see scripts/ for implementation)

---
Version: {manifest['version']} | Imported
"""


def generate_dashboard_yaml(name: str, manifest: dict[str, Any]) -> str:
    """Generate a dashboard.yaml for the imported skill."""
    return f"""# Dashboard configuration for {name}
# Auto-generated during import

hub_id: imported
display_name: {name.replace('-', ' ').title()}
description: {manifest['description']}
icon: Package
color: slate

tabs: []

actions: []
"""


def execute_import(
    import_plan: dict[str, Any],
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Execute the import plan.

    Args:
        import_plan: Plan from convert_to_augur_skill
        dry_run: If True, don't actually copy files
        overwrite: If True, overwrite existing skill

    Returns:
        Result dict with success status and details
    """
    target_path = Path(import_plan["target_path"])

    # Check if already exists
    if target_path.exists() and not overwrite:
        return {
            "success": False,
            "error": f"Skill already exists at {target_path}. Use --overwrite to replace.",
            "existing_path": str(target_path),
        }

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "would_create": str(target_path),
            "files_to_copy": len(import_plan["files_to_copy"]),
            "files_to_generate": len(import_plan["files_to_generate"]),
        }

    try:
        # Remove existing if overwrite
        if target_path.exists() and overwrite:
            shutil.rmtree(target_path)

        # Create target directory
        target_path.mkdir(parents=True, exist_ok=True)

        # Copy files
        copied_files = []
        for file_spec in import_plan["files_to_copy"]:
            src = Path(file_spec["src"])
            dst = target_path / file_spec["dst"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied_files.append(file_spec["dst"])

        # Generate files
        generated_files = []
        for file_spec in import_plan["files_to_generate"]:
            dst = target_path / file_spec["dst"]
            # Don't overwrite if already copied
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(file_spec["content"], encoding="utf-8")
                generated_files.append(file_spec["dst"])

        return {
            "success": True,
            "skill_name": import_plan["name"],
            "target_path": str(target_path),
            "copied_files": copied_files,
            "generated_files": generated_files,
            "source_type": import_plan["source_type"],
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def scan_for_plugins() -> list[dict[str, Any]]:
    """Scan common locations for importable plugins."""
    found = []

    for source_pattern, description in COMMON_PLUGIN_SOURCES:
        source_path = expand_path(source_pattern)

        if not source_path.exists():
            continue

        # Check if the path itself is a plugin
        plugin_type = detect_plugin_type(source_path)
        if plugin_type:
            manifest = parse_plugin_manifest(source_path)
            found.append(
                {
                    "path": str(source_path),
                    "type": plugin_type,
                    "name": manifest["name"],
                    "description": manifest["description"],
                    "source": description,
                }
            )
            continue

        # Scan subdirectories
        if source_path.is_dir():
            for item in source_path.iterdir():
                if not item.is_dir():
                    # Check for zip files
                    if item.suffix == ".zip":
                        found.append(
                            {
                                "path": str(item),
                                "type": "zip",
                                "name": item.stem,
                                "description": "Compressed plugin",
                                "source": description,
                            }
                        )
                    continue

                plugin_type = detect_plugin_type(item)
                if plugin_type:
                    manifest = parse_plugin_manifest(item)
                    found.append(
                        {
                            "path": str(item),
                            "type": plugin_type,
                            "name": manifest["name"],
                            "description": manifest["description"],
                            "source": description,
                        }
                    )

    return found


def import_plugin(
    source: str,
    target_bundle: str = DEFAULT_TARGET_BUNDLE,
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Import a plugin from the given source.

    Args:
        source: Path to plugin directory or zip file
        target_bundle: Augur bundle to import into (apps, services, crew)
        dry_run: If True, don't actually import
        overwrite: If True, overwrite existing skill

    Returns:
        Import result dict
    """
    source_path = expand_path(source)
    temp_dir = None

    try:
        # Handle zip files
        if source_path.suffix == ".zip":
            if not source_path.exists():
                return {"success": False, "error": f"Zip file not found: {source}"}
            temp_dir = Path(tempfile.mkdtemp())
            source_path = extract_zip(source_path, temp_dir)

        if not source_path.exists():
            return {"success": False, "error": f"Source not found: {source}"}

        # Detect plugin type
        plugin_type = detect_plugin_type(source_path)
        if not plugin_type:
            return {
                "success": False,
                "error": f"Could not detect plugin type at: {source}",
                "hint": "Expected .claude-plugin/, SKILL.md, server.py, or pyproject.toml",
            }

        # Parse manifest
        manifest = parse_plugin_manifest(source_path)

        # Create import plan
        import_plan = convert_to_augur_skill(source_path, plugin_type, manifest, target_bundle)

        # Execute import
        result = execute_import(import_plan, dry_run=dry_run, overwrite=overwrite)
        result["manifest"] = manifest
        result["import_plan"] = {
            "files_to_copy": len(import_plan["files_to_copy"]),
            "files_to_generate": len(import_plan["files_to_generate"]),
        }

        return result

    finally:
        # Cleanup temp directory
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir)


def interactive_import() -> dict[str, Any]:
    """Run interactive import wizard."""
    _out("\n=== Augur Skill Importer ===\n")

    # Scan for plugins
    _out("Scanning for importable plugins...")
    found = scan_for_plugins()

    if found:
        _out(f"\nFound {len(found)} plugin(s):\n")
        for i, plugin in enumerate(found, 1):
            _out(f"  {i}. [{plugin['type']}] {plugin['name']}")
            _out(f"     Path: {plugin['path']}")
            _out(f"     Source: {plugin['source']}")
            if plugin['description']:
                _out(f"     Description: {plugin['description'][:60]}...")
            _out()

        _out("  0. Enter custom path")
        _out()

        try:
            choice = input("Select plugin to import (number): ").strip()
            if choice == "0":
                source = input("Enter path to plugin or zip file: ").strip()
            else:
                idx = int(choice) - 1
                if 0 <= idx < len(found):
                    source = found[idx]["path"]
                else:
                    return {"success": False, "error": "Invalid selection"}
        except (ValueError, EOFError):
            return {"success": False, "error": "Invalid input"}
    else:
        _out("No plugins found in common locations.\n")
        try:
            source = input("Enter path to plugin or zip file: ").strip()
        except EOFError:
            return {"success": False, "error": "No input provided"}

    if not source:
        return {"success": False, "error": "No source provided"}

    # Ask for target bundle
    _out("\nTarget bundle:")
    _out("  1. lifestyle (default - user-facing personal skills)")
    _out("  2. ai (AI/integration capabilities)")
    _out("  3. dev (dev/build tools)")

    try:
        bundle_choice = input("Select bundle [1]: ").strip() or "1"
        bundle_map = {"1": "lifestyle", "2": "ai", "3": "dev"}
        target_bundle = bundle_map.get(bundle_choice, "lifestyle")
    except EOFError:
        target_bundle = "lifestyle"

    # Ask for overwrite
    try:
        overwrite = input("Overwrite if exists? [y/N]: ").strip().lower() == "y"
    except EOFError:
        overwrite = False

    # Dry run first
    _out("\nAnalyzing plugin...")
    result = import_plugin(source, target_bundle, dry_run=True)

    if not result.get("success"):
        return result

    _out(f"\nWill import: {result.get('would_create', 'unknown')}")
    _out(f"  Files to copy: {result.get('files_to_copy', 0)}")
    _out(f"  Files to generate: {result.get('files_to_generate', 0)}")

    try:
        confirm = input("\nProceed with import? [Y/n]: ").strip().lower()
        if confirm and confirm != "y":
            return {"success": False, "error": "Import cancelled by user"}
    except EOFError:
        pass

    # Execute import
    _out("\nImporting...")
    result = import_plugin(source, target_bundle, dry_run=False, overwrite=overwrite)

    if result.get("success"):
        _out(f"\n✓ Successfully imported '{result.get('skill_name')}' to {result.get('target_path')}")
        _out(f"  Copied: {len(result.get('copied_files', []))} files")
        _out(f"  Generated: {len(result.get('generated_files', []))} files")
    else:
        _out(f"\n✗ Import failed: {result.get('error')}")

    return result


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Import external plugins into Augur",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python skill_importer.py                           # Interactive mode
    python skill_importer.py /path/to/plugin           # Import from directory
    python skill_importer.py plugin.zip                # Import from zip
    python skill_importer.py --scan                    # Scan for plugins
    python skill_importer.py --list-sources            # List search locations
    python skill_importer.py /path --bundle services   # Import to services bundle
""",
    )
    parser.add_argument("source", nargs="?", help="Path to plugin directory or zip file")
    parser.add_argument(
        "--bundle",
        "-b",
        default=DEFAULT_TARGET_BUNDLE,
        choices=[
            "core",
            "career",
            "growth",
            "finance",
            "health",
            "productivity",
            "integrations",
            "lifestyle",
            "creative",
            "home",
            "consulting",
            "venture",
            "enterprise",
            "ai",
            "admin",
            "observe",
            "dev",
        ],
        help=f"Target Augur bundle (default: {DEFAULT_TARGET_BUNDLE})",
    )
    parser.add_argument("--overwrite", "-f", action="store_true", help="Overwrite existing skill")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Show what would be imported")
    parser.add_argument("--scan", "-s", action="store_true", help="Scan for importable plugins")
    parser.add_argument("--list-sources", "-l", action="store_true", help="List plugin source locations")
    parser.add_argument("--json", action="store_true", help="Output JSON results")

    args = parser.parse_args()

    # List sources
    if args.list_sources:
        _out("\nCommon plugin source locations:\n")
        for pattern, description in COMMON_PLUGIN_SOURCES:
            path = expand_path(pattern)
            exists = "✓" if path.exists() else "✗"
            _out(f"  {exists} {pattern}")
            _out(f"    {description}")
            _out()
        return 0

    # Scan mode
    if args.scan:
        found = scan_for_plugins()
        if args.json:
            _out(json.dumps({"success": True, "plugins": found}, indent=2))
        else:
            if found:
                _out(f"\nFound {len(found)} importable plugin(s):\n")
                for plugin in found:
                    _out(f"  [{plugin['type']}] {plugin['name']}")
                    _out(f"    Path: {plugin['path']}")
                    _out(f"    Source: {plugin['source']}")
                    if plugin['description']:
                        _out(f"    Description: {plugin['description'][:60]}...")
                    _out()
            else:
                _out("\nNo plugins found in common locations.")
                _out("Use --list-sources to see searched locations.")
        return 0

    # Interactive mode if no source provided
    if not args.source:
        result = interactive_import()
        if args.json:
            _out(json.dumps(result, indent=2))
        return 0 if result.get("success") else 1

    # Direct import
    result = import_plugin(
        args.source,
        target_bundle=args.bundle,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
    )

    if args.json:
        _out(json.dumps(result, indent=2))
    else:
        if result.get("success"):
            if args.dry_run:
                _out(f"Would import to: {result.get('would_create')}")
                _out(f"  Files to copy: {result.get('files_to_copy', 0)}")
                _out(f"  Files to generate: {result.get('files_to_generate', 0)}")
            else:
                _out(f"✓ Successfully imported '{result.get('skill_name')}'")
                _out(f"  Target: {result.get('target_path')}")
                _out(f"  Copied: {len(result.get('copied_files', []))} files")
                _out(f"  Generated: {len(result.get('generated_files', []))} files")
        else:
            _out(f"✗ Import failed: {result.get('error')}")
            if result.get("hint"):
                _out(f"  Hint: {result.get('hint')}")

    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
