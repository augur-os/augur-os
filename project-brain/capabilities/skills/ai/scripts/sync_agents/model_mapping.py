"""sync_agents/model_mapping.py — Model tier resolution for cross-client agent sync.

ADR-464: Maps abstract model tiers (fast/standard/deep) to client-specific
model IDs, and resolves client-specific models back to abstract tiers.
"""
from __future__ import annotations

import yaml

# Lazy-loaded cache
_mapping_cache: dict | None = None


def _load_mapping() -> dict:
    """Load and cache model_mapping.yaml from config/agents/."""
    global _mapping_cache
    if _mapping_cache is not None:
        return _mapping_cache

    from .constants import PROJECT_ROOT, logger

    mapping_path = PROJECT_ROOT / "config" / "agents" / "model_mapping.yaml"
    if not mapping_path.exists():
        logger.warning(f"Model mapping not found: {mapping_path}")
        _mapping_cache = {"tiers": {}, "reverse_lookup": {}}
        return _mapping_cache

    try:
        raw = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            logger.warning(f"Invalid model_mapping.yaml format (expected dict)")
            _mapping_cache = {"tiers": {}, "reverse_lookup": {}}
            return _mapping_cache

        _mapping_cache = {
            "tiers": raw.get("tiers", {}),
            "reverse_lookup": raw.get("reverse_lookup", {}),
        }
    except Exception as e:
        logger.error(f"Failed to load model_mapping.yaml: {e}")
        _mapping_cache = {"tiers": {}, "reverse_lookup": {}}

    return _mapping_cache


def resolve_tier(client: str, model_name: str) -> str:
    """Resolve a client-specific model name to an abstract tier.

    Args:
        client: Client identifier (e.g., "claude-code", "gemini").
        model_name: Client-specific model name (e.g., "sonnet", "gemini-3-flash-preview").

    Returns:
        Abstract tier name ("fast", "standard", or "deep").
        Falls back to "standard" if no mapping found.
    """
    mapping = _load_mapping()

    # 1. Try reverse_lookup first (direct model → tier)
    reverse = mapping.get("reverse_lookup", {})
    if model_name in reverse:
        return reverse[model_name]

    # 2. Search tiers for the client+model combination
    for tier_name, tier_data in mapping.get("tiers", {}).items():
        clients = tier_data.get("clients", {})
        if clients.get(client) == model_name:
            return tier_name

    return "standard"


def resolve_model(from_client: str, to_client: str, model_name: str) -> str:
    """Map a model from one client to the equivalent model in another client.

    Args:
        from_client: Source client identifier.
        to_client: Target client identifier.
        model_name: Model name in the source client's format.

    Returns:
        Equivalent model name for the target client.
        Falls back to the standard tier's model for the target client.
    """
    tier = resolve_tier(from_client, model_name)
    mapping = _load_mapping()

    tier_data = mapping.get("tiers", {}).get(tier, {})
    clients = tier_data.get("clients", {})

    if to_client in clients:
        return clients[to_client]

    # Fallback: standard tier for target client
    standard = mapping.get("tiers", {}).get("standard", {}).get("clients", {})
    return standard.get(to_client, model_name)


def get_tier_model(tier: str, client: str) -> str | None:
    """Get the model name for a specific tier and client.

    Args:
        tier: Abstract tier name ("fast", "standard", "deep").
        client: Client identifier.

    Returns:
        Model name for the client at the given tier, or None if not found.
    """
    mapping = _load_mapping()
    tier_data = mapping.get("tiers", {}).get(tier, {})
    return tier_data.get("clients", {}).get(client)


def get_all_tiers() -> list[str]:
    """Return all defined tier names."""
    mapping = _load_mapping()
    return list(mapping.get("tiers", {}).keys())


def get_supported_clients() -> set[str]:
    """Return all client identifiers that have model mappings."""
    mapping = _load_mapping()
    clients: set[str] = set()
    for tier_data in mapping.get("tiers", {}).values():
        clients.update(tier_data.get("clients", {}).keys())
    return clients


def invalidate_cache() -> None:
    """Clear the cached mapping (useful for tests)."""
    global _mapping_cache
    _mapping_cache = None
