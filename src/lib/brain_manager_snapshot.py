"""Tier-aware Brain Harness manager snapshot and mutations (ADR-785)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import shutil
from typing import Any

from src.lib.brain_effective import EffectiveSet, compute_effective_skills
from src.lib.brain_layered_projection import (
    LayeredCapabilitySource,
    resolve_layered_projection,
)
from src.lib.brain_manifest import STANDARD_BRAIN_FILES
from src.lib.brain_memory_tiers import memory_dir_for_brain
from src.lib.brain_registry_models import Brain, BrainType
from src.lib.brain_stack import BrainStack
from src.lib.frontmatter_utils import parse_frontmatter

MANAGER_GROUPS = {
    "instructions": "Instructions",
    "commands": "Commands",
    "skills": "Skills",
    "subagents": "Subagents",
    "mcp": "MCP",
    "aug_commands": "aug subcommands",
    "memory": "Memory",
    "profile": "Profile",
    "knowledge": "Knowledge",
    "workflows": "Workflows",
}

_DUAL_OWNERSHIP_GROUPS = {"instructions", "commands", "skills", "subagents", "mcp"}
_ROOT_PROFILE_FILES = {"IDENTITY.md", "SOUL.md", "USER.md"}


@dataclass(frozen=True)
class _Occurrence:
    name: str
    path: Path
    tier: BrainType
    brain_id: str
    owner: str = "augur"
    summary: str = ""


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _tier_label(tier: str | BrainType) -> str:
    value = tier.value if isinstance(tier, BrainType) else str(tier)
    return {
        "global": "Global",
        "personal": "User",
        "user": "User",
        "project": "Project",
        "team": "Team",
    }.get(value, value.replace("_", " ").title())


def _normalize_tier(value: str) -> BrainType:
    normalized = value.strip().lower()
    if normalized == "user":
        normalized = "personal"
    try:
        return BrainType(normalized)
    except ValueError as exc:
        raise ValueError(f"unknown tier: {value}") from exc


def _rel_or_abs(path: Path, project_root: Path | None) -> str:
    if project_root is not None:
        try:
            return path.resolve(strict=False).relative_to(project_root.resolve(strict=False)).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def _read_skill_meta(skill_dir: Path) -> dict[str, Any]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return {}
    try:
        frontmatter, _body = parse_frontmatter(skill_md)
    except Exception:
        return {}
    return frontmatter


def _is_skill_dir(path: Path) -> bool:
    return path.is_dir() and (path / "SKILL.md").is_file()


def _is_entry_path(path: Path) -> bool:
    if path.name.startswith(".") or path.name == "README.md":
        return False
    if path.is_dir():
        return True
    return path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml", ".json"}


def _entry_name(path: Path) -> str:
    return path.stem if path.is_file() else path.name


def _tier_details(stack: BrainStack) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for brain in stack.ordered():
        details.append(
            {
                "key": brain.type.value,
                "label": _tier_label(brain.type),
                "brain_id": brain.id,
                "root": str(brain.data_root),
                "writable": brain.type is not BrainType.GLOBAL and brain.write_policy != "read_only",
            }
        )
    return details


def _brain_for_tier(stack: BrainStack, tier: BrainType) -> Brain:
    for brain in stack.ordered():
        if brain.type is tier:
            return brain
    raise ValueError(f"tier is not active in this stack: {tier.value}")


def _effective_from_occurrences(occurrences: Iterable[_Occurrence]) -> dict[str, list[_Occurrence]]:
    grouped: dict[str, list[_Occurrence]] = {}
    seen_roots: set[Path] = set()
    for occurrence in occurrences:
        root = occurrence.path.parent.resolve(strict=False)
        if root in seen_roots and occurrence.path.resolve(strict=False) in {
            item.path.resolve(strict=False) for items in grouped.values() for item in items
        }:
            continue
        grouped.setdefault(occurrence.name, []).append(occurrence)
    return grouped


def _rows_from_grouped(
    capability_type: str,
    grouped: dict[str, list[_Occurrence]],
    *,
    project_root: Path | None,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    shadowed_names: list[str] = []
    for name in sorted(grouped):
        occurrences = grouped[name]
        if not occurrences:
            continue
        winner = occurrences[-1]
        shadowed = occurrences[:-1]
        if shadowed:
            shadowed_names.append(name)
        entries.append(
            _entry_payload(
                capability_type,
                name=name,
                winner=winner,
                shadowed=shadowed,
                all_occurrences=occurrences,
                project_root=project_root,
            )
        )
    return {
        "label": MANAGER_GROUPS[capability_type],
        "entries": entries,
        "effective": len(entries),
        "shadowed": shadowed_names,
    }


def _rows_from_effective_set(
    capability_type: str,
    effective: EffectiveSet,
    *,
    layered_by_tier: dict[BrainType, str],
    project_root: Path | None,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for name, entry in sorted(effective.entries.items()):
        winner = _Occurrence(
            name=name,
            path=entry.winner,
            tier=entry.winner_tier,
            brain_id=layered_by_tier[entry.winner_tier],
        )
        shadowed = [
            _Occurrence(
                name=name,
                path=path,
                tier=tier,
                brain_id=layered_by_tier[tier],
            )
            for tier, path in entry.shadowed
        ]
        entries.append(
            _entry_payload(
                capability_type,
                name=name,
                winner=winner,
                shadowed=shadowed,
                all_occurrences=[*shadowed, winner],
                project_root=project_root,
            )
        )
    return {
        "label": MANAGER_GROUPS[capability_type],
        "entries": entries,
        "effective": len(entries),
        "shadowed": effective.shadowed_names(),
    }


def _entry_payload(
    capability_type: str,
    *,
    name: str,
    winner: _Occurrence,
    shadowed: Sequence[_Occurrence],
    all_occurrences: Sequence[_Occurrence],
    project_root: Path | None,
) -> dict[str, Any]:
    actions = _actions_for(capability_type, winner)
    return {
        "id": f"{capability_type}:{name}",
        "capability_type": capability_type,
        "name": name,
        "owner": winner.owner,
        "owner_label": "Augur-managed" if winner.owner == "augur" else winner.owner,
        "winner_tier": winner.tier.value,
        "winner_tier_label": _tier_label(winner.tier),
        "winner_brain_id": winner.brain_id,
        "winner_path": _rel_or_abs(winner.path, project_root),
        "summary": winner.summary,
        "tiers": [
            {
                "tier": item.tier.value,
                "tier_label": _tier_label(item.tier),
                "brain_id": item.brain_id,
                "path": _rel_or_abs(item.path, project_root),
                "status": "effective" if item is winner else "shadowed",
                "owner": item.owner,
            }
            for item in all_occurrences
        ],
        "shadowed": [item.tier.value for item in shadowed],
        "shadowed_entries": [
            {
                "tier": item.tier.value,
                "tier_label": _tier_label(item.tier),
                "brain_id": item.brain_id,
                "path": _rel_or_abs(item.path, project_root),
            }
            for item in shadowed
        ],
        "actions": actions,
    }


def _actions_for(capability_type: str, winner: _Occurrence) -> dict[str, Any]:
    promote_reason = None
    demote_reason = None
    promote_enabled = capability_type in _DUAL_OWNERSHIP_GROUPS and winner.owner != "augur"
    demote_enabled = capability_type == "skills" and winner.owner == "augur"
    if winner.owner == "augur":
        promote_reason = "Already Augur-managed"
    if capability_type not in _DUAL_OWNERSHIP_GROUPS:
        promote_reason = "Augur-only capability"
        demote_reason = "Augur-only capability"
        demote_enabled = False
    elif capability_type != "skills":
        demote_reason = "Only skill demotion is implemented in ADR-785"
        demote_enabled = False
    elif winner.tier is BrainType.GLOBAL:
        demote_reason = "Global tier is read-only"
        demote_enabled = False

    return {
        "promote": {
            "enabled": promote_enabled,
            "tool": "harness-promote-capability",
            "reason": promote_reason,
        },
        "demote": {
            "enabled": demote_enabled,
            "tool": "harness-demote-capability",
            "reason": demote_reason,
        },
    }


def _occurrences_from_roots(
    layers: Sequence[LayeredCapabilitySource],
    *,
    roots_of: Callable[[LayeredCapabilitySource], tuple[Path, ...]],
    is_entry: Callable[[Path], bool] = _is_entry_path,
    name_of: Callable[[Path], str] = _entry_name,
) -> list[_Occurrence]:
    occurrences: list[_Occurrence] = []
    seen_roots: set[Path] = set()
    for layer in layers:
        for root in roots_of(layer):
            resolved_root = Path(root).resolve(strict=False)
            if resolved_root in seen_roots:
                continue
            seen_roots.add(resolved_root)
            if not Path(root).is_dir():
                continue
            for child in sorted(Path(root).iterdir()):
                if not is_entry(child):
                    continue
                occurrences.append(
                    _Occurrence(
                        name=name_of(child),
                        path=child,
                        tier=layer.tier,
                        brain_id=layer.brain_id,
                    )
                )
    return occurrences


def _instruction_occurrences(layers: Sequence[LayeredCapabilitySource]) -> list[_Occurrence]:
    occurrences: list[_Occurrence] = []
    seen: set[Path] = set()
    for layer in layers:
        path = layer.sources.rules
        resolved = path.resolve(strict=False)
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        occurrences.append(
            _Occurrence(
                name="agent-rules",
                path=path,
                tier=layer.tier,
                brain_id=layer.brain_id,
            )
        )
    return occurrences


def _skill_frontmatter_occurrences(
    layers: Sequence[LayeredCapabilitySource],
    *,
    field: str,
    capability_type: str,
) -> list[_Occurrence]:
    occurrences: list[_Occurrence] = []
    seen_roots: set[Path] = set()
    for layer in layers:
        for root in layer.sources.skill_roots:
            resolved_root = root.resolve(strict=False)
            if resolved_root in seen_roots or not root.is_dir():
                continue
            seen_roots.add(resolved_root)
            for child in sorted(root.iterdir()):
                if not _is_skill_dir(child):
                    continue
                meta = _read_skill_meta(child)
                values = meta.get(field) or []
                for name, summary in _normalize_frontmatter_items(values):
                    occurrences.append(
                        _Occurrence(
                            name=name,
                            path=child / "SKILL.md",
                            tier=layer.tier,
                            brain_id=layer.brain_id,
                            summary=summary,
                        )
                    )
    return occurrences


def _normalize_frontmatter_items(values: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if not isinstance(values, list):
        return out
    for value in values:
        if isinstance(value, str) and value.strip():
            out.append((value.strip(), ""))
        elif isinstance(value, dict):
            raw_name = value.get("id") or value.get("name")
            if raw_name:
                out.append((str(raw_name).strip(), str(value.get("description") or "")))
    return out


def _memory_occurrences(stack: BrainStack) -> list[_Occurrence]:
    occurrences: list[_Occurrence] = []
    seen_dirs: set[Path] = set()
    for brain in stack.ordered():
        memory_dir = memory_dir_for_brain(brain)
        resolved = memory_dir.resolve(strict=False)
        if resolved in seen_dirs or not memory_dir.is_dir():
            continue
        seen_dirs.add(resolved)
        try:
            from src.lib.brain_memory_tiers import _read_memory_dir

            entries = _read_memory_dir(memory_dir, brain=brain)
        except Exception:
            entries = []
        for entry in entries:
            occurrences.append(
                _Occurrence(
                    name=entry.key,
                    path=entry.source_path,
                    tier=brain.type,
                    brain_id=brain.id,
                    summary=entry.description,
                )
            )
    return occurrences


def _profile_occurrences(stack: BrainStack) -> list[_Occurrence]:
    occurrences: list[_Occurrence] = []
    seen_standard_paths: set[Path] = set()
    seen_roots: set[Path] = set()
    for brain in stack.ordered():
        root = Path(brain.data_root)

        for filename in STANDARD_BRAIN_FILES:
            if filename not in _ROOT_PROFILE_FILES:
                continue
            path = root / filename
            if not path.is_file():
                continue
            resolved = path.resolve(strict=False)
            if resolved in seen_standard_paths:
                continue
            seen_standard_paths.add(resolved)
            occurrences.append(
                _Occurrence(
                    name=path.stem.lower(),
                    path=path,
                    tier=brain.type,
                    brain_id=brain.id,
                )
            )

        for profile_root in (root / "profile", root / "knowledge" / "profile"):
            resolved = profile_root.resolve(strict=False)
            if resolved in seen_roots or not profile_root.is_dir():
                continue
            seen_roots.add(resolved)
            for path in sorted(profile_root.rglob("*.md")):
                if path.name == "README.md":
                    continue
                occurrences.append(
                    _Occurrence(
                        name=path.stem,
                        path=path,
                        tier=brain.type,
                        brain_id=brain.id,
                    )
                )
    return occurrences


def _knowledge_occurrences(stack: BrainStack) -> list[_Occurrence]:
    occurrences: list[_Occurrence] = []
    seen_dirs: set[Path] = set()
    for brain in stack.ordered():
        root = Path(brain.data_root)
        knowledge_root = root / "knowledge" if (root / "knowledge").is_dir() else root
        for subdir in ("notes", "sources", "wiki"):
            directory = knowledge_root / subdir
            resolved = directory.resolve(strict=False)
            if resolved in seen_dirs or not directory.is_dir():
                continue
            seen_dirs.add(resolved)
            for path in sorted(directory.rglob("*.md")):
                if path.name == "README.md":
                    continue
                occurrences.append(
                    _Occurrence(
                        name=path.stem,
                        path=path,
                        tier=brain.type,
                        brain_id=brain.id,
                    )
                )
    return occurrences


def _skill_target_root(brain: Brain) -> Path:
    return Path(brain.data_root) / "capabilities" / "skills"


def _copy_dir(
    source: Path,
    target: Path,
    *,
    replace: bool,
    remove_source: bool,
) -> None:
    resolved_source = source.expanduser().resolve(strict=True)
    if not resolved_source.is_dir() or not (resolved_source / "SKILL.md").is_file():
        raise ValueError("source_path must be a skill directory containing SKILL.md")
    if target.exists():
        if not replace:
            raise ValueError(f"target already exists: {target}")
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(resolved_source, target)
    if remove_source and resolved_source != target.resolve(strict=False):
        shutil.rmtree(resolved_source)


def harness_manager_snapshot(
    stack: BrainStack,
    *,
    project_root: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return the tiered effective/shadowed manager snapshot for the active stack."""
    layered = resolve_layered_projection(stack, project_root=project_root)
    layered_by_tier = {layer.tier: layer.brain_id for layer in layered.layers}

    groups: dict[str, Any] = {
        key: {"label": label, "entries": [], "effective": 0, "shadowed": []} for key, label in MANAGER_GROUPS.items()
    }
    groups["skills"] = _rows_from_effective_set(
        "skills",
        compute_effective_skills(layered),
        layered_by_tier=layered_by_tier,
        project_root=project_root,
    )
    groups["instructions"] = _rows_from_grouped(
        "instructions",
        _effective_from_occurrences(_instruction_occurrences(layered.layers)),
        project_root=project_root,
    )
    groups["subagents"] = _rows_from_grouped(
        "subagents",
        _effective_from_occurrences(
            _occurrences_from_roots(layered.layers, roots_of=lambda layer: layer.sources.agent_roots)
        ),
        project_root=project_root,
    )
    groups["workflows"] = _rows_from_grouped(
        "workflows",
        _effective_from_occurrences(
            _occurrences_from_roots(layered.layers, roots_of=lambda layer: layer.sources.workflow_roots)
        ),
        project_root=project_root,
    )
    groups["mcp"] = _rows_from_grouped(
        "mcp",
        _effective_from_occurrences(
            _skill_frontmatter_occurrences(
                layered.layers,
                field="x-augur-mcp-tools",
                capability_type="mcp",
            )
        ),
        project_root=project_root,
    )
    groups["commands"] = _rows_from_grouped(
        "commands",
        _effective_from_occurrences(
            _skill_frontmatter_occurrences(
                layered.layers,
                field="x-augur-commands",
                capability_type="commands",
            )
        ),
        project_root=project_root,
    )
    groups["memory"] = _rows_from_grouped(
        "memory",
        _effective_from_occurrences(_memory_occurrences(stack)),
        project_root=project_root,
    )
    groups["profile"] = _rows_from_grouped(
        "profile",
        _effective_from_occurrences(_profile_occurrences(stack)),
        project_root=project_root,
    )
    groups["knowledge"] = _rows_from_grouped(
        "knowledge",
        _effective_from_occurrences(_knowledge_occurrences(stack)),
        project_root=project_root,
    )

    details = _tier_details(stack)
    return {
        "success": True,
        "version": "1.0",
        "generated_at": generated_at or _utc_now(),
        "tiers": [tier["key"] for tier in details],
        "tier_details": details,
        "groups": groups,
        "skills": groups["skills"],
    }


def harness_promote_capability(
    stack: BrainStack,
    *,
    capability_type: str,
    name: str,
    source_path: Path | str,
    target_tier: str,
    project_root: Path | None = None,
    replace: bool = False,
    remove_source: bool = False,
) -> dict[str, Any]:
    """Promote a client-native skill directory into an Augur-managed tier."""
    if capability_type not in {"skill", "skills"}:
        return {"success": False, "message": "only skill promotion is supported"}
    tier = _normalize_tier(target_tier)
    if tier is BrainType.GLOBAL:
        return {"success": False, "message": "Global tier is read-only"}
    brain = _brain_for_tier(stack, tier)
    if brain.write_policy == "read_only":
        return {"success": False, "message": f"{tier.value} tier is read-only"}
    target = _skill_target_root(brain) / name
    try:
        _copy_dir(Path(source_path), target, replace=replace, remove_source=remove_source)
    except (OSError, ValueError) as exc:
        return {"success": False, "message": str(exc)}
    return {
        "success": True,
        "message": "Skill promoted",
        "target_path": str(target),
        "snapshot": harness_manager_snapshot(stack, project_root=project_root),
    }


def harness_demote_capability(
    stack: BrainStack,
    *,
    capability_type: str,
    name: str,
    target_client: str,
    target_scope: str = "local",
    client_skill_dirs: dict[str, Path] | None = None,
    project_root: Path | None = None,
    replace: bool = False,
    remove_source: bool = False,
) -> dict[str, Any]:
    """Demote an Augur-managed skill to one client skill directory."""
    if capability_type not in {"skill", "skills"}:
        return {"success": False, "message": "only skill demotion is supported"}
    snapshot = harness_manager_snapshot(stack, project_root=project_root)
    skill_rows = {row["name"]: row for row in snapshot["groups"]["skills"]["entries"]}
    row = skill_rows.get(name)
    if row is None:
        return {"success": False, "message": f"skill not found: {name}"}
    if row["winner_tier"] == BrainType.GLOBAL.value and remove_source:
        return {"success": False, "message": "Global tier is read-only"}
    source = Path(row["winner_path"])
    if project_root is not None and not source.is_absolute():
        source = project_root / source
    if client_skill_dirs is None:
        from src.config.paths import get_client_skill_dirs

        client_skill_dirs = get_client_skill_dirs()
    normalized_scope = "global" if target_scope in {"global", "home", "user"} else "local"
    tag = f"{target_client}-{normalized_scope}"
    target_parent = client_skill_dirs.get(tag)
    if target_parent is None:
        return {"success": False, "message": f"client skill directory is not configured: {tag}"}
    target = target_parent / name
    try:
        _copy_dir(source, target, replace=replace, remove_source=remove_source)
    except (OSError, ValueError) as exc:
        return {"success": False, "message": str(exc)}

    verify: dict[str, Any] | None = None
    try:
        from src.lib.brain_verify_harness import verify_harness_summary

        verify = verify_harness_summary(
            stack,
            clients=(target_client,),
            client_dirs=client_skill_dirs,
            project_root=project_root,
        )
    except Exception:
        verify = None
    return {
        "success": True,
        "message": "Skill demoted",
        "target_path": str(target),
        "snapshot": harness_manager_snapshot(stack, project_root=project_root),
        "verify_harness": verify,
    }
