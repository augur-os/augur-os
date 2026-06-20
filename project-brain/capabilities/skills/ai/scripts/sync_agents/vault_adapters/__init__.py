"""sync_agents/vault_adapters/ — Vault adapter registry (ADR-436)."""
from __future__ import annotations

import os
import shutil as _shutil
from abc import ABC, abstractmethod
from pathlib import Path


class VaultAdapter(ABC):
    """Base class for all knowledge vault sync adapters (ADR-436).

    Unlike BaseAdapter (IDE/CLI), VaultAdapters handle bidirectional
    knowledge sync — notes, memory, and vault content.
    """

    adapter_name: str = ""

    @abstractmethod
    def sync_to_vault(self, content: dict) -> int:
        """Sync Augur content to the vault. Returns files written."""
        ...

    @abstractmethod
    def sync_from_vault(self) -> dict:
        """Read vault content back into Augur. Returns discovered items."""
        ...

    @abstractmethod
    def detect_installed(self) -> bool:
        """Check if this vault tool is installed/configured."""
        ...

    def get_managed_dirs(self) -> list[str]:
        """Return vault directories this adapter manages."""
        return []

    def cleanup(self) -> list[str]:
        """Delete managed vault directories. Returns list of deleted paths."""
        from ..constants import logger

        deleted = []
        for path_str in self.get_managed_dirs():
            path = Path(path_str).expanduser()
            if not path.exists():
                continue
            try:
                if path.is_dir():
                    for item in path.rglob("*"):
                        if item.is_file() and not os.access(item, os.W_OK):
                            item.chmod(0o666)
                    _shutil.rmtree(path)
                else:
                    if not os.access(path, os.W_OK):
                        path.chmod(0o666)
                    path.unlink()
                deleted.append(path_str)
                logger.info(f"Cleaned up vault path: {path_str}")
            except OSError as e:
                logger.warning(f"Failed to clean up vault {path_str}: {e}")
        return deleted


class LocalFileVaultAdapter(VaultAdapter):
    """Vault tools with direct filesystem access (Obsidian, Logseq)."""

    @abstractmethod
    def get_vault_root(self) -> Path:
        """Return the root directory of the local vault."""
        ...

    def detect_installed(self) -> bool:
        """Detect by checking if vault root exists."""
        return self.get_vault_root().exists()


class LocalAppVaultAdapter(VaultAdapter):
    """Vault tools accessed via CLI/AppleScript bridge (Apple Notes)."""

    @abstractmethod
    def get_bridge_command(self) -> str:
        """Return the CLI/AppleScript command for vault access."""
        ...


class CloudVaultAdapter(VaultAdapter):
    """Vault tools accessed via remote API (Notion)."""

    @abstractmethod
    def get_api_base_url(self) -> str:
        """Return the base API URL for the cloud vault."""
        ...
