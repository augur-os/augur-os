"""Export target implementations for skill exporter.

Each function exports an Augur skill to a specific target format:
    export_claude_code    — .claude-plugin/ directory
    export_mcp_server     — standalone MCP server with server.py
    export_python_package — pyproject.toml + src/ layout
    export_tarball        — distributable .tar.gz archive

Also includes shared helpers:
    copy_layer1_resources — copy Layer 1 resources (scripts, tests, etc.)
    detect_bundle         — detect which bundle a skill belongs to
    read_dashboard_yaml   — read dashboard.yaml from a skill directory
    generate_plugin_json  — generate plugin.json manifest

Split from skill_exporter.py for module size management.
"""

from __future__ import annotations

import json
import shutil
import tarfile
from pathlib import Path
from typing import Any

try:
    from src.config.paths import get_project_root
    _ROOT_PREFIX = str(get_project_root()) + "/"
except Exception:  # pragma: no cover - fallback when src is not importable
    _ROOT_PREFIX = str(Path(__file__).resolve().parents[5]) + "/"

from skill_exporter_parse import (
    generate_agent_md,
    generate_commands,
    generate_exported_skill_md,
    generate_tier_agents,
)


def copy_layer1_resources(skill_path: Path, output_dir: Path):
    """Copy Layer 1 (Standard Core) resources only.

    Copies scripts/ and tests/ directories. Skips Layer 2 extension directories.
    Also copies modules/ and references/ as resources (useful context for agents).
    """
    # Copy scripts/ (Layer 1)
    scripts_dir = skill_path / "scripts"
    if scripts_dir.exists():
        target_dir = output_dir / "scripts"
        target_dir.mkdir(parents=True, exist_ok=True)
        for py_file in scripts_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            # Strip Augur-specific path references
            content = content.replace("plugins/data/", "")
            content = content.replace(_ROOT_PREFIX, "").replace("~/Projects/Augur/", "")
            (target_dir / py_file.name).write_text(content, encoding="utf-8")

    # Copy tests/ (Layer 1)
    tests_dir = skill_path / "tests"
    if tests_dir.exists():
        target_dir = output_dir / "tests"
        target_dir.mkdir(parents=True, exist_ok=True)
        for test_file in tests_dir.glob("*.py"):
            content = test_file.read_text(encoding="utf-8")
            (target_dir / test_file.name).write_text(content, encoding="utf-8")

    # Copy modules/ and references/ as agent resources (useful context)
    resources_dir = output_dir / "resources"
    for subdir_name in ["modules", "references"]:
        source_dir = skill_path / subdir_name
        if source_dir.exists():
            target_dir = resources_dir / subdir_name
            target_dir.mkdir(parents=True, exist_ok=True)
            for md_file in source_dir.glob("*.md"):
                content = md_file.read_text(encoding="utf-8")
                content = content.replace("plugins/data/", "")
                content = content.replace(_ROOT_PREFIX, "").replace("~/Projects/Augur/", "")
                (target_dir / md_file.name).write_text(content, encoding="utf-8")

    # Copy requirements.txt if it exists (Layer 1)
    req_file = skill_path / "requirements.txt"
    if req_file.exists():
        shutil.copy2(req_file, output_dir / "requirements.txt")


def detect_bundle(skill_path: Path) -> str:
    """Detect which bundle a skill belongs to by reading x-augur-hub from SKILL.md frontmatter."""
    try:
        from src.config.paths import _read_skill_frontmatter
        fm = _read_skill_frontmatter(skill_path)
        return fm.get("x-augur-hub", "unknown") if fm else "unknown"
    except ImportError:
        return "unknown"


def read_dashboard_yaml(skill_path: Path) -> dict[str, Any]:
    """Read dashboard.yaml from a skill directory and return parsed config."""
    dash_yaml = skill_path / "dashboard.yaml"
    if not dash_yaml.exists():
        return {}
    try:
        import yaml

        return yaml.safe_load(dash_yaml.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def generate_plugin_json(skill_path: Path, parsed: dict[str, Any]) -> dict[str, Any]:
    """Generate a plugin.json manifest with metadata and dependencies.

    Reads SKILL.md frontmatter for name/version/description and
    dashboard.yaml for dependency declarations.
    """
    fm = parsed["frontmatter"]
    name = fm.get("name", skill_path.name)
    version = fm.get("version", "1.0.0")
    description = fm.get("description", "")
    bundle = detect_bundle(skill_path)

    # Read dependencies from dashboard.yaml
    dash_config = read_dashboard_yaml(skill_path)
    deps = dash_config.get("dependencies", {})
    required = deps.get("required", [])
    optional = deps.get("optional", [])

    # Read hub info
    hub = dash_config.get("hub", {})

    manifest: dict[str, Any] = {
        "name": name,
        "version": version,
        "description": description,
        "bundle": bundle,
        "hub": hub.get("id", name) if hub else name,
        "dependencies": {
            "required": required,
            "optional": optional,
        },
    }

    return manifest


def export_claude_code(skill_path: Path, parsed: dict[str, Any], output_base: Path) -> Path:
    """Export as a Claude Code plugin (.claude-plugin/ structure)."""
    fm = parsed["frontmatter"]
    name = fm.get("name", skill_path.name)

    plugin_dir = output_base / f"augur-{name}"

    # Clean previous export
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)

    # Create structure
    (plugin_dir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (plugin_dir / "skills" / name).mkdir(parents=True, exist_ok=True)
    (plugin_dir / "agents").mkdir(parents=True, exist_ok=True)
    (plugin_dir / "commands").mkdir(parents=True, exist_ok=True)

    # 1. Plugin manifest
    manifest = {
        "name": f"augur-{name}",
        "description": fm.get("description", f"Augur {name} agent"),
        "version": fm.get("version", "1.0.0"),
        "author": {"name": "Augur"},
    }
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # 2. plugin.json with dependencies
    plugin_manifest = generate_plugin_json(skill_path, parsed)
    (plugin_dir / "plugin.json").write_text(json.dumps(plugin_manifest, indent=2), encoding="utf-8")

    # 3. Skill SKILL.md (Layer 1 only)
    skill_md_content = generate_exported_skill_md(parsed)
    (plugin_dir / "skills" / name / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

    # 4. Agent definition (default + per-tier variants)
    agent_md = generate_agent_md(parsed)
    (plugin_dir / "agents" / f"{name}.md").write_text(agent_md, encoding="utf-8")

    tier_agents = generate_tier_agents(parsed)
    for tier_slug, tier_content in tier_agents.items():
        (plugin_dir / "agents" / f"{tier_slug}.md").write_text(tier_content, encoding="utf-8")

    # 5. Commands from triggers
    commands = generate_commands(parsed)
    for cmd_slug, cmd_content in commands.items():
        (plugin_dir / "commands" / f"{cmd_slug}.md").write_text(cmd_content, encoding="utf-8")

    # 6. Copy Layer 1 resources
    copy_layer1_resources(skill_path, plugin_dir / "skills" / name)

    # 7. README
    bundle = detect_bundle(skill_path)
    triggers = fm.get("triggers", [])
    trigger_lines = [f"- `/augur-{name}:{t.replace(' ', '-')}`" for t in triggers[:5]]
    triggers_str = "\n".join(trigger_lines)
    readme = f"""# Augur {name.title()} Plugin

{fm.get('description', '')}

## Installation

```bash
claude --plugin-dir ./augur-{name}
```

Or add to a marketplace and install:
```bash
/plugin install augur-{name}
```

## Available Commands

{triggers_str}

## Skills

This plugin provides the `{name}` skill which Claude will automatically use
when tasks match its capabilities.

## Agent

The `{name}` agent is available for specialized tasks.

---
Exported from Augur {bundle} skill: `{skill_path.name}`
"""
    (plugin_dir / "README.md").write_text(readme, encoding="utf-8")

    return plugin_dir


def export_mcp_server(skill_path: Path, parsed: dict[str, Any], output_base: Path) -> Path:
    """Export as a standalone MCP server."""
    fm = parsed["frontmatter"]
    name = fm.get("name", skill_path.name)
    description = fm.get("description", "")
    version = fm.get("version", "1.0.0")

    server_dir = output_base / f"augur-{name}-mcp"

    if server_dir.exists():
        shutil.rmtree(server_dir)

    server_dir.mkdir(parents=True, exist_ok=True)

    # 1. plugin.json with dependencies
    plugin_manifest = generate_plugin_json(skill_path, parsed)
    (server_dir / "plugin.json").write_text(json.dumps(plugin_manifest, indent=2), encoding="utf-8")

    # 2. SKILL.md (Layer 1 only)
    skill_md_content = generate_exported_skill_md(parsed)
    (server_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

    # 3. Copy Layer 1 resources
    copy_layer1_resources(skill_path, server_dir)

    # 4. Generate server.py stub
    server_py = f'''#!/usr/bin/env python3
"""
Standalone MCP server for {name}.

Exported from Augur skill: {skill_path.name}
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("{name}", description="{description}")


# TODO: Register your tools here
# @mcp.tool()
# def example_tool(param: str) -> str:
#     """Example tool description."""
#     return "result"


if __name__ == "__main__":
    mcp.run()
'''
    (server_dir / "server.py").write_text(server_py, encoding="utf-8")

    # 5. Requirements
    req_content = "mcp>=1.0.0\n"
    existing_req = skill_path / "requirements.txt"
    if existing_req.exists():
        req_content += existing_req.read_text(encoding="utf-8")
    (server_dir / "requirements.txt").write_text(req_content, encoding="utf-8")

    # 6. README
    readme = f"""# {name} MCP Server

{description}

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python server.py
```

## Configuration

Add to your MCP client configuration:

```json
{{
    "mcpServers": {{
        "{name}": {{
            "command": "python",
            "args": ["server.py"]
        }}
    }}
}}
```

---
Exported from Augur skill: `{skill_path.name}` v{version}
"""
    (server_dir / "README.md").write_text(readme, encoding="utf-8")

    return server_dir


def export_python_package(skill_path: Path, parsed: dict[str, Any], output_base: Path) -> Path:
    """Export as a Python package with pyproject.toml."""
    fm = parsed["frontmatter"]
    name = fm.get("name", skill_path.name)
    description = fm.get("description", "")
    version = fm.get("version", "1.0.0")

    pkg_name = name.replace("-", "_")
    pkg_dir = output_base / f"augur-{name}"

    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)

    (pkg_dir / "src" / pkg_name).mkdir(parents=True, exist_ok=True)

    # 1. pyproject.toml
    deps = fm.get("dependencies", {}).get("python", [])
    deps_str = ", ".join(f'"{d}"' for d in deps)

    pyproject = f"""[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "augur-{name}"
version = "{version}"
description = "{description}"
requires-python = ">=3.11"
dependencies = [{deps_str}]

[project.urls]
Homepage = "https://github.com/augur/augur-{name}"
"""
    (pkg_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")

    # 2. plugin.json with dependencies
    plugin_manifest = generate_plugin_json(skill_path, parsed)
    (pkg_dir / "plugin.json").write_text(json.dumps(plugin_manifest, indent=2), encoding="utf-8")

    # 3. __init__.py
    (pkg_dir / "src" / pkg_name / "__init__.py").write_text(
        f'"""Augur {name} package."""\n\n__version__ = "{version}"\n',
        encoding="utf-8",
    )

    # 4. Copy scripts as modules
    scripts_dir = skill_path / "scripts"
    if scripts_dir.exists():
        for py_file in scripts_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            content = py_file.read_text(encoding="utf-8")
            content = content.replace("plugins/data/", "")
            content = content.replace(_ROOT_PREFIX, "").replace("~/Projects/Augur/", "")
            (pkg_dir / "src" / pkg_name / py_file.name).write_text(content, encoding="utf-8")

    # 5. SKILL.md and README
    skill_md_content = generate_exported_skill_md(parsed)
    (pkg_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")
    (pkg_dir / "README.md").write_text(
        f"# augur-{name}\n\n{description}\n\nExported from Augur skill: `{skill_path.name}`\n",
        encoding="utf-8",
    )

    return pkg_dir


def export_tarball(skill_path: Path, parsed: dict[str, Any], output_base: Path) -> Path:
    """Export as a distributable tarball (.tar.gz) with plugin.json manifest.

    Output: dist/plugins/{name}-{version}.tar.gz containing:
      - plugin.json (manifest with dependencies)
      - SKILL.md (Layer 1 only)
      - scripts/, tests/ (Layer 1 resources)
      - dashboard.yaml (if present)
      - requirements.txt (if present)
    """
    fm = parsed["frontmatter"]
    name = fm.get("name", skill_path.name)
    version = fm.get("version", "1.0.0")

    # Build in a temp directory, then tar it
    staging_dir = output_base / f"{name}-{version}"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    # 1. plugin.json manifest
    manifest = generate_plugin_json(skill_path, parsed)
    (staging_dir / "plugin.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # 2. SKILL.md (Layer 1 only)
    skill_md_content = generate_exported_skill_md(parsed)
    (staging_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

    # 3. Copy Layer 1 resources (scripts, tests, modules, references, requirements.txt)
    copy_layer1_resources(skill_path, staging_dir)

    # 4. Copy dashboard.yaml (needed for hub mounting on install)
    dash_yaml = skill_path / "dashboard.yaml"
    if dash_yaml.exists():
        shutil.copy2(dash_yaml, staging_dir / "dashboard.yaml")

    # 5. Copy dashboard/ directory (UI components for mounting)
    dash_dir = skill_path / "dashboard"
    if dash_dir.exists():
        shutil.copytree(dash_dir, staging_dir / "dashboard")

    # 6. Create tarball
    dist_dir = output_base / "dist" / "plugins"
    dist_dir.mkdir(parents=True, exist_ok=True)
    tarball_path = dist_dir / f"{name}-{version}.tar.gz"

    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(staging_dir, arcname=f"{name}-{version}")

    # Clean up staging directory
    shutil.rmtree(staging_dir)

    return tarball_path
