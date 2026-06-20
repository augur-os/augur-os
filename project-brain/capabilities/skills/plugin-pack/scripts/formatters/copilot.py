"""Copilot formatter - produces GitHub Copilot-native repository assets."""
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
import logging
import shutil
from pathlib import Path

import yaml

from .base import BaseFormatter
from .mcp_config import build_augur_mcp_config

logger = logging.getLogger(__name__)

_AUGUR_MANAGED_MARKERS = ("AUGUR-GENERATED", "AUGUR-ADAPTED-COPY")

# Sync-managed subtrees under .github — stale Augur-marked files in these
# directories are pruned on install when absent from the fresh build output.
_PRUNED_SUBTREES = ("agents", "skills", "prompts")


def _is_augur_managed(path: Path) -> bool:
    """Return True when an existing file carries an Augur-generated marker."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return any(marker in content for marker in _AUGUR_MANAGED_MARKERS)


class CopilotFormatter(BaseFormatter):
    """Format assembled plugin output as GitHub Copilot repository assets."""

    def plugin_dir(self, output_dir: Path) -> Path:
        return output_dir / ".github"

    def write_manifest(self, plugin_dir: Path, version: str) -> None:
        instructions = f"""# Augur Copilot Instructions

<!-- AUGUR-GENERATED version={version} -->

Use Augur as a project-first second brain for knowledge retrieval, synthesis, and saved context.
Work review-first: inspect the relevant repo files, tests, and generated Augur context before changing code.
Prefer Augur MCP tools for knowledge operations instead of ad hoc local scripts.
"""
        (plugin_dir / "copilot-instructions.md").write_text(instructions, encoding="utf-8")

        agents_dir = plugin_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        agent = f"""---
name: augur
description: Project-first Augur agent for repository knowledge, review, and MCP-assisted workflows
---

<!-- AUGUR-GENERATED version={version} -->

Use this agent when repository work benefits from Augur knowledge, retained memory, or wiki-backed context.
Start review-first, ground answers in project files, and call Augur MCP tools when knowledge search or capture is needed.
"""
        (agents_dir / "augur.agent.md").write_text(agent, encoding="utf-8")

    def write_mcp_config(self, plugin_dir: Path, project_root: Path, python_path: str) -> None:
        config = build_augur_mcp_config(project_root, python_path, "copilot")
        content = (
            "# Augur MCP Setup for Copilot\n\n"
            "<!-- AUGUR-GENERATED -->\n\n"
            "Copy this example into the Copilot MCP configuration surface for this project. "
            "This file is guidance only; plugin-pack does not mutate user secrets or editor configuration.\n\n"
            "```json\n"
            f"{json.dumps(config, indent=2)}\n"
            "```\n"
        )
        (plugin_dir / "copilot-mcp.md").write_text(content, encoding="utf-8")

    def write_marketplace(self, output_dir: Path, version: str) -> None:
        return None

    def write_skills(self, plugin_dir: Path, skills: dict[str, str]) -> None:
        for name, content in skills.items():
            skill_dir = plugin_dir / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def write_commands(self, plugin_dir: Path, commands: dict[str, dict]) -> None:
        prompts_dir = plugin_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        for name, cmd in commands.items():
            frontmatter = yaml.safe_dump(
                {"description": cmd["description"]},
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            ).rstrip("\n")
            content = (
                "---\n"
                f"{frontmatter}\n"
                "---\n"
                "<!-- AUGUR-GENERATED -->\n\n"
                f"{cmd['body']}\n\n"
                "User input:\n{{input}}\n"
            )
            (prompts_dir / f"augur-{name}.prompt.md").write_text(content, encoding="utf-8")

    def install(
        self,
        output_dir: Path,
        version: str,
        *,
        install_root: Path | None = None,
    ) -> bool:
        plugin_source = output_dir / ".github"
        if not plugin_source.exists():
            logger.warning("Copilot .github source not found at %s", plugin_source)
            return False

        if install_root is None:
            from src.config.paths import get_project_root

            install_root = Path(get_project_root())

        target = install_root / ".github"
        target.mkdir(parents=True, exist_ok=True)

        self._copy_generated_tree(plugin_source, target)
        self._prune_stale_tree(plugin_source, target)

        logger.info("  Installed Augur Copilot assets into: %s", target)
        return True

    def _copy_generated_tree(self, source: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        for source_child in source.iterdir():
            target_child = target / source_child.name

            if source_child.is_dir():
                if target_child.exists() and not target_child.is_dir():
                    continue
                self._copy_generated_tree(source_child, target_child)
                continue

            if target_child.exists() and not _is_augur_managed(target_child):
                continue

            target_child.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_child, target_child)

    def _prune_stale_tree(self, source: Path, target: Path) -> None:
        """Remove stale Augur-managed files absent from the fresh build output.

        Only the sync-managed subtrees (agents/skills/prompts) are walked;
        unmarked user-owned files are never touched.
        """
        for subtree in _PRUNED_SUBTREES:
            target_root = target / subtree
            if not target_root.is_dir():
                continue
            source_root = source / subtree
            for target_file in sorted(target_root.rglob("*")):
                if not target_file.is_file():
                    continue
                if (source_root / target_file.relative_to(target_root)).exists():
                    continue
                if not _is_augur_managed(target_file):
                    continue
                target_file.unlink()
                logger.info("  Pruned stale Augur Copilot asset: %s", target_file)
            # Prune now-empty directories bottom-up, keeping the subtree root.
            for target_dir in sorted(target_root.rglob("*"), reverse=True):
                if target_dir.is_dir() and not target_dir.is_symlink() and not any(target_dir.iterdir()):
                    target_dir.rmdir()
