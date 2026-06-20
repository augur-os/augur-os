"""Deterministic rule engine for the typed knowledge graph (ADR-738).

Loads config/system/graph_edges.yaml into a RuleSet. Fails CLOSED: a malformed
config never raises into a write path — it falls back to a minimal ruleset with
only the bare-wikilink `mentions` fallback (still a superset of nothing lost).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("graph.edge_rules")

# The fail-closed minimum: every [[wikilink]] still becomes a `mentions` edge.
_FALLBACK_EDGE_TYPES: dict[str, Any] = {
    "mentions": {"rules": [{"kind": "body_wikilink", "scope": "bare"}]}
}
_FALLBACK_TIERS: dict[str, Any] = {
    "tier_1": {"min_inbound": 10, "min_source_types": 3},
    "tier_2": {"min_inbound": 3, "min_source_types": 1},
}


@dataclass
class RuleSet:
    """Parsed edge-type registry + tier thresholds."""

    edge_types: dict[str, Any] = field(default_factory=dict)
    tiers: dict[str, Any] = field(default_factory=dict)

    def rules_for_kind(self, kind: str) -> list[tuple[str, dict[str, Any]]]:
        """Return (edge_type, rule) pairs for every rule of the given kind."""
        out: list[tuple[str, dict[str, Any]]] = []
        for edge_type, spec in self.edge_types.items():
            for rule in spec.get("rules", []):
                if isinstance(rule, dict) and rule.get("kind") == kind:
                    out.append((edge_type, rule))
        return out


def _coerce(data: Any) -> RuleSet:
    """Validate a parsed YAML doc into a RuleSet, or raise ValueError."""
    if not isinstance(data, dict):
        raise ValueError("graph_edges.yaml root is not a mapping")
    edge_types = data.get("edge_types")
    if not isinstance(edge_types, dict) or not edge_types:
        raise ValueError("graph_edges.yaml has no edge_types mapping")
    for name, spec in edge_types.items():
        if not isinstance(spec, dict) or not isinstance(spec.get("rules"), list):
            raise ValueError(f"edge type {name!r} has no rules list")
    tiers = data.get("tiers")
    if not isinstance(tiers, dict):
        tiers = dict(_FALLBACK_TIERS)
    return RuleSet(edge_types=edge_types, tiers=tiers)


def load_rules(config_path: str | Path | None = None) -> RuleSet:
    """Load the edge-type registry. Fails closed to a minimal ruleset."""
    if config_path is None:
        from src.config.paths import get_project_root

        config_path = get_project_root() / "config" / "system" / "graph_edges.yaml"
    path = Path(config_path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return _coerce(data)
    except Exception as exc:  # noqa: BLE001 — fail closed, never raise into a write
        logger.warning("graph_edges.yaml unusable (%s); falling back to mentions-only", exc)
        return RuleSet(edge_types=dict(_FALLBACK_EDGE_TYPES), tiers=dict(_FALLBACK_TIERS))
