"""sync_agents/vault_adapters/obsidian.py — Obsidian vault adapter (ADR-436)."""
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
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import LocalFileVaultAdapter

try:
    from ..constants import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class ObsidianVaultAdapter(LocalFileVaultAdapter):
    """Obsidian vault sync adapter.

    get_vault_dir() IS the Obsidian vault (per ADR-270).
    Obsidian is opt-in — scaffold adds .obsidian/ config when requested.
    """

    adapter_name = "obsidian"

    def get_vault_root(self) -> Path:
        """Return vault root from src.config.paths."""
        from src.config.paths import get_vault_dir
        return get_vault_dir()

    def get_managed_dirs(self) -> list[str]:
        vault = self.get_vault_root()
        return [str(vault / ".obsidian")]

    def detect_installed(self) -> bool:
        """Obsidian is installed if vault root has .obsidian/ directory."""
        obsidian_dir = self.get_vault_root() / ".obsidian"
        return obsidian_dir.exists()

    def sync_to_vault(self, content: dict) -> int:
        """Sync Augur knowledge to Obsidian vault.

        Augur writes only to its own managed subdirectories.
        User-created notes outside managed dirs are read-only.

        Uses last-write-wins based on file mtime.
        """
        vault_root = self.get_vault_root()
        if not vault_root.exists():
            logger.warning(f"Vault root does not exist: {vault_root}")
            return 0

        written = 0
        managed_dirs = content.get("managed_dirs", ["memory", "dev"])

        for subdir_name in managed_dirs:
            source_items = content.get(subdir_name, {})
            target_dir = vault_root / subdir_name
            target_dir.mkdir(parents=True, exist_ok=True)

            for filename, file_content in source_items.items():
                target_file = target_dir / filename
                # Last-write-wins: only write if source is newer or file missing
                if target_file.exists():
                    existing = target_file.read_text(encoding="utf-8")
                    if existing == file_content:
                        continue
                target_file.write_text(file_content, encoding="utf-8")
                written += 1

        if written:
            logger.info(f"Synced {written} files to Obsidian vault")
        return written

    def sync_from_vault(self) -> dict:
        """Read vault content from Augur-managed directories.

        Only reads from managed subdirectories, not user's personal notes.
        """
        vault_root = self.get_vault_root()
        if not vault_root.exists():
            return {}

        result = {}
        managed_dirs = ["memory", "dev"]

        for subdir_name in managed_dirs:
            subdir = vault_root / subdir_name
            if not subdir.exists():
                continue
            items = {}
            for md_file in subdir.rglob("*.md"):
                rel = md_file.relative_to(subdir)
                items[str(rel)] = md_file.read_text(encoding="utf-8")
            if items:
                result[subdir_name] = items

        return result

    def scaffold(self) -> dict:
        """Create .obsidian/ config directory for vault.

        Makes get_vault_dir()/ work as an Obsidian vault.
        Only creates if not already present.
        """
        vault_root = self.get_vault_root()
        obsidian_dir = vault_root / ".obsidian"

        if obsidian_dir.exists():
            return {"status": "already_configured", "path": str(obsidian_dir)}

        vault_root.mkdir(parents=True, exist_ok=True)
        obsidian_dir.mkdir(parents=True, exist_ok=True)

        # Minimal Obsidian workspace config
        app_config = {
            "livePreview": True,
            "readableLineLength": True,
            "strictLineBreaks": False,
            "showFrontmatter": True,
        }
        (obsidian_dir / "app.json").write_text(
            json.dumps(app_config, indent=2), encoding="utf-8"
        )

        # Appearance config
        appearance_config = {
            "baseFontSize": 16,
            "interfaceFontSize": 14,
        }
        (obsidian_dir / "appearance.json").write_text(
            json.dumps(appearance_config, indent=2), encoding="utf-8"
        )

        # Core plugins — enable file explorer, search, graph
        core_plugins = [
            "file-explorer",
            "global-search",
            "graph",
            "tag-pane",
            "page-preview",
            "starred",
            "markdown-importer",
            "outline",
        ]
        (obsidian_dir / "core-plugins.json").write_text(
            json.dumps(core_plugins, indent=2), encoding="utf-8"
        )

        # Workspace layout
        workspace = {
            "main": {
                "id": "main",
                "type": "split",
                "children": [
                    {
                        "id": "editor",
                        "type": "leaf",
                        "state": {"type": "empty"},
                    }
                ],
            }
        }
        (obsidian_dir / "workspace.json").write_text(
            json.dumps(workspace, indent=2), encoding="utf-8"
        )

        logger.info(f"Scaffolded Obsidian vault at {vault_root}")
        return {"status": "created", "path": str(obsidian_dir)}
