from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class EffectiveNamedSource(Generic[T]):
    name: str
    root: Path
    path: Path
    source: T
    shadowed_roots: tuple[Path, ...]
    shadowed_paths: tuple[Path, ...]


@dataclass(frozen=True)
class LogicalSkillRootLayer:
    tier: str
    brain_id: str
    root: Path


@dataclass(frozen=True)
class EffectiveSkillReport(Generic[T]):
    logical_layers: tuple[LogicalSkillRootLayer, ...]
    physical_roots: tuple[Path, ...]
    choices: tuple[EffectiveNamedSource[T], ...]

    @property
    def shadowed_choices(self) -> tuple[EffectiveNamedSource[T], ...]:
        return tuple(choice for choice in self.choices if choice.shadowed_paths)

    @property
    def shadowed_count(self) -> int:
        return sum(len(choice.shadowed_paths) for choice in self.choices)


def choose_effective_named_sources(
    ordered_roots: Sequence[Path],
    loader: Callable[[Path], Sequence[T]],
    *,
    name_getter: Callable[[T], str],
    path_getter: Callable[[T], Path],
) -> list[EffectiveNamedSource[T]]:
    """Choose most-specific named sources from general-to-specific roots.

    ``ordered_roots`` must be Global -> Personal -> Project. Later roots replace
    earlier roots for the same name. Shadow fields preserve the replaced sources.
    """
    chosen: dict[str, EffectiveNamedSource[T]] = {}

    for root in ordered_roots:
        resolved_root = Path(root)
        for source in loader(resolved_root):
            name = name_getter(source)
            path = path_getter(source)
            previous = chosen.get(name)
            shadowed_roots: tuple[Path, ...] = ()
            shadowed_paths: tuple[Path, ...] = ()
            if previous is not None:
                shadowed_roots = (*previous.shadowed_roots, previous.root)
                shadowed_paths = (*previous.shadowed_paths, previous.path)
            chosen[name] = EffectiveNamedSource(
                name=name,
                root=resolved_root,
                path=path,
                source=source,
                shadowed_roots=shadowed_roots,
                shadowed_paths=shadowed_paths,
            )

    return [chosen[name] for name in sorted(chosen)]


def build_effective_skill_report(
    logical_layers: Sequence[LogicalSkillRootLayer],
    loader: Callable[[Path], Sequence[T]],
    *,
    name_getter: Callable[[T], str],
    path_getter: Callable[[T], Path],
    physical_roots: Sequence[Path] | None = None,
) -> EffectiveSkillReport[T]:
    """Report logical skill layers separately from deduped physical roots."""
    layers = tuple(
        LogicalSkillRootLayer(
            tier=str(layer.tier),
            brain_id=str(layer.brain_id),
            root=Path(layer.root),
        )
        for layer in logical_layers
    )
    layer_roots = tuple(layer.root for layer in layers)
    roots = _dedupe_roots(physical_roots if physical_roots is not None else layer_roots)
    selection_roots = layer_roots or roots
    choices = choose_effective_named_sources(
        selection_roots,
        loader,
        name_getter=name_getter,
        path_getter=path_getter,
    )
    return EffectiveSkillReport(
        logical_layers=layers,
        physical_roots=roots,
        choices=tuple(choices),
    )


def _dedupe_roots(roots: Iterable[Path]) -> tuple[Path, ...]:
    seen: set[Path] = set()
    deduped: list[Path] = []
    for root in roots:
        path = Path(root)
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path)
    return tuple(deduped)
