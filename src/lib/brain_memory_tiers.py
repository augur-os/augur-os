from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from src.lib.brain_registry_models import Brain, BrainType
from src.lib.brain_stack import BrainStack


@dataclass(frozen=True)
class TierMemoryEntry:
    key: str
    tier: BrainType
    brain_id: str
    memory_dir: Path
    source_path: Path
    description: str = ""
    body: str = ""
    section: str | None = None
    subsection: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


_MEMORY_ITEM_RE = re.compile(r"^\s*-\s+\*\*(?P<key>[^*]+)\*\*:\s*(?P<value>.*)$")
_HANDOFF_TIMESTAMP_KEYS = (
    "reviewed_at",
    "source_created_at",
    "created_at",
    "created",
    "updated_at",
    "updated",
    "_updated",
)
_SOURCE_CLIENT_KEYS = ("source_client", "client", "origin_client", "source")
_SOURCE_CLIENT_PREFIXES = (
    "claude-code",
    "claude",
    "codex",
    "gemini",
    "cursor",
    "copilot",
    "cowork",
)
_TIER_RANK = {
    BrainType.GLOBAL: 0,
    BrainType.PERSONAL: 1,
    BrainType.PROJECT: 2,
}
_HANDOFF_INTRO = (
    "*Compact startup context generated from Augur memory. Full recall is "
    "pull-based: use `/ask`, `memory-search`, or `knowledge-memory-read` when "
    "deeper history is needed.*"
)


def memory_dir_for_brain(brain: Brain) -> Path:
    """Return the canonical memory dir for a brain tier.

    Contract (see test_client_memory_sweep): the PERSONAL tier never uses a
    knowledge/ subdir — its live memory is flat ``root/memory`` in the legacy
    layout and ``root/_augur/memory`` in the domains layout. The legacy vault
    HAS a knowledge/ dir (holding other content), so a knowledge-dir-exists
    probe must never reroute the personal tier.
    """
    from src.lib.brain_layout import brain_layout, vault_machine_dir

    root = Path(brain.data_root)
    if brain.type is BrainType.PROJECT:
        return root / "knowledge" / "memory"
    if brain_layout(root) == "domains":
        # Domains layout: live memory moves under the machine dir (_augur/),
        # preserving the never-knowledge-subdir contract for the personal
        # tier. Applies to ANY brain whose root declares layout: domains —
        # today only the personal vault does; GLOBAL/project brains never do.
        return vault_machine_dir(root, "memory")
    if brain.type is BrainType.GLOBAL and (root / "knowledge").is_dir():
        return root / "knowledge" / "memory"
    return root / "memory"


def tier_memory_dirs(stack: BrainStack) -> tuple[Path, ...]:
    """Return memory dirs from least-specific to most-specific tier."""
    return tuple(memory_dir_for_brain(brain) for brain in stack.ordered())


def resolve_memory_write_target(stack: BrainStack) -> Path | None:
    """Return the most-specific writable memory dir, never the Global tier."""
    target = resolve_memory_write_brain_target(stack)
    return target.memory_dir if target is not None else None


def resolve_memory_write_brain_target(stack: BrainStack):
    """Return the most-specific writable BrainWriteTarget, never Global."""
    from src.lib.brain_write_routing import BrainWriteTarget

    for brain in reversed(stack.ordered()):
        if brain.type is BrainType.GLOBAL:
            continue
        if brain.write_policy == "read_only":
            continue
        root = Path(brain.data_root)
        memory_dir = memory_dir_for_brain(brain)
        if brain.type is BrainType.PROJECT:
            knowledge_dir = root / "knowledge"
            notes_vault_dir = knowledge_dir
        else:
            knowledge_dir = root
            notes_vault_dir = root
        mode = "packet" if brain.write_policy == "packets_only" else "direct"
        return BrainWriteTarget(
            brain=brain,
            reason="tier-memory-write",
            mode=mode,
            notes_vault_dir=notes_vault_dir,
            memory_dir=memory_dir,
            knowledge_dir=knowledge_dir,
            packet_root=(root / "inbox" / "propagation") if mode == "packet" else None,
        )
    return None


def read_memory_union(stack: BrainStack) -> dict[str, TierMemoryEntry]:
    """Read tiered memory entries; most-specific tiers win duplicate keys."""
    union: dict[str, TierMemoryEntry] = {}
    for brain in stack.ordered():
        memory_dir = memory_dir_for_brain(brain)
        for entry in _read_memory_dir(memory_dir, brain=brain):
            union[entry.key] = entry
    return union


def render_memory_union_markdown(stack: BrainStack) -> str:
    """Render the tiered union as a client-projectable MEMORY.md payload."""
    entries = read_memory_union(stack)
    if not entries:
        return ""

    lines = [
        "# Augur Memory",
        "",
        "*Generated from the active Global/User/Project memory union.*",
        "",
        "## Tiered Memory Union",
        "",
    ]
    for key in sorted(entries):
        entry = entries[key]
        summary = entry.description or _first_body_line(entry.body) or entry.key
        lines.append(f"- **{entry.key}**: {summary}")
        lines.append(f"  - Tier: {entry.tier.value}")
        lines.append(f"  - Brain: {entry.brain_id}")
    lines.append("")
    return "\n".join(lines)


def render_memory_handoff_markdown(
    stack: BrainStack,
    *,
    max_entries: int = 8,
    max_bytes: int = 2400,
) -> str:
    """Render compact startup context for native client memory surfaces.

    The handoff is intentionally small. Full memory remains pull-based through
    the Augur memory/search tools and /ask so every client can retrieve exactly
    what the user asks for without loading the whole memory union on startup.
    """
    union = read_memory_union(stack)
    if not union or max_entries <= 0 or max_bytes <= 0:
        return ""

    entries = _select_handoff_entries(union.values(), max_entries=max_entries)
    if not entries:
        return ""

    prefix = [
        "# Augur Cross-Client Handoff",
        "",
        _HANDOFF_INTRO,
        "",
        "## Recent Work",
        "",
    ]
    footer = [
        "",
        "## Retrieval Policy",
        "",
        "- Treat this file as a startup handoff, not canonical memory.",
        "- Use `/ask` or Augur memory tools for targeted recall across clients, brains, and older work.",
        "",
    ]
    lines = [*prefix]
    for entry in entries:
        summary = _compact_text(entry.description or _first_body_line(entry.body) or entry.key, 180)
        details = [f"tier={entry.tier.value}", f"brain={entry.brain_id}"]
        source = _entry_source_label(entry)
        if source:
            details.append(f"source={source}")
        entry_lines = [
            f"- **{entry.key}**: {summary}",
            f"  - {', '.join(details)}",
        ]
        candidate = [*lines, *entry_lines, *footer]
        if len(_join_markdown(candidate).encode("utf-8")) > max_bytes:
            break
        lines.extend(entry_lines)

    lines.extend(footer)
    return _limit_markdown_bytes(lines, max_bytes=max_bytes)


def _select_handoff_entries(
    entries: Iterable[TierMemoryEntry],
    *,
    max_entries: int,
) -> list[TierMemoryEntry]:
    candidates = [entry for entry in entries if _is_handoff_candidate(entry)]
    ordered = sorted(candidates, key=_handoff_sort_key, reverse=True)
    return ordered[:max_entries]


def _is_handoff_candidate(entry: TierMemoryEntry) -> bool:
    if entry.source_path.name.lower() == "readme.md" and not entry.description.strip():
        return False
    return bool((entry.description or entry.body or entry.key).strip())


def _handoff_sort_key(entry: TierMemoryEntry) -> tuple[float, int, str]:
    return (_entry_timestamp(entry), _TIER_RANK.get(entry.tier, 0), entry.key)


def _entry_timestamp(entry: TierMemoryEntry) -> float:
    for key in _HANDOFF_TIMESTAMP_KEYS:
        value = entry.metadata.get(key)
        if value is None:
            continue
        parsed = _parse_timestamp(value)
        if parsed is not None:
            return parsed
    try:
        return entry.source_path.stat().st_mtime
    except OSError:
        return 0.0


def _parse_timestamp(value: Any) -> float | None:
    if isinstance(value, datetime):
        return value.timestamp()
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def _entry_source_label(entry: TierMemoryEntry) -> str:
    for key in _SOURCE_CLIENT_KEYS:
        value = str(entry.metadata.get(key) or "").strip()
        if value:
            return _compact_text(value, 40)
    stem = entry.source_path.stem.lower()
    for prefix in _SOURCE_CLIENT_PREFIXES:
        if stem == prefix or stem.startswith(f"{prefix}_") or stem.startswith(f"{prefix}-"):
            return prefix
    return ""


def _compact_text(value: str, max_chars: int) -> str:
    text = " ".join(value.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _limit_markdown_bytes(lines: list[str], *, max_bytes: int) -> str:
    text = _join_markdown(lines)
    if len(text.encode("utf-8")) <= max_bytes:
        return text

    kept: list[str] = []
    for line in lines:
        candidate = "\n".join([*kept, line])
        if not candidate.endswith("\n"):
            candidate += "\n"
        if len(candidate.encode("utf-8")) > max_bytes:
            break
        kept.append(line)
    if not kept:
        return ""
    text = "\n".join(kept).rstrip() + "\n"
    return text


def _join_markdown(lines: list[str]) -> str:
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text


def _read_memory_dir(memory_dir: Path, *, brain: Brain) -> list[TierMemoryEntry]:
    entries: list[TierMemoryEntry] = []
    entries.extend(_read_entry_files(memory_dir, brain=brain))
    entries.extend(_read_memory_md_items(memory_dir, brain=brain))
    return entries


def _read_entry_files(memory_dir: Path, *, brain: Brain) -> list[TierMemoryEntry]:
    entries_dir = memory_dir / "entries"
    if not entries_dir.is_dir():
        return []

    out: list[TierMemoryEntry] = []
    for path in sorted(entries_dir.glob("*.md")):
        try:
            from src.lib.frontmatter_utils import parse_frontmatter

            meta, body = parse_frontmatter(path, include_sidecar_config=False)
        except Exception:  # noqa: BLE001 - malformed memory entries should not break reads
            continue
        key = str(meta.get("name") or path.stem).strip()
        if not key:
            continue
        out.append(
            TierMemoryEntry(
                key=key,
                tier=brain.type,
                brain_id=brain.id,
                memory_dir=memory_dir,
                source_path=path,
                description=str(meta.get("description") or ""),
                body=body.strip(),
                metadata=dict(meta),
            )
        )
    return out


def _read_memory_md_items(memory_dir: Path, *, brain: Brain) -> list[TierMemoryEntry]:
    path = memory_dir / "MEMORY.md"
    if not path.is_file():
        return []

    section: str | None = None
    subsection: str | None = None
    out: list[TierMemoryEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line.removeprefix("## ").strip()
            subsection = None
            continue
        if line.startswith("### "):
            subsection = line.removeprefix("### ").strip()
            continue
        match = _MEMORY_ITEM_RE.match(line)
        if not match:
            continue
        key = match.group("key").strip()
        if not key:
            continue
        out.append(
            TierMemoryEntry(
                key=key,
                tier=brain.type,
                brain_id=brain.id,
                memory_dir=memory_dir,
                source_path=path,
                description=match.group("value").strip(),
                section=section,
                subsection=subsection,
            )
        )
    return out


def _first_body_line(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""
