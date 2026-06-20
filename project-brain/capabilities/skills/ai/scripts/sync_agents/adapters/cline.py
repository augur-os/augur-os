"""sync_agents/adapters/cline.py — Cline adapter."""
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
from pathlib import Path

from .base import BaseAdapter
from ..constants import (
    PROJECT_ROOT,
    SOURCE_RULES_LABEL,
    MCP_CONFIG_TEMPLATE,
    GENERATED_FILES,
    logger,
)
from ..engine import write_generated_file, clean_directory
from ..templates import locate_mcp_python, render_rules_projection, _load_project_context

from src.lib.ai.crew_parser import scan_crew_skills  # noqa: E402

class ClineAdapter(BaseAdapter):
    """Cline CLI adapter.

    Cline uses .clinerules/ for rules and skills/ for skills (same format as Claude Code).
    Rules are markdown files in .clinerules/ that provide persistent instructions.
    """

    adapter_name = "cline"

    def get_managed_files(self) -> list[str]:
        return [
            ".clinerules/augur-rules.md",
        ]

    def detect_installed(self) -> bool:
        from ..constants import PROJECT_ROOT
        return (PROJECT_ROOT / ".clinerules").is_dir()

    def sync_rules(self, content: str) -> None:
        """Sync rules to .clinerules/ directory.

        Cline reads all .md files in .clinerules/ as rules.
        We sync the main agent-rules to a dedicated file.
        """
        resolved = render_rules_projection(content)

        # Create .clinerules directory
        clinerules_dir = PROJECT_ROOT / ".clinerules"
        clinerules_dir.mkdir(parents=True, exist_ok=True)

        # Write main rules file
        write_generated_file(
            clinerules_dir / "augur-rules.md",
            resolved,
            source=SOURCE_RULES_LABEL,
        )

    def sync_subagents(self) -> None:
        """Generate Cline subagent profiles from crew SKILL.md files.

        Cline uses .claude/agents/ for subagents (same as Claude Code).
        """
        profiles = scan_crew_skills(PROJECT_ROOT)
        if not profiles:
            logger.warning("No crew skills found for subagent generation")
            return

        agents_dir = PROJECT_ROOT / ".claude" / "agents"
        clean_directory(agents_dir)

        project_context = _load_project_context(PROJECT_ROOT)

        registry = []
        for profile in profiles:
            agent_md = profile.to_agent_markdown(
                tier="medium",
                project_context=project_context,
            )
            target = agents_dir / f"{profile.name}.md"
            write_generated_file(
                target,
                agent_md,
                source=f"skills/{profile.name}/SKILL.md",
            )
            registry.append(profile.to_registry_entry())
            logger.info(f"  → Subagent: {profile.name}")

        registry_path = agents_dir / "registry.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        if registry_path.exists():
            current_mode = registry_path.stat().st_mode
            if not (current_mode & 0o200):
                registry_path.chmod(current_mode | 0o200)
        registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
        registry_path.chmod(0o444)
        GENERATED_FILES.append(registry_path)
        logger.info(f"✅ Generated {agents_dir.relative_to(PROJECT_ROOT)}/registry.json ({len(registry)} agents)")

    def generate_mcp_config(self) -> None:
        """Generate resolved MCP config for Cline (.claude/mcp.json).

        Same as Claude Code since Cline uses the same config format.
        """
        if not MCP_CONFIG_TEMPLATE.exists():
            logger.warning(f"MCP config template not found: {MCP_CONFIG_TEMPLATE}")
            return

        try:
            template_content = MCP_CONFIG_TEMPLATE.read_text(encoding="utf-8")

            resolved = template_content.replace("${AUGUR_ROOT}", PROJECT_ROOT.as_posix())

            resolved = resolved.replace("${AUGUR_PYTHON}", locate_mcp_python())
            resolved = resolved.replace("${AUGUR_CLIENT_ID}", "cline")

            config = json.loads(resolved)

            target = PROJECT_ROOT / ".claude" / "mcp.json"
            target.parent.mkdir(parents=True, exist_ok=True)

            target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            GENERATED_FILES.append(target)
            logger.info(f"✅ Generated {target.relative_to(PROJECT_ROOT)} (MCP config)")
        except Exception as e:
            logger.error(f"Failed to generate MCP config for Cline: {e}")
