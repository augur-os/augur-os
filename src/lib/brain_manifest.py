from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from src.lib.brain_registry_models import Brain, BrainType
from src.lib.frontmatter_utils import write_frontmatter

BRAIN_MANIFEST_NAME = "BRAIN.yaml"
PROJECT_BRAIN_DIRNAME = "project-brain"
BRAIN_SCHEMA_VERSION = 1

STANDARD_BRAIN_FILES = (
    "IDENTITY.md",
    "SOUL.md",
    "USER.md",
    "AGENTS.md",
    "MEMORY.md",
    "TOOLS.md",
    "HEARTBEAT.md",
)

_STANDARD_BRAIN_FILE_TEMPLATES: dict[str, tuple[dict[str, str], str]] = {
    "IDENTITY.md": (
        {
            "title": "Brain Identity",
            "brain_scope": "unknown",
            "status": "active",
            "owner": "unknown",
        },
        ("# Identity\n\n" "Describe this brain's public identity, scope, owner, and intended use.\n"),
    ),
    "SOUL.md": (
        {
            "title": "Brain Soul",
            "brain_scope": "unknown",
            "status": "active",
            "owner": "unknown",
        },
        ("# Soul\n\n" "Describe the durable persona, values, tone, and behavioral boundaries " "for this brain.\n"),
    ),
    "USER.md": (
        {
            "title": "Brain User Context",
            "brain_scope": "unknown",
            "status": "active",
            "owner": "unknown",
        },
        ("# User Context\n\n" "Describe the human, team, or project user context this brain should " "optimize for.\n"),
    ),
    "AGENTS.md": (
        {
            "title": "Brain Agent Instructions",
            "brain_scope": "unknown",
            "status": "active",
            "owner": "unknown",
        },
        (
            "# Agent Instructions\n\n"
            "Describe portable operating instructions authored by this brain. "
            "Client-native instruction files remain generated projections.\n"
        ),
    ),
    "MEMORY.md": (
        {
            "title": "Brain Memory Entrypoint",
            "brain_scope": "unknown",
            "status": "active",
            "owner": "unknown",
        },
        ("# Memory\n\n" "Summarize compact durable memory and point agents to deeper memory " "retrieval surfaces.\n"),
    ),
    "TOOLS.md": (
        {
            "title": "Brain Tool Conventions",
            "brain_scope": "unknown",
            "status": "active",
            "owner": "unknown",
        },
        (
            "# Tools\n\n"
            "Describe tool conventions and local environment notes. Tool authority "
            "remains governed by Augur policy and MCP configuration.\n"
        ),
    ),
    "HEARTBEAT.md": (
        {
            "title": "Brain Heartbeat",
            "brain_scope": "unknown",
            "status": "active",
            "owner": "unknown",
        },
        (
            "# Heartbeat\n\n"
            "Describe recurring routine intent and review checklists. Scheduling "
            "remains owned by Augur routines.\n"
        ),
    ),
}


def standard_brain_default_body(name: str) -> str | None:
    """Return the scaffold default markdown body for a standard brain file.

    Used to detect unfilled placeholder files so projections can skip them.
    Returns None for unknown file names.
    """
    entry = _STANDARD_BRAIN_FILE_TEMPLATES.get(name)
    return entry[1] if entry else None


_SKELETON_DIRS_KNOWLEDGE = (
    "capabilities/skills",
    "capabilities/agents",
    "knowledge/memory/entries",
    "knowledge/notes",
    "knowledge/sources",
    "knowledge/wiki",
    "decisions/adrs",
    "config",
)

_SKELETON_DIRS_DOMAINS = (
    "_augur/capabilities/skills",
    "_augur/capabilities/agents",
    "_augur/knowledge/memory/entries",
    "_augur/config",
    "_augur/decisions/adrs",
    "_augur/archive",
    "inbox",
    "wiki",
    "sources",
)


def _skeleton_dirs(layout: str = "knowledge") -> tuple[str, ...]:
    return _SKELETON_DIRS_DOMAINS if layout == "domains" else _SKELETON_DIRS_KNOWLEDGE


def brain_skeleton_paths(layout: str = "knowledge") -> frozenset[str]:
    """All brain-relative skeleton dir paths, including implied parents.

    Hygiene/alignment scanners must treat these as intentional structure:
    brain-init scaffolds them, so flagging them as orphan or removing them
    when empty would fight the scaffold.

    Pass ``layout="domains"`` for a brain using the domains layout.
    """
    paths: set[str] = set()
    for rel in _skeleton_dirs(layout):
        parts = rel.split("/")
        for i in range(1, len(parts) + 1):
            paths.add("/".join(parts[:i]))
    return frozenset(paths)


def brain_skeleton_top_dirs(layout: str = "knowledge") -> frozenset[str]:
    """Top-level dir names scaffolded by brain-init.

    Pass ``layout="domains"`` for a brain using the domains layout.
    """
    return frozenset(rel.split("/", 1)[0] for rel in _skeleton_dirs(layout))


def is_brain_root(path: Path) -> bool:
    """True when path is a brain data root (has a BRAIN.yaml manifest)."""
    return (path / BRAIN_MANIFEST_NAME).is_file()


@dataclass(frozen=True)
class BrainManifest:
    schema_version: int
    id: str
    type: BrainType
    root: str
    attached_project: str | None = None
    description: str | None = None
    layout: str | None = None

    @classmethod
    def from_brain(
        cls,
        brain: Brain,
        attached_project: Path | None = None,
        layout: str | None = None,
    ) -> BrainManifest:
        return cls(
            schema_version=BRAIN_SCHEMA_VERSION,
            id=brain.id,
            type=brain.type,
            root=str(brain.data_root),
            attached_project=str(attached_project) if attached_project else None,
            description=brain.description,
            layout=layout,
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BrainManifest:
        version = raw.get("schema_version")
        if version != BRAIN_SCHEMA_VERSION:
            raise ValueError(f"unsupported BRAIN.yaml schema_version: {version}")
        brain_id = _required_string(raw, "id")
        type_value = _required_string(raw, "type")
        root = _required_string(raw, "root")
        try:
            brain_type = BrainType(type_value)
        except ValueError as exc:
            raise ValueError(f"invalid brain type: {raw.get('type')}") from exc
        return cls(
            schema_version=version,
            id=brain_id,
            type=brain_type,
            root=root,
            attached_project=_optional_string(raw.get("attached_project")),
            description=_optional_string(raw.get("description")),
            layout=_optional_string(raw.get("layout")),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "id": self.id,
            "type": self.type.value,
            "root": self.root,
        }
        if self.attached_project is not None:
            data["attached_project"] = self.attached_project
        if self.description is not None:
            data["description"] = self.description
        if self.layout is not None:
            data["layout"] = self.layout
        return data


def ensure_brain_skeleton(root: Path) -> None:
    from src.lib.brain_layout import brain_layout

    root.mkdir(parents=True, exist_ok=True)
    layout = brain_layout(root)
    for rel in _skeleton_dirs(layout):
        (root / rel).mkdir(parents=True, exist_ok=True)
    _ensure_standard_brain_files(root)


def _ensure_standard_brain_files(root: Path) -> None:
    for filename in STANDARD_BRAIN_FILES:
        path = root / filename
        if path.exists():
            continue
        metadata, body = _STANDARD_BRAIN_FILE_TEMPLATES[filename]
        write_frontmatter(path, metadata, body)


def _same_location(base: Path, existing_value: str, new_value: str | None) -> bool:
    """True when an existing manifest path string and the new one resolve to the
    same filesystem location (so the existing string's style can be preserved)."""
    if new_value is None:
        return False
    try:
        existing_resolved = (base / existing_value).resolve()
        new_resolved = Path(new_value).resolve()
    except (OSError, ValueError, RuntimeError):
        return False
    return existing_resolved == new_resolved


def _preserve_manifest_path_style(root: Path, manifest: BrainManifest) -> BrainManifest:
    """Keep the committed manifest's ``root``/``attached_project`` path *style*.

    ``BrainManifest.from_brain`` (and the project-init heal path) serialize
    registry-absolute paths, but the committed ``project-brain/BRAIN.yaml`` uses
    the portable relative form (``root: .``, ``attached_project: ..``). Rewriting
    absolute machine paths dirties the repo on every ``aug sync``/``project init``
    — and that working-tree churn is what leaked ``/Users/<name>`` paths into a
    public release tree. When the existing string resolves to the same location
    as the new value, keep the existing string so the portable form survives;
    only write a new path when it genuinely points somewhere else.
    """
    path = root / BRAIN_MANIFEST_NAME
    if not path.is_file():
        return manifest
    try:
        existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return manifest
    if not isinstance(existing, dict):
        return manifest

    updates: dict[str, Any] = {}
    existing_root = existing.get("root")
    if isinstance(existing_root, str) and existing_root and _same_location(root, existing_root, manifest.root):
        updates["root"] = existing_root
    existing_attached = existing.get("attached_project")
    if (
        isinstance(existing_attached, str)
        and existing_attached
        and _same_location(root, existing_attached, manifest.attached_project)
    ):
        updates["attached_project"] = existing_attached
    return replace(manifest, **updates) if updates else manifest


def write_brain_manifest(root: Path, manifest: BrainManifest) -> Path:
    # Preserve a layout declared in the existing manifest when the caller did
    # not set one — the layout is a brain-local property (e.g. the domains
    # reorg) that the registry does not model; dropping it on rewrite would
    # silently flip the brain back to the legacy layout.
    if manifest.layout is None:
        path = root / BRAIN_MANIFEST_NAME
        if path.is_file():
            try:
                existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                existing = {}
            if isinstance(existing, dict) and existing.get("layout"):
                manifest = replace(manifest, layout=str(existing["layout"]))
    # Preserve the committed relative path style for root/attached_project so a
    # rewrite does not clobber it with machine-specific absolute paths.
    manifest = _preserve_manifest_path_style(root, manifest)
    ensure_brain_skeleton(root)
    path = root / BRAIN_MANIFEST_NAME
    path.write_text(
        yaml.safe_dump(manifest.to_dict(), sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    # The manifest may have changed the layout; long-lived processes resolve
    # layout through the lru-cached brain_layout — invalidate it.
    from src.lib.brain_layout import brain_layout

    brain_layout.cache_clear()
    return path


def read_brain_manifest(path: Path) -> BrainManifest:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(f"invalid BRAIN.yaml content: {path}")
    return BrainManifest.from_dict(raw)


def project_brain_root_for(project_root: Path) -> Path:
    return project_root.resolve() / PROJECT_BRAIN_DIRNAME


def find_project_brain_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        brain_root = candidate / PROJECT_BRAIN_DIRNAME
        if (brain_root / BRAIN_MANIFEST_NAME).is_file():
            return brain_root
    return None


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _required_string(raw: dict[str, Any], field: str) -> str:
    value = raw.get(field)
    if value is None:
        raise ValueError(f"missing required BRAIN.yaml field: {field}")
    text = str(value)
    if not text.strip():
        raise ValueError(f"missing required BRAIN.yaml field: {field}")
    return text
