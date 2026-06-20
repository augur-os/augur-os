"""Unified AI client resolver for per-action routing.

Resolves which AI client (Claude Code, Codex, Ollama, etc.) handles
a given action by walking a priority chain:

  1. Airplane mode → Ollama (absolute override)
  2. --local flag  → Ollama (autoloop mode)
  3. Per-action override → user preference for this action
  4. Global default → user's default client
  5. Implicit → whatever IDE agent is connected
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class ResolvedClient:
    """Result of client resolution."""

    client_id: str
    client_type: str  # "ide" | "local" | "api"
    model: str | None = None
    source: str = "implicit"  # "airplane" | "local_flag" | "override" | "global" | "implicit"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Known client type mappings
_CLIENT_TYPES: dict[str, str] = {
    "ollama": "local",
    "claude-code": "ide",
    "antigravity": "ide",
    "codex": "ide",
    "cursor": "ide",
    "cline": "ide",
    "gemini": "ide",
    "windsurf": "ide",
    "opencode": "ide",
    "claude-desktop": "ide",
    "cowork": "ide",
}


def _client_type_for(client_id: str) -> str:
    """Infer client_type from client_id."""
    return _CLIENT_TYPES.get(client_id, "ide")


class ClientResolver:
    """Resolves which AI client should handle a given action."""

    def __init__(self, prefs_path: Path | None = None):
        self._prefs_path = prefs_path

    def _get_prefs_path(self) -> Path:
        if self._prefs_path:
            return self._prefs_path
        from src.mcp.augur_shared.config import get_preferences_path

        return get_preferences_path()

    def _load_prefs(self) -> dict[str, Any]:
        from src.config.preferences import load_preferences

        if self._prefs_path:
            return load_preferences(path=self._prefs_path, migrate_legacy=False)
        return load_preferences()

    def _get_ollama_model(self, prefs: dict[str, Any]) -> str | None:
        return prefs.get("local_backends", {}).get("ollama", {}).get("model", "qwen3.5:9b")

    def resolve(self, action_id: str, *, local_flag: bool = False) -> ResolvedClient:
        """Resolve which client should handle the given action.

        Priority: airplane > local_flag > override > global > implicit.
        """
        prefs = self._load_prefs()
        airplane = prefs.get("airplane_mode", {})
        routing = prefs.get("client_routing", {})
        overrides = routing.get("overrides", {})
        default_client = routing.get("default_client")

        # Priority 1: Airplane mode
        if airplane.get("enabled"):
            return ResolvedClient(
                client_id="ollama",
                client_type="local",
                model=self._get_ollama_model(prefs),
                source="airplane",
            )

        # Priority 2: --local flag
        if local_flag:
            return ResolvedClient(
                client_id="ollama",
                client_type="local",
                model=self._get_ollama_model(prefs),
                source="local_flag",
            )

        # Priority 3: Per-action override
        if action_id in overrides:
            cid = overrides[action_id]
            return ResolvedClient(
                client_id=cid,
                client_type=_client_type_for(cid),
                model=self._get_ollama_model(prefs) if cid == "ollama" else None,
                source="override",
            )

        # Priority 4: Global default
        if default_client:
            return ResolvedClient(
                client_id=default_client,
                client_type=_client_type_for(default_client),
                model=self._get_ollama_model(prefs) if default_client == "ollama" else None,
                source="global",
            )

        # Priority 5: Implicit (no routing configured)
        return ResolvedClient(client_id="", client_type="ide", source="implicit")

    def set_override(self, action_id: str, client_id: str) -> None:
        """Set a per-action client override."""
        prefs = self._load_prefs()
        routing = prefs.setdefault("client_routing", {})
        overrides = routing.setdefault("overrides", {})
        overrides[action_id] = client_id
        self._save_prefs(prefs)

    def clear_override(self, action_id: str) -> bool:
        """Clear a per-action override. Returns True if it existed."""
        prefs = self._load_prefs()
        overrides = prefs.get("client_routing", {}).get("overrides", {})
        if action_id not in overrides:
            return False
        del overrides[action_id]
        self._save_prefs(prefs)
        return True

    def set_default(self, client_id: str | None) -> None:
        """Set or clear the global default client."""
        prefs = self._load_prefs()
        routing = prefs.setdefault("client_routing", {})
        routing["default_client"] = client_id
        self._save_prefs(prefs)

    def list_overrides(self) -> dict[str, str]:
        """Return all per-action overrides."""
        prefs = self._load_prefs()
        return dict(prefs.get("client_routing", {}).get("overrides", {}))

    def _save_prefs(self, prefs: dict[str, Any]) -> None:
        from src.config.preferences import save_preferences

        save_preferences(prefs, path=self._get_prefs_path())
