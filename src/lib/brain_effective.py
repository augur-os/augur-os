"""Effective/shadowed resolution across the layered brain stack (ADR-781 §2d).

Pure computation over a ``LayeredProjection``: for each capability, the most
specific tier wins a given entry name and earlier tiers become its ``shadowed``
list. Coincident physical roots (the Augur-repo D10 Global==Project case) are
enumerated once, attributed to the first (most general) tier that holds them.
No filesystem writes, no client contact.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.lib.brain_layered_projection import (
    LayeredCapabilitySource,
    LayeredProjection,
    resolve_layered_projection,
)
from src.lib.brain_registry_models import BrainType
from src.lib.brain_stack import BrainStack


@dataclass(frozen=True)
class EffectiveEntry:
    name: str
    winner: Path
    winner_tier: BrainType
    shadowed: tuple[tuple[BrainType, Path], ...]  # (tier, path) general -> more specific


@dataclass(frozen=True)
class EffectiveSet:
    entries: dict[str, EffectiveEntry]

    def names(self) -> list[str]:
        return list(self.entries.keys())

    def shadowed_names(self) -> list[str]:
        return [name for name, e in self.entries.items() if e.shadowed]


def _is_skill_dir(path: Path) -> bool:
    return path.is_dir() and (path / "SKILL.md").is_file()


def _compute_effective(
    layers: Sequence[LayeredCapabilitySource],
    *,
    roots_of: Callable[[LayeredCapabilitySource], tuple[Path, ...]],
    is_entry: Callable[[Path], bool],
) -> EffectiveSet:
    entries: dict[str, EffectiveEntry] = {}
    seen_roots: set[Path] = set()
    for layer in layers:  # general (global) -> specific (project)
        for root in roots_of(layer):
            resolved = Path(root).resolve()
            if resolved in seen_roots:  # D10 coincident root: count once, as the general tier
                continue
            seen_roots.add(resolved)
            if not Path(root).is_dir():
                continue
            for child in sorted(Path(root).iterdir()):
                if not is_entry(child):
                    continue
                name = child.name
                prior = entries.get(name)
                shadowed = prior.shadowed + ((prior.winner_tier, prior.winner),) if prior is not None else ()
                entries[name] = EffectiveEntry(
                    name=name,
                    winner=child,
                    winner_tier=layer.tier,
                    shadowed=shadowed,
                )
    return EffectiveSet(entries=entries)


def compute_effective_skills(layered: LayeredProjection) -> EffectiveSet:
    return _compute_effective(
        layered.layers,
        roots_of=lambda layer: layer.sources.skill_roots,
        is_entry=_is_skill_dir,
    )


def effective_summary(stack: BrainStack, *, project_root: Path | None = None) -> dict[str, dict]:
    """Compact effective/shadowed summary per capability for verify-harness / UI / CLI."""
    layered = resolve_layered_projection(stack, project_root=project_root)
    skills = compute_effective_skills(layered)
    return {
        "skills": {
            "effective": len(skills.names()),
            "shadowed": skills.shadowed_names(),
        }
    }
