"""
CLI skill subcommand discovery.

Scans canonical skill directories for MCP modules that expose a
`register_subcommands(subparsers)` function, enabling plugins
to contribute CLI subcommands without modifying core cli.py.

Part of ADR-260: CLI Subcommand Plugin Architecture
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from src.logging import get_entity_logger

logger = get_entity_logger("cli.plugins")


def _get_skill_dirs(project_root: Path) -> list[Path]:
    """Get tier-ordered managed skill roots without importing MCP modules."""
    from src.config.paths import get_managed_skill_source_dirs

    return get_managed_skill_source_dirs(project_root)


def _subcommand_source_dirs(project_root: Path | None = None) -> list[Path]:
    """Return managed skill roots ordered general -> specific."""
    from src.config.paths import get_project_root

    return _get_skill_dirs(project_root or get_project_root())


def discover_subcommands(subparsers) -> int:
    """Scan canonical skills for CLI subcommand registrations.

    Args:
        subparsers: argparse subparsers action to register commands on.

    Returns:
        Number of plugins that contributed subcommands.
    """
    from src.config.paths import get_project_root

    skill_dirs = list(reversed(_subcommand_source_dirs(get_project_root())))
    contributed = 0
    # Track which plugin registered each subcommand name for collision detection
    existing_subcommands = set(subparsers._name_parser_map.keys()) if hasattr(subparsers, "_name_parser_map") else set()
    registered_by: dict[str, str] = {name: "built-in" for name in existing_subcommands}

    for skills_dir in skill_dirs:
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            mcp_init = skill_dir / "scripts" / "mcp" / "__init__.py"
            if not mcp_init.exists():
                continue

            plugin_id = skill_dir.name

            try:
                module_name = f"skill_cli_{skill_dir.name.replace('-', '_')}"

                spec = importlib.util.spec_from_file_location(module_name, mcp_init)
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                if not hasattr(module, "register_subcommands"):
                    continue

                before = set(subparsers._name_parser_map.keys())

                class _CollisionProxy:
                    def __init__(self, real_subparsers, registered_by, plugin_id):
                        self._real = real_subparsers
                        self._registered_by = registered_by
                        self._plugin_id = plugin_id
                        self._skipped = []

                    def add_parser(self, name, **kwargs):
                        if name in self._registered_by:
                            logger.warning(
                                "Subcommand '%s' already registered by %s, skipping %s",
                                name,
                                self._registered_by[name],
                                self._plugin_id,
                            )
                            self._skipped.append(name)
                            return argparse.ArgumentParser(prog=name)
                        self._registered_by[name] = self._plugin_id
                        return self._real.add_parser(name, **kwargs)

                proxy = _CollisionProxy(subparsers, registered_by, plugin_id)
                module.register_subcommands(proxy)

                after = set(subparsers._name_parser_map.keys())
                new_names = after - before
                if new_names:
                    contributed += 1
                    logger.debug("Skill %s registered subcommands: %s", plugin_id, new_names)

            except Exception as e:
                logger.error("Failed to load CLI subcommands from %s: %s", plugin_id, e)

    logger.info("CLI subcommand discovery: %d skills contributed subcommands", contributed)
    return contributed
