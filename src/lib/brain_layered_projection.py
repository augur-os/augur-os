"""Layered capability-source merge across the Global/User/Project brain stack.

ADR-781 Phase 2b foundation. Pure enumeration: given a resolved ``BrainStack``,
return each tier's ``BrainProjectionSources`` in precedence order (general ->
specific) plus deduped, precedence-ordered root accessors. The Augur dev repo's
self-hosting coincidence (Global and project-augur share ``project-brain``) is
collapsed by ``_dedupe`` so a coincident root is projected once (D10).

This module does NOT write anything and does NOT do per-name effective/shadowed
resolution — that is the pipeline wiring (2b-wire) and 2c respectively.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.lib.brain_projection import (
    BrainProjectionSources,
    resolve_brain_projection_sources,
)
from src.lib.brain_registry_models import BrainType
from src.lib.brain_stack import BrainStack


@dataclass(frozen=True)
class LayeredCapabilitySource:
    tier: BrainType
    brain_id: str
    sources: BrainProjectionSources


@dataclass(frozen=True)
class LayeredProjection:
    """Per-tier capability sources ordered general (global) -> specific (project)."""

    layers: tuple[LayeredCapabilitySource, ...]

    def ordered_skill_roots(self) -> tuple[Path, ...]:
        return self._dedupe(r for layer in self.layers for r in layer.sources.skill_roots)

    def ordered_agent_roots(self) -> tuple[Path, ...]:
        return self._dedupe(r for layer in self.layers for r in layer.sources.agent_roots)

    def ordered_policy_roots(self) -> tuple[Path, ...]:
        return self._dedupe(r for layer in self.layers for r in layer.sources.policy_roots)

    def ordered_workflow_roots(self) -> tuple[Path, ...]:
        return self._dedupe(r for layer in self.layers for r in layer.sources.workflow_roots)

    @staticmethod
    def _dedupe(roots: Iterable[Path]) -> tuple[Path, ...]:
        seen: set[Path] = set()
        out: list[Path] = []
        for root in roots:
            resolved = Path(root).resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            out.append(Path(root))
        return tuple(out)


def resolve_layered_projection(stack: BrainStack, *, project_root: Path | None = None) -> LayeredProjection:
    """Enumerate per-tier capability sources for the stack, general -> specific."""
    layers: list[LayeredCapabilitySource] = []
    for brain in stack.ordered():
        attached = (
            stack.project.attached_project if brain.type is BrainType.PROJECT and stack.project is not None else None
        )
        sources = resolve_brain_projection_sources(brain=brain, attached_project=attached, project_root=project_root)
        layers.append(LayeredCapabilitySource(tier=brain.type, brain_id=brain.id, sources=sources))
    return LayeredProjection(layers=tuple(layers))


def layered_skill_source_dirs(stack: BrainStack, *, project_root: Path | None = None) -> tuple[Path, ...]:
    """Ordered general-to-specific, deduped skill roots across the tier stack."""
    return resolve_layered_projection(stack, project_root=project_root).ordered_skill_roots()
