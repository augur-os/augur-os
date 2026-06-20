"""ClientConfigAdapter protocol: read/diff/write a single AI-client's config."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.cli_config.manifest import Manifest, ServerEntry


@dataclass(frozen=True)
class ConfigDiff:
    """Pending changes the adapter would write."""

    added: list[ServerEntry]
    updated: list[ServerEntry]
    removed: list[str]  # ids of augur-* entries no longer in manifest

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.updated or self.removed)


class ClientConfigAdapter(Protocol):
    """Per-client config read/write adapter.

    Each adapter is responsible for:
    - Locating the user-tier config file (defaults; override-able for tests).
    - Reading existing config; preserving non-augur entries verbatim.
    - Computing the diff vs. manifest.
    - Writing the new config atomically with a timestamped backup.

    All adapters scope their writes to entries with id matching `augur*`.
    """

    name: str  # 'claude' | 'codex' | 'gemini' | 'copilot'

    def default_config_path(self) -> Path:
        """Default config path for this client."""
        ...

    def diff(self, manifest: Manifest, config_path: Path | None = None) -> ConfigDiff:
        """Compute the diff between manifest and current config."""
        ...

    def apply(self, manifest: Manifest, config_path: Path | None = None) -> Path | None:
        """Apply the manifest. Returns path of the backup file, or None if no prior config existed."""
        ...
