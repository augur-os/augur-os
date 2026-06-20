"""Shared YAML-frontmatter utilities for markdown files.

Provides parse, write, and collection-loading functions used across
the ADR, action, and vault migration phases (ADR-404), plus canonical
skill metadata loaders for SKILL.md/config.yaml discovery.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_SYSTEM_FIELD_READ_ALIASES = {
    "_article_metadata": "article_metadata",
    "_classification_basis": "classification_basis",
    "_compiler_version": "compiler_version",
    "_confidence": "confidence",
    "_content_kind": "content_kind",
    "_hub": "hub",
    "_intent": "intent",
    "_page_type": "page_type",
    "_rewrite_signal_fingerprint": "rewrite_signal_fingerprint",
    "_skill_candidates": "skill_candidates",
    "_source_fingerprint": "source_fingerprint",
    "_source_type": "source_type",
    "_sources": "sources",
    "_updated": "updated",
    "_wiki_compile": "wiki_compile",
}
VAULT_SYSTEM_FIELD_MAP = {legacy_key: system_key for system_key, legacy_key in _SYSTEM_FIELD_READ_ALIASES.items()}


def is_system_field(key: object) -> bool:
    """Return True for Augur-managed vault system metadata fields."""
    return isinstance(key, str) and key.startswith("_")


def split_system_user(meta: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Partition frontmatter into system and user-owned fields.

    Relative key order is preserved within each partition so callers can
    round-trip user-facing properties without reshuffling them.
    """
    system: dict[str, Any] = {}
    user: dict[str, Any] = {}
    for key, value in meta.items():
        if is_system_field(key):
            system[key] = value
        else:
            user[key] = value
    return system, user


def merge_system_user(system: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    """Merge user frontmatter with system frontmatter for vault-note writes.

    User fields are kept first and cannot be overwritten by non-system keys in
    the system payload. System fields must use the ``_`` convention.
    """
    merged: dict[str, Any] = {}
    for key, value in user.items():
        if not is_system_field(key):
            merged[key] = value
    for key, value in system.items():
        if is_system_field(key):
            merged[key] = value
    return merged


def merge_vault_frontmatter(
    existing_meta: dict[str, Any],
    metadata: dict[str, Any],
    *,
    system_field_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Merge a vault-note metadata update through the system/user boundary."""
    field_map = system_field_map or VAULT_SYSTEM_FIELD_MAP
    existing_system, existing_user = split_system_user(existing_meta)
    incoming_system: dict[str, Any] = {}
    incoming_user: dict[str, Any] = {}

    for key, value in metadata.items():
        if value is None:
            continue
        system_key = field_map.get(key) if isinstance(key, str) else None
        if system_key is not None:
            incoming_system[system_key] = value
        elif is_system_field(key):
            incoming_system[str(key)] = value
        elif isinstance(key, str):
            incoming_user[key] = value

    system_keys = set(existing_system) | set(incoming_system)
    for legacy_key, system_key in field_map.items():
        if system_key in system_keys:
            existing_user.pop(legacy_key, None)

    user = dict(existing_user)
    user.update(incoming_user)
    system = dict(existing_system)
    system.update(incoming_system)
    return merge_system_user(system, user)


def write_vault_frontmatter(path: Path, metadata: dict[str, Any], body: str) -> None:
    """Write a vault note while preserving user fields and hiding system fields."""
    existing_meta: dict[str, Any] = {}
    if path.exists():
        existing_meta, _ = parse_frontmatter(path, include_sidecar_config=False)
    write_frontmatter(path, merge_vault_frontmatter(existing_meta, metadata), body)


def _wikilink_targets(value: str) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for match in _WIKILINK_RE.finditer(value):
        target = match.group(1).strip()
        if target and target not in seen:
            seen.add(target)
            targets.append(target)
    return targets


def extract_relationships(meta: dict[str, Any]) -> dict[str, list[str]]:
    """Extract frontmatter wikilink relationships from any field.

    The scan is deliberately field-name agnostic: every string leaf containing
    ``[[wikilinks]]`` becomes a relationship edge. Nested dict fields are
    reported with dotted paths to preserve the exact source field.
    """
    relationships: dict[str, list[str]] = {}

    def add_targets(field: str, value: str) -> None:
        targets = _wikilink_targets(value)
        if not targets:
            return
        existing = relationships.setdefault(field, [])
        seen = set(existing)
        for target in targets:
            if target not in seen:
                seen.add(target)
                existing.append(target)

    def visit(field: str, value: Any) -> None:
        if isinstance(value, str):
            add_targets(field, value)
            return
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                if not isinstance(child_key, str):
                    continue
                child_field = f"{field}.{child_key}" if field else child_key
                visit(child_field, child_value)
            return
        if isinstance(value, list):
            for item in value:
                visit(field, item)

    for key, value in meta.items():
        if isinstance(key, str):
            visit(key, value)
    return relationships


def _apply_system_field_read_aliases(meta: dict[str, Any]) -> dict[str, Any]:
    """Expose temporary read aliases for migrated vault system fields.

    TODO_CLEANUP(ADR-571): remove after the vault migration proof shows no
    live consumers read pre-ADR non-underscore compiler/source-card fields.
    Writes must use the underscore keys and merge_system_user().
    """
    for system_key, legacy_key in _SYSTEM_FIELD_READ_ALIASES.items():
        if system_key in meta and legacy_key not in meta:
            meta[legacy_key] = meta[system_key]
    return meta


def parse_frontmatter(
    path: Path,
    *,
    include_sidecar_config: bool = True,
) -> tuple[dict[str, Any], str]:
    """Parse a markdown file with optional YAML frontmatter.

    Returns (metadata_dict, body_string). If no frontmatter found,
    metadata_dict is empty and body_string is the full file content.
    """
    content = path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        return {}, content

    # Find closing ---
    end = content.find("\n---", 4)
    if end == -1:
        return {}, content

    yaml_block = content[4:end]
    body = content[end + 4 :]  # skip \n---
    if body.startswith("\n"):
        body = body[1:]

    try:
        meta = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        return {}, content

    if not isinstance(meta, dict):
        return {}, content

    # Merge x-augur-config from sidecar file if pointer is present.
    # When SKILL.md frontmatter contains ``x-augur-config-file: config.yaml``
    # (and no inline x-augur-config), the sidecar is loaded and injected so
    # read-only consumers see a unified view without needing code changes.
    # Writers that need the raw on-disk frontmatter can opt out.
    config_file = meta.get("x-augur-config-file")
    if include_sidecar_config and config_file and "x-augur-config" not in meta:
        sidecar = path.parent / config_file
        if sidecar.exists():
            try:
                cfg = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
                if isinstance(cfg, dict):
                    meta["x-augur-config"] = cfg
            except yaml.YAMLError:
                pass  # Sidecar parse failure — proceed without config

    return _apply_system_field_read_aliases(meta), body


def _resolve_skill_md_path(skill_path: Path) -> Path:
    """Return the canonical SKILL.md path for a skill dir or SKILL.md path."""
    return skill_path if skill_path.name == "SKILL.md" else skill_path / "SKILL.md"


def load_skill_frontmatter(
    skill_path: Path,
    *,
    include_sidecar_config: bool = True,
) -> dict[str, Any]:
    """Load merged SKILL.md frontmatter for a skill directory or SKILL.md path."""
    skill_md = _resolve_skill_md_path(skill_path)
    if not skill_md.is_file():
        return {}
    try:
        meta, _body = parse_frontmatter(
            skill_md,
            include_sidecar_config=include_sidecar_config,
        )
    except Exception:
        return {}
    return meta if isinstance(meta, dict) else {}


def get_skill_config_sidecar(skill_path: Path) -> Path | None:
    """Return the configured sidecar config path for a skill, if declared."""
    skill_md = _resolve_skill_md_path(skill_path)
    frontmatter = load_skill_frontmatter(skill_md, include_sidecar_config=False)
    config_file = frontmatter.get("x-augur-config-file")
    if isinstance(config_file, str) and config_file:
        return skill_md.parent / config_file
    return None


def load_skill_contract(skill_path: Path) -> dict[str, Any]:
    """Load canonical skill metadata plus compatibility aliases.

    Returns a normalized dict built from SKILL.md frontmatter and optional
    ``config.yaml`` sidecar so older consumers can stop reading retired
    ``augur/augur.yaml`` files directly.
    """
    skill_md = _resolve_skill_md_path(skill_path)
    skill_dir = skill_md.parent
    frontmatter, body = parse_frontmatter(skill_md) if skill_md.is_file() else ({}, "")
    if not isinstance(frontmatter, dict):
        return {}

    config = frontmatter.get("x-augur-config")
    if not isinstance(config, dict):
        config = {}

    contributions = config.get("contributions")
    if not isinstance(contributions, dict):
        contributions = {}

    mcp_tools = frontmatter.get("x-augur-mcp-tools")
    normalized_tools = (
        [tool for tool in mcp_tools if isinstance(tool, str) and tool.strip()] if isinstance(mcp_tools, list) else []
    )

    commands = frontmatter.get("x-augur-commands")
    normalized_commands = (
        [command for command in commands if isinstance(command, dict)] if isinstance(commands, list) else []
    )

    contract: dict[str, Any] = {
        "skill_dir": skill_dir,
        "skill_md": skill_md,
        "body": body,
        "frontmatter": frontmatter,
        "config_file": get_skill_config_sidecar(skill_md),
        "name": (
            frontmatter.get("name")
            if isinstance(frontmatter.get("name"), str) and frontmatter.get("name")
            else skill_dir.name
        ),
        "description": (frontmatter.get("description") if isinstance(frontmatter.get("description"), str) else ""),
        "config": config,
        "contributions": contributions,
        "mcp": {"tools": normalized_tools},
        "commands": normalized_commands,
    }
    return contract


def write_frontmatter(path: Path, metadata: dict[str, Any], body: str) -> None:
    """Write a markdown file with YAML frontmatter.

    Serialization options: allow_unicode=True, sort_keys=False,
    default_flow_style=False (block style).
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    yaml_str = yaml.dump(
        dict(metadata),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).rstrip("\n")

    parts = ["---", yaml_str, "---", ""]
    if body:
        parts.append(body)
    content = "\n".join(parts)
    if not content.endswith("\n"):
        content += "\n"

    path.write_text(content, encoding="utf-8")


def stamp_import_metadata(skill_path: Path, source: str, url: str, version: str) -> None:
    """Stamp import origin metadata into a skill's SKILL.md frontmatter.

    Args:
        skill_path: Path to the skill directory (containing SKILL.md).
        source: Origin type — "github", "skills-sh", or "local".
        url: Source URL (repo URL or skills.sh URL).
        version: Version tag or commit SHA at time of import.
    """
    from datetime import date

    skill_md = skill_path / "SKILL.md"
    fm, body = parse_frontmatter(skill_md)
    fm["x-augur-source"] = source
    fm["x-augur-source-url"] = url
    fm["x-augur-source-version"] = version
    fm["x-augur-imported-at"] = date.today().isoformat()
    write_frontmatter(skill_md, fm, body)


def _is_seed_file(md_file: Path) -> bool:
    """Check if a markdown file is a seed file (has ``source: seed`` in frontmatter)."""
    try:
        meta, _ = parse_frontmatter(md_file)
        return meta.get("source") == "seed"
    except Exception:
        return False


def load_collection(
    directory: Path,
    *,
    exclude_seeds: bool = False,
) -> list[dict[str, Any]]:
    """Load all .md files from a directory, returning a list of metadata dicts.

    Each dict contains the frontmatter fields. Files without valid
    frontmatter are skipped. The file stem is added as '_source' key.

    Args:
        directory:     Directory to scan for .md files.
        exclude_seeds: If True, skip files whose frontmatter contains
                       ``source: seed``. Used to load only user-created data
                       from vault directories that may still contain legacy
                       seed copies.
    """
    items: list[dict[str, Any]] = []

    if not directory.is_dir():
        return items

    for md_file in sorted(directory.glob("*.md")):
        meta, _body = parse_frontmatter(md_file)
        if meta:
            if exclude_seeds and meta.get("source") == "seed":
                continue
            meta["_source"] = md_file.stem
            items.append(meta)

    return items


def _load_skill_frontmatter_with_body(
    skill_dir: Path,
    *,
    include_sidecar_config: bool = True,
) -> tuple[dict[str, Any], str]:
    """Load SKILL.md frontmatter/body from a skill directory.

    Returns ``({}, "")`` when the skill has no SKILL.md.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return {}, ""
    return parse_frontmatter(skill_md, include_sidecar_config=include_sidecar_config)


def load_skill_config(skill_dir: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Return normalized skill frontmatter, merged config, and body.

    Config is sourced from canonical ``SKILL.md`` frontmatter, with optional
    ``x-augur-config-file`` sidecar support handled by ``parse_frontmatter``.
    Selected top-level frontmatter fields are projected into the returned
    config dict for older read-only consumers while the repo finishes the
    augur.yaml retirement.
    """
    frontmatter, body = _load_skill_frontmatter_with_body(skill_dir)
    if not isinstance(frontmatter, dict):
        return {}, {}, body

    raw_config = frontmatter.get("x-augur-config")
    config = dict(raw_config) if isinstance(raw_config, dict) else {}

    if "name" not in config and isinstance(frontmatter.get("name"), str):
        config["name"] = frontmatter["name"]

    mcp_tools = frontmatter.get("x-augur-mcp-tools")
    if isinstance(mcp_tools, list):
        filtered = [tool for tool in mcp_tools if isinstance(tool, str) and tool]
        if filtered:
            mcp = config.get("mcp")
            if not isinstance(mcp, dict):
                mcp = {}
            else:
                mcp = dict(mcp)
            existing = mcp.get("tools")
            if not isinstance(existing, list) or not existing:
                mcp["tools"] = filtered
            else:
                seen = {tool for tool in existing if isinstance(tool, str)}
                mcp["tools"] = [*existing, *[tool for tool in filtered if tool not in seen]]
            config["mcp"] = mcp

    return frontmatter, config, body


def load_skill_data(
    vault_dir: Path,
    seed_dir: Path,
    subpath: str = "",
) -> list[dict[str, Any]]:
    """Load skill data from vault with automatic seed fallback.

    Resolution order:
      1. Vault: load user-created files (excluding any with ``source: seed``).
         If at least one user file exists, return those.
      2. Seeds: if no user data in vault, load directly from the seed directory.
      3. Empty list if neither source has data.

    Args:
        vault_dir: Root vault directory for the skill (e.g. ``~/Au-vault/eisenhower/``).
        seed_dir:  Root seed directory for the skill (e.g. ``skills/eisenhower/assets/seeds/``).
        subpath:   Optional subdirectory under both vault and seed dirs
                   (e.g. ``"tasks"``).
    """
    vault_path = vault_dir / subpath if subpath else vault_dir
    seed_path = seed_dir / subpath if subpath else seed_dir

    # Check vault for user data (exclude seed copies)
    if vault_path.is_dir():
        user_items = load_collection(vault_path, exclude_seeds=True)
        if user_items:
            return user_items

    # Fall back to seeds served directly from plugin source
    if seed_path.is_dir():
        return load_collection(seed_path)

    return []
