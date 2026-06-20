from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.lib.brain_context import ActiveBrainContext, resolve_active_context
from src.lib.brain_registry_io import load_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)

GLOBAL_BRAIN_ID = "augur-core"


def resolve_global_brain(*, core_root: Path | None = None) -> Brain:
    """Synthesize the read-only Global (Augur-core) brain.

    The Global tier is the installed Augur platform; it is never stored in the
    registry and is never a write target (write_policy=read_only). Its data_root
    is the Augur core BRAIN root — the directory that holds ``capabilities/`` and
    ``instructions/`` — so projection resolves real capability roots, consistent
    with the personal and project tiers. In the Augur dev repo this is
    ``<repo>/project-brain``, which coincides with the project-augur source; the
    layered merge dedupes the coincident roots (ADR-781 D10).
    """
    root = (core_root if core_root is not None else _default_core_root()).resolve()
    return Brain(
        id=GLOBAL_BRAIN_ID,
        type=BrainType.GLOBAL,
        data_root=root,
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
        write_policy="read_only",
        description="Augur core (installed platform)",
    )


def _default_core_root() -> Path:
    from src.config.paths import get_project_root
    from src.lib.brain_manifest import PROJECT_BRAIN_DIRNAME

    return get_project_root() / PROJECT_BRAIN_DIRNAME


@dataclass(frozen=True)
class BrainStack:
    global_brain: Brain
    user_brain: Brain | None
    project: ActiveBrainContext | None

    def ordered(self) -> tuple[Brain, ...]:
        """Tiers from least specific (global) to most specific (project)."""
        tiers: list[Brain] = [self.global_brain]
        if self.user_brain is not None:
            tiers.append(self.user_brain)
        if self.project is not None:
            tiers.append(self.project.active_brain)
        return tuple(tiers)

    def most_specific(self) -> Brain:
        return self.ordered()[-1]

    def to_header_dict(self) -> dict[str, object]:
        stack: dict[str, object] = {"global": _tier_block(self.global_brain)}
        if self.user_brain is not None:
            stack["user"] = _tier_block(self.user_brain)
        if self.project is not None:
            stack["project"] = _tier_block(self.project.active_brain)
        return {"augur_stack": stack, "generated_projection": True}


def resolve_active_stack(
    *,
    cwd: Path | None = None,
    registry_path: Path | None = None,
    explicit_brain: str | None = None,
    explicit_project: Path | None = None,
    core_root: Path | None = None,
) -> BrainStack:
    """Resolve the ordered Global -> User -> Project brain stack.

    Global is always present (synthesized). User is the registry's single
    personal brain, if any. Project is present only when an active project brain
    resolves for ``cwd`` (delegated to the retained ``resolve_active_context``).
    """
    global_brain = resolve_global_brain(core_root=core_root)
    registry = _load_registry_if_present(registry_path)
    user_brain = _find_personal(registry) if registry is not None else None

    project_ctx: ActiveBrainContext | None = None
    try:
        ctx = resolve_active_context(
            cwd=cwd,
            registry_path=registry_path,
            explicit_brain=explicit_brain,
            explicit_project=explicit_project,
        )
    except KeyError:
        ctx = None
    if ctx is not None and ctx.active_brain.type is BrainType.PROJECT:
        project_ctx = ctx

    return BrainStack(
        global_brain=global_brain,
        user_brain=user_brain,
        project=project_ctx,
    )


def _tier_block(brain: Brain) -> dict[str, str]:
    return {
        "id": brain.id,
        "type": brain.type.value,
        "root": str(brain.data_root),
    }


def _find_personal(registry: BrainRegistry) -> Brain | None:
    for brain in registry.brains.values():
        if brain.type is BrainType.PERSONAL:
            return brain
    return None


def _load_registry_if_present(registry_path: Path | None) -> BrainRegistry | None:
    if registry_path is None:
        try:
            from src.lib.brain_registry import get_registry

            return get_registry()
        except Exception:
            return None
    if not registry_path.is_file():
        return None
    return load_registry(registry_path)
