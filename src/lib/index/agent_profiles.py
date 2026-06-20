"""Agent profile projection metadata helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

DEFAULT_MASTER_CLIENT = "claude-code"

CLIENT_AGENT_DIRS: dict[str, str] = {
    "claude-code": ".claude/agents",
    "gemini": ".antigravity/agents",
    "codex": ".codex/agents",
    "cursor": ".cursor/agents",
    "copilot": ".github/agents",
    "opencode": ".opencode/agents",
    "antigravity": ".subagents",
}


def _client_metadata_key(client: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", client.lower()).strip("_")


def load_agent_model_mapping(root: Path) -> dict[str, Any]:
    mapping_path = root / "config" / "agents" / "model_mapping.yaml"
    if not mapping_path.is_file():
        return {"tiers": {}, "reverse_lookup": {}}

    try:
        raw = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
    except Exception:
        return {"tiers": {}, "reverse_lookup": {}}
    if not isinstance(raw, dict):
        return {"tiers": {}, "reverse_lookup": {}}
    return {
        "tiers": raw.get("tiers", {}) if isinstance(raw.get("tiers"), dict) else {},
        "reverse_lookup": (raw.get("reverse_lookup", {}) if isinstance(raw.get("reverse_lookup"), dict) else {}),
    }


def resolve_agent_model_tier(mapping: dict[str, Any], client: str, model: str) -> str:
    if not model:
        return ""

    reverse = mapping.get("reverse_lookup", {})
    if isinstance(reverse, dict) and model in reverse:
        return str(reverse[model])

    tiers = mapping.get("tiers", {})
    if isinstance(tiers, dict):
        for tier_name, tier_data in tiers.items():
            if not isinstance(tier_data, dict):
                continue
            clients = tier_data.get("clients", {})
            if isinstance(clients, dict) and clients.get(client) == model:
                return str(tier_name)

    return "standard"


def _client_models_for_tier(mapping: dict[str, Any], tier: str) -> dict[str, str]:
    tiers = mapping.get("tiers", {})
    if not isinstance(tiers, dict):
        return {}
    tier_data = tiers.get(tier, {})
    if not isinstance(tier_data, dict):
        return {}
    clients = tier_data.get("clients", {})
    if not isinstance(clients, dict):
        return {}
    return {str(client): str(model) for client, model in clients.items() if client and model}


def agent_projection_metadata(
    root: Path,
    *,
    name: str,
    frontmatter: dict[str, Any],
) -> dict[str, str]:
    """Return client-aware model/projection metadata for an agent profile."""
    root = Path(root)
    master_client = str(frontmatter.get("x-augur-master") or frontmatter.get("master_client") or DEFAULT_MASTER_CLIENT)
    source_model = str(frontmatter.get("model") or frontmatter.get("default_model") or "")
    mapping = load_agent_model_mapping(root)
    source_tier = resolve_agent_model_tier(mapping, master_client, source_model)

    metadata: dict[str, str] = {"master_client": master_client}
    if source_model:
        metadata["source_model"] = source_model
    if source_tier:
        metadata["source_tier"] = source_tier

    client_models = _client_models_for_tier(mapping, source_tier)
    if client_models:
        metadata["projection_clients"] = ",".join(client_models.keys())

    for client, model in client_models.items():
        client_key = _client_metadata_key(client)
        metadata[f"{client_key}_model"] = model

        rel_dir = CLIENT_AGENT_DIRS.get(client)
        if not rel_dir:
            continue
        rel_path = Path(rel_dir) / f"{name}.md"
        metadata[f"{client_key}_profile_path"] = rel_path.as_posix()
        metadata[f"{client_key}_sync_status"] = "synced" if (root / rel_path).is_file() else "missing"

    return metadata
