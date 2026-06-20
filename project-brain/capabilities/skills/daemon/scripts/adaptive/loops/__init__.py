"""Adaptive loop implementations.

Avoid eager imports so individual tests can import one loop module without
requiring the entire loop package graph to resolve old absolute imports.
"""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "BaseLoop",
    "LoopResult",
    "CodeQualityLoop",
    "CommandEvolutionLoop",
    "HardeningLoop",
    "KnowledgeEnrichmentLoop",
    "SelfHealLoop",
]


def __getattr__(name: str):
    module_map = {
        "BaseLoop": ".base_loop",
        "LoopResult": ".base_loop",
        "CodeQualityLoop": ".code_quality",
        "CommandEvolutionLoop": ".command_evolution",
        "HardeningLoop": ".hardening",
        "KnowledgeEnrichmentLoop": ".knowledge_enrichment",
        "SelfHealLoop": ".self_heal",
    }
    if name not in module_map:
        raise AttributeError(name)
    module = import_module(module_map[name], __name__)
    return getattr(module, name)
