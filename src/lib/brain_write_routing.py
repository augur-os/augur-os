from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.lib.brain_context import resolve_active_context
from src.lib.brain_registry_io import load_registry
from src.lib.brain_registry_models import Brain, BrainRegistry, BrainType


@dataclass(frozen=True)
class BrainWriteTarget:
    brain: Brain
    reason: str
    mode: str
    notes_vault_dir: Path
    memory_dir: Path
    knowledge_dir: Path
    packet_root: Path | None = None

    def summary(self) -> dict[str, str]:
        return {
            "id": self.brain.id,
            "type": self.brain.type.value,
            "reason": self.reason,
            "mode": self.mode,
        }


def resolve_write_target(
    *,
    explicit_brain: str | None = None,
    cwd: Path | None = None,
    registry_path: Path | None = None,
) -> BrainWriteTarget:
    """Resolve the destination brain for write operations.

    Order: explicit ``--to`` destination, cwd project brain, personal fallback.
    """
    registry = _load_registry(registry_path)
    if explicit_brain:
        brain = registry.get(explicit_brain)
        if brain is None:
            raise KeyError(f"brain not registered: {explicit_brain}")
        return _target_for(brain, reason="explicit")

    start = cwd or Path.cwd()
    context = resolve_active_context(
        cwd=start,
        registry_path=_resolve_registry_path(registry_path),
    )
    if context.active_brain.type is BrainType.PROJECT:
        return _target_for(context.active_brain, reason="active-project")

    personal = registry.get("personal")
    if personal is not None:
        return _target_for(personal, reason="personal-fallback")

    return _target_for(context.active_brain, reason=context.source)


def _load_registry(registry_path: Path | None) -> BrainRegistry:
    if registry_path is not None:
        return load_registry(registry_path)
    from src.lib.brain_registry import get_registry

    return get_registry()


def _resolve_registry_path(registry_path: Path | None) -> Path | None:
    if registry_path is not None:
        return registry_path
    from src.config.paths import get_brain_registry_path

    return get_brain_registry_path()


def _target_for(brain: Brain, *, reason: str) -> BrainWriteTarget:
    from src.lib.brain_layout import brain_knowledge_dir

    root = Path(brain.data_root)
    mode = "packet" if brain.write_policy == "packets_only" else "direct"
    # Card writers (prompt/url/note) resolve their own capture dir via
    # brain_capture_dir(vault_dir), so the notes vault root is always the brain
    # root. knowledge_dir routes through brain_knowledge_dir so domains layout
    # puts the machine knowledge subtree under _augur/.
    knowledge_dir = brain_knowledge_dir(root)
    notes_vault_dir = root
    # TODO_BUG: memory_dir here (consumed by memory_review/ask_retention) uses
    # the knowledge-memory lineage (legacy knowledge/memory; domains
    # _augur/knowledge/memory), while brain_memory_tiers.memory_dir_for_brain
    # resolves the PERSONAL tier on the tier lineage (legacy memory/; domains
    # _augur/memory). The divergence predates the layout work; the layout
    # routing preserves each system's lineage in both layouts. Unifying the two
    # memory roots needs its own spec/ADR — do not change behavior here.
    memory_dir = knowledge_dir / "memory"
    return BrainWriteTarget(
        brain=brain,
        reason=reason,
        mode=mode,
        notes_vault_dir=notes_vault_dir,
        memory_dir=memory_dir,
        knowledge_dir=knowledge_dir,
        packet_root=(root / "inbox" / "propagation") if mode == "packet" else None,
    )
