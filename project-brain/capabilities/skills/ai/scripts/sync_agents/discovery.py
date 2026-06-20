"""
sync_agents/discovery.py

Claude plugin discovery and bidirectional sync functions.

ADR-186: Extracted from monolithic sync_agents.py.
ADR-252: Command export removed — skills are auto-discovered from plugins/.
Handles frontmatter parsing and the full ADR-171 bidirectional plugin sync
surface (discover/assemble/resolve/distribute).
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
import json
import os
import shutil
from pathlib import Path

from . import constants as _constants_mod
from .constants import (
    PROJECT_ROOT,
    HEADER_TEMPLATE,
    _CLAUDE_ONLY_FIELDS,
    GENERATED_FILES,
    logger,
)

# External lib imports (already on sys.path via constants.py)
from src.lib.generated_artifacts import write_stable_json


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------


def strip_claude_frontmatter_fields(content: str) -> str:
    """Strip Claude-specific fields from YAML frontmatter while keeping IDE-agnostic ones.

    Removes fields like ``context`` and ``agent`` (which only Claude Code uses for
    fork/dispatch behaviour) but preserves ``name``, ``description``, ``visibility``,
    ``allowed-tools``, ``license``, ``metadata``, etc.

    If the frontmatter becomes empty after stripping, the entire frontmatter block is
    removed (equivalent to ``strip_yaml_frontmatter``).

    Args:
        content: Markdown content potentially with YAML frontmatter.

    Returns:
        Content with Claude-only fields removed from frontmatter.
    """
    if not content.startswith("---"):
        return content

    lines = content.splitlines()
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return content

    # Parse frontmatter lines, filtering out Claude-only fields
    kept_lines: list[str] = []
    for line in lines[1:end_idx]:
        # Check if the line starts a top-level key (not indented / nested)
        stripped = line.lstrip()
        if stripped == line and ":" in stripped:
            key = stripped.split(":", 1)[0].strip()
            if key in _CLAUDE_ONLY_FIELDS:
                continue
        kept_lines.append(line)

    body = "\n".join(lines[end_idx + 1:]).lstrip("\n")

    # If no meaningful fields remain, just return the body
    if not any(ln.strip() for ln in kept_lines):
        return body

    # Reconstruct with filtered frontmatter
    return "---\n" + "\n".join(kept_lines) + "\n---\n" + body


# --- Phase 3: Bidirectional Plugin Sync (ADR-171) ---


def _parse_md_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from a markdown file into a dict.

    Handles simple key: value pairs (no nested YAML). Returns empty dict
    if no frontmatter found.
    """
    if not content.startswith("---"):
        return {}

    lines = content.splitlines()
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}

    result = {}
    for line in lines[1:end_idx]:
        if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def discover_claude_plugins(cache_dir: Path) -> list[dict]:
    """Scan installed Claude Code plugins and extract metadata (ADR-171).

    Args:
        cache_dir: Path to ~/.claude/plugins/cache/claude-plugins-official/

    Returns:
        List of plugin dicts with keys: name, description, version_dir, agents, skills, commands
    """
    plugins = []

    if not cache_dir.exists():
        logger.info(f"Claude plugin cache not found: {cache_dir}")
        return plugins

    for plugin_dir in sorted(cache_dir.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
            continue

        # Each plugin has exactly one version subdirectory
        version_dirs = [d for d in plugin_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if not version_dirs:
            logger.warning(f"No version directory in plugin {plugin_dir.name}")
            continue

        version_dir = version_dirs[0]

        # Read plugin manifest
        manifest_path = version_dir / ".claude-plugin" / "plugin.json"
        manifest = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to read manifest for {plugin_dir.name}: {e}")

        plugin = {
            "name": manifest.get("name", plugin_dir.name),
            "description": manifest.get("description", ""),
            "version": manifest.get("version", version_dir.name),
            "author": manifest.get("author", {}).get("name", "Unknown") if isinstance(manifest.get("author"), dict) else "Unknown",
            "agents": [],
            "skills": [],
            "commands": [],
        }

        # Extract agents from agents/*.md
        agents_dir = version_dir / "agents"
        if agents_dir.is_dir():
            for agent_file in sorted(agents_dir.glob("*.md")):
                try:
                    content = agent_file.read_text(encoding="utf-8")
                    fm = _parse_md_frontmatter(content)
                    plugin["agents"].append({
                        "name": fm.get("name", agent_file.stem),
                        "description": fm.get("description", ""),
                        "model": fm.get("model", ""),
                        "tools": fm.get("tools", ""),
                        "file": str(agent_file.relative_to(version_dir)),
                        "content": content,
                    })
                except OSError as e:
                    logger.warning(f"Failed to read agent {agent_file}: {e}")

        # Extract skills from skills/*/SKILL.md (superpowers-style nested layout)
        skills_dir = version_dir / "skills"
        if skills_dir.is_dir():
            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    fm = _parse_md_frontmatter(content)
                    plugin["skills"].append({
                        "name": fm.get("name", skill_dir.name),
                        "description": fm.get("description", ""),
                        "file": str(skill_file.relative_to(version_dir)),
                    })
                except OSError as e:
                    logger.warning(f"Failed to read skill {skill_file}: {e}")

        # Extract commands from commands/*.md (feature-dev-style flat layout)
        commands_dir = version_dir / "commands"
        if commands_dir.is_dir():
            for cmd_file in sorted(commands_dir.glob("*.md")):
                try:
                    content = cmd_file.read_text(encoding="utf-8")
                    fm = _parse_md_frontmatter(content)
                    plugin["commands"].append({
                        "name": fm.get("name", cmd_file.stem),
                        "description": fm.get("description", ""),
                        "file": str(cmd_file.relative_to(version_dir)),
                    })
                except OSError as e:
                    logger.warning(f"Failed to read command {cmd_file}: {e}")

        plugins.append(plugin)
        agent_count = len(plugin["agents"])
        skill_count = len(plugin["skills"])
        cmd_count = len(plugin["commands"])
        logger.info(
            f"  -> Plugin: {plugin['name']} "
            f"(agents={agent_count}, skills={skill_count}, commands={cmd_count})"
        )

    logger.info(f"Discovered {len(plugins)} Claude plugins")
    return plugins


def assemble_claude_plugins(plugins: list[dict], output_path: Path) -> None:
    """Write assembled_claude_plugins.json — lean metadata cache (ADR-171).

    Follows the assembled_hubs.json pattern: generated_at, plugin_count, plugins[].
    Strips content fields to keep the cache lean.
    """
    from datetime import datetime

    lean_plugins = []
    for p in plugins:
        lean = {
            "name": p["name"],
            "description": p["description"],
            "version": p["version"],
            "author": p["author"],
            "agents": [
                {"name": a["name"], "description": a["description"], "model": a.get("model", "")}
                for a in p["agents"]
            ],
            "skills": [
                {"name": s["name"], "description": s["description"]}
                for s in p["skills"]
            ],
            "commands": [
                {"name": c["name"], "description": c["description"]}
                for c in p["commands"]
            ],
        }
        lean_plugins.append(lean)

    assembly = {
        "generated_at": datetime.now().isoformat(),
        "plugin_count": len(lean_plugins),
        "plugins": lean_plugins,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        current_mode = output_path.stat().st_mode
        if not (current_mode & 0o200):
            output_path.chmod(current_mode | 0o200)
    write_stable_json(output_path, assembly, volatile_keys=("generated_at",))
    GENERATED_FILES.append(output_path)
    logger.info(f"Generated assembled_claude_plugins.json ({len(lean_plugins)} plugins)")


def resolve_overlaps(plugins: list[dict], project_root: Path) -> list[dict]:
    """Resolve plugin import overlaps (ADR-171).

    Previously walked plugins/*/skills/*/augur/augur.yaml for claude_plugins.imports.
    Those augur.yaml files were deleted during the ADR-430 migration to skills/.
    This function is retained as a no-op stub for callers that still invoke it.

    Returns:
        Empty list (no augur.yaml import declarations remain).
    """
    return []


def distribute_imported_agents(
    resolved_imports: list[dict],
    project_root: Path,
) -> int:
    """Write imported Claude plugin agents to adapter-specific paths (ADR-171).

    For each resolved import, writes agent content to each adapter's skill/workflow dir.
    Claude Code agents are already natively available — only non-Claude adapters need files.
    Non-agent IDEs get capabilities described in the agent prompt (stripped of Claude frontmatter).

    Returns count of files written.
    """
    from .engine import write_generated_file, _is_adapter_enabled  # lazy import to break circular dep

    def _load_ide_integrations_for_root(root: Path) -> dict:
        """Load adapter enablement config from the provided project root."""
        config_path = root / "config" / "agents" / "ide_integrations.yaml"
        if not config_path.exists():
            return {"integrations": {}}
        try:
            import yaml as pyyaml

            with open(config_path, encoding="utf-8") as f:
                data = pyyaml.safe_load(f) or {}
            return data if "integrations" in data else {"integrations": {}}
        except Exception as e:
            logger.warning(f"Failed to load ide_integrations.yaml from {config_path}: {e}")
            return {"integrations": {}}

    count = 0
    ide_config = _load_ide_integrations_for_root(project_root)

    for imp in resolved_imports:
        for item in imp["items"]:
            if item["type"] != "agent":
                continue

            agent_name = item["name"]
            content = item.get("content", "")
            if not content:
                continue

            # Strip Claude-specific frontmatter for non-Claude adapters
            clean_content = strip_claude_frontmatter_fields(content)
            source_ref = f"claude-plugin:{imp['source']}/agents/{agent_name}"

            for adapter_name, target_dir in _constants_mod._ADAPTER_AGENT_PATHS.items():
                # Gate on enabled flag (ADR-219)
                if not _is_adapter_enabled(adapter_name, ide_config):
                    continue

                if adapter_name in ("gemini", "opencode", "claude_desktop", "claude_code"):
                    # Claude-style adapters expect skills in subdirectories as SKILL.md
                    skill_dir = target_dir / agent_name
                    skill_dir.mkdir(parents=True, exist_ok=True)
                    target_file = skill_dir / "SKILL.md"
                else:
                    # Flat adapters expect .md files
                    target_dir.mkdir(parents=True, exist_ok=True)
                    target_file = target_dir / f"{agent_name}.md"

                write_generated_file(target_file, clean_content, source=source_ref)
                count += 1

    if count:
        logger.info(f"Distributed {count} imported agent files across {len(_constants_mod._ADAPTER_AGENT_PATHS)} adapters")
    return count
