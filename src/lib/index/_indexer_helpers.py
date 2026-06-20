"""Internal helpers for the unified RAG indexer.

Checksum computation, entry writing, and bundle/skill discovery.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.paths import (
    get_claude_plugin_skill_dirs,
    get_client_skill_dirs,
    get_configured_vault_skills_dir,
    get_managed_skill_source_dirs,
    get_project_brain_skills_dir,
    get_project_root,
    get_vault_skills_dir,
)
from src.lib.frontmatter_utils import load_skill_contract, parse_frontmatter, write_frontmatter
from src.plugins.skill_discovery import normalize_skill_id

_PRESERVED_ENTRY_METADATA: dict[str, dict[str, Any]] = {}
_LEGACY_WIKI_COMPILE_METADATA_KEYS = (
    "wiki_compile_status",
    "wiki_compiled_at",
    "wiki_compiled_checksum",
    "wiki_targets",
)
_CLIENT_LOCAL_SKILL_PREFIXES: dict[tuple[str, str], str] = {
    (".claude", "skills"): "claude",
    (".codex", "skills"): "codex",
    (".gemini", "skills"): "gemini",
    (".opencode", "skills"): "opencode",
}


def source_path_key(source_path: Any) -> str:
    """Return a stable slash-separated key for source_path metadata."""
    return str(source_path).replace("\\", "/")


def humanize_slug(name: str) -> str:
    """Derive a friendly title from a vault/ADR slug.

    "2026-05-30-demo-invoice-2" -> "Demo Invoice 2" (drop the leading date and
    capture-modality prefix noise). "demo" is a topic, not a modality, so it is
    kept; derived-copy suffixes (.extracted/.transcript) are dropped. Falls back
    to the original name when empty.
    """
    s = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)
    s = re.sub(r"^(prompt|url|voice|thought|meeting|email)-", "", s)
    s = re.sub(r"\.(extracted|transcript)$", "", s)
    return s.replace("-", " ").replace("_", " ").strip().title() or name


def source_path_for(path: Path, root: Path) -> str:
    """Return path relative to root, or absolute, using portable separators."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _active_managed_skill_source_dirs(root: Path) -> list[Path]:
    """Return managed skill roots that are valid after the project-brain migration."""
    root = Path(root).resolve()
    allowed = {
        get_project_brain_skills_dir(root).resolve(),
        get_configured_vault_skills_dir(root).resolve(),
        get_vault_skills_dir().resolve(),
    }
    dirs: list[Path] = []
    seen: set[Path] = set()
    for skills_dir in get_managed_skill_source_dirs(root):
        resolved = Path(skills_dir).resolve()
        if resolved not in allowed or resolved in seen:
            continue
        dirs.append(skills_dir)
        seen.add(resolved)
    return dirs


def _is_stale_repo_root_skill_dir(skill_dir: Path, root: Path) -> bool:
    """Return True for the retired repo-root skills/{name} layout."""
    try:
        rel = Path(skill_dir).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return False
    return len(rel.parts) >= 2 and rel.parts[0] == "skills"


def _checksum(path: Path) -> str:
    """Return MD5 hex digest of file content."""
    return hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()  # noqa: S324


def _mtime_iso(path: Path) -> str:
    """Return file modification time as ISO-8601 UTC string."""
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def clear_preserved_entry_metadata() -> None:
    """Drop any cached pre-scan metadata from a previous reindex run."""
    _PRESERVED_ENTRY_METADATA.clear()


def prime_preserved_entry_metadata(category_dir: Path) -> None:
    """Snapshot user-managed metadata from an existing category tree.

    The snapshot is keyed by source_path so it can survive directory removal
    during a rebuild and be merged back into the rewritten entry.
    """
    if not category_dir.is_dir():
        return

    for entry_file in sorted(category_dir.rglob("*.md")):
        if not entry_file.is_file():
            continue
        try:
            existing_meta, _ = parse_frontmatter(entry_file)
        except Exception:
            continue

        source_path = existing_meta.get("source_path")
        if not source_path:
            continue

        preserved: dict[str, Any] = {}
        if "manual_related" in existing_meta:
            preserved["manual_related"] = existing_meta["manual_related"]

        if preserved:
            _PRESERVED_ENTRY_METADATA[source_path_key(source_path)] = preserved


def _merge_preserved_metadata(metadata: dict[str, Any], preserved: dict[str, Any]) -> None:
    """Merge cached manual metadata into a freshly built entry."""
    if preserved.get("manual_related") and "manual_related" not in metadata:
        metadata["manual_related"] = preserved["manual_related"]


def _drop_legacy_wiki_compile_metadata(metadata: dict[str, Any]) -> None:
    """Remove RAG-owned wiki compiler fields before writing."""
    for key in _LEGACY_WIKI_COMPILE_METADATA_KEYS:
        metadata.pop(key, None)


def _has_legacy_wiki_compile_metadata(metadata: dict[str, Any]) -> bool:
    """Return True when an entry still carries legacy wiki compiler fields."""
    return any(key in metadata for key in _LEGACY_WIKI_COMPILE_METADATA_KEYS)


def _write_entry(output_path: Path, metadata: dict[str, Any], body: str = "") -> None:
    """Write a RAG index entry, preserving existing manual metadata.

    Steps:
    1. Read existing entry (if any) to extract manual_related.
    2. Merge manual_related into metadata.
    3. Drop legacy wiki compiler fields.
    4. Stamp indexed_at with current UTC time.
    5. Call write_frontmatter() to persist the entry.
    """
    _drop_legacy_wiki_compile_metadata(metadata)

    if output_path.exists():
        existing_meta, _ = parse_frontmatter(output_path)
        _merge_preserved_metadata(metadata, existing_meta)
    else:
        source_path = metadata.get("source_path")
        if source_path:
            preserved = _PRESERVED_ENTRY_METADATA.get(source_path_key(source_path))
            if preserved:
                _merge_preserved_metadata(metadata, preserved)

    _drop_legacy_wiki_compile_metadata(metadata)
    metadata["indexed_at"] = datetime.now(tz=timezone.utc).isoformat()
    write_frontmatter(output_path, metadata, body)


def _classify_skill_dir(skill_dir: Path, root: Path) -> tuple[str, str]:
    """Classify a skill directory for browse metadata.

    Returns (skill_client, skill_origin).
    """
    root = Path(root).resolve()
    skill_dir = Path(skill_dir).resolve()
    project_brain_skills_dir = get_project_brain_skills_dir(root).resolve()
    private_skills_dir = get_configured_vault_skills_dir(root).resolve()
    for managed_dir in _active_managed_skill_source_dirs(root):
        managed_dir = managed_dir.resolve()
        try:
            skill_dir.relative_to(managed_dir)
        except ValueError:
            continue
        if managed_dir == project_brain_skills_dir:
            return ("augur", "canonical")
        if managed_dir == private_skills_dir:
            return ("vault", "canonical")

    try:
        rel = skill_dir.relative_to(root)
    except ValueError:
        rel = None

    if rel is not None:
        parts = rel.parts
        if len(parts) >= 3:
            client = _CLIENT_LOCAL_SKILL_PREFIXES.get((parts[0], parts[1]))
            if client:
                return (client, "client-local")

    for source_tag, client_parent in get_client_skill_dirs().items():
        try:
            skill_dir.relative_to(client_parent.resolve())
        except ValueError:
            continue
        client, _, scope = source_tag.partition("-")
        if scope in {"local", "global"}:
            return (client, f"client-{scope}")
        return (source_tag, "client")

    for plugin_parent in get_claude_plugin_skill_dirs():
        try:
            skill_dir.relative_to(plugin_parent.resolve())
        except ValueError:
            continue
        return ("claude-plugin", "plugin-cache")

    return ("unknown", "external")


def _skill_overlay_metadata(skill_dir: Path, root: Path) -> dict[str, str]:
    root = Path(root).resolve()
    resolved = Path(skill_dir).resolve()
    project_brain_skills = get_project_brain_skills_dir(root).resolve()
    private_skill_roots = {
        get_configured_vault_skills_dir(root).resolve(),
        get_vault_skills_dir().resolve(),
    }

    metadata_by_parent = {
        project_brain_skills: {
            "brain_scope": "project",
            "vault_scope": "shared",
            "vault_root": "project-brain",
            "promotion_state": "integrated",
            "source_root": "project-brain",
        },
        **{
            private_skills: {
                "vault_scope": "private",
                "vault_root": "private-vault",
                "promotion_state": "private",
                "source_root": "private-vault",
            }
            for private_skills in private_skill_roots
        },
    }

    for parent, metadata in metadata_by_parent.items():
        try:
            resolved.relative_to(parent)
        except ValueError:
            continue
        return dict(metadata)

    return {}


def _canonical_skill_ids(root: Path) -> set[str]:
    """Return normalized canonical skill ids under managed skill roots."""
    canonical_ids: set[str] = set()
    for skills_dir in _active_managed_skill_source_dirs(Path(root).resolve()):
        if not skills_dir.is_dir():
            continue
        canonical_ids.update(
            normalize_skill_id(skill_dir.name)
            for skill_dir in skills_dir.iterdir()
            if skill_dir.is_dir() and not skill_dir.name.startswith(".")
        )
    return canonical_ids


_SYNC_AGENTS_EXPORT_MARKERS = ("AUTO-GENERATED FILE", "sync_agents")


def _is_sync_agents_export(skill_dir: Path) -> bool:
    """True when SKILL.md carries the sync_agents auto-generated export header.

    Command exports (e.g. /ask projected into .codex/skills/ask/) have no
    canonical skill dir, so the canonical-id check below cannot catch them;
    the generator marker in the body head is their only fingerprint.
    """
    skill_md = skill_dir / "SKILL.md"
    try:
        head = skill_md.read_text(encoding="utf-8", errors="ignore")[:1500]
    except OSError:
        return False
    return all(marker in head for marker in _SYNC_AGENTS_EXPORT_MARKERS)


def _is_duplicate_generated_skill(
    skill_dir: Path,
    root: Path,
    canonical_skill_ids: set[str],
    *,
    skill_name: str | None = None,
) -> bool:
    """Return True when a client-local generated skill duplicates a canonical skill."""
    skill_client, skill_origin = _classify_skill_dir(skill_dir, root)
    if skill_origin not in {"client-local", "client-global"} or skill_client == "augur":
        return False

    if _is_sync_agents_export(skill_dir):
        return True

    candidate_ids = {normalize_skill_id(Path(skill_dir).name)}
    if skill_name:
        candidate_ids.add(normalize_skill_id(skill_name))
    candidate_ids.discard("")
    return any(candidate_id in canonical_skill_ids for candidate_id in candidate_ids)


def _discover_skill_entries(root: Path) -> list[tuple[str, Path, Any | None]]:
    """Return (bundle_name, skill_dir, SkillRecord) entries via canonical skill discovery.

    Delegates to discover_all_skills() and extracts hub + path from each
    SkillRecord, filtered to the provided root so test and temp-tree callers
    do not accidentally index the host machine's global client skills.
    """
    root = Path(root).resolve()
    project_root = Path(get_project_root()).resolve()

    canonical_skill_ids = _canonical_skill_ids(root)

    if root != project_root:
        discovered: list[tuple[str, Path, Any | None]] = []
        seen: set[Path] = set()

        def _append_skill(skill_dir: Path, default_bundle: str) -> None:
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                return
            if _is_stale_repo_root_skill_dir(skill_dir, root):
                return
            resolved = skill_dir.resolve()
            if resolved in seen:
                return
            seen.add(resolved)
            meta, _ = parse_frontmatter(skill_md)
            if _is_duplicate_generated_skill(
                skill_dir,
                root,
                canonical_skill_ids,
                skill_name=str(meta.get("name") or ""),
            ):
                return
            bundle = str(default_bundle or "unknown").strip() or "unknown"  # x-augur-hub removed by ADR-802
            discovered.append((bundle, skill_dir, None))

        for managed_dir in _active_managed_skill_source_dirs(root):
            if not managed_dir.is_dir():
                continue
            for skill_dir in sorted(managed_dir.iterdir()):
                if skill_dir.is_dir():
                    _append_skill(skill_dir, "unknown")

        plugins_root = root / "plugins"
        if plugins_root.is_dir():
            for bundle_dir in sorted(plugins_root.iterdir()):
                if not bundle_dir.is_dir():
                    continue
                skills_dir = bundle_dir / "skills"
                if not skills_dir.is_dir():
                    continue
                for skill_dir in sorted(skills_dir.iterdir()):
                    if skill_dir.is_dir():
                        _append_skill(skill_dir, bundle_dir.name)

        for first, second in _CLIENT_LOCAL_SKILL_PREFIXES:
            client_skills_dir = root / first / second
            if not client_skills_dir.is_dir():
                continue
            for skill_dir in sorted(client_skills_dir.iterdir()):
                if skill_dir.is_dir():
                    _append_skill(skill_dir, "unknown")

        return discovered

    from src.plugins.skill_discovery import discover_all_skills

    root_resolved = root.resolve()
    discovered = []
    seen: set[Path] = set()
    for rec in discover_all_skills():
        if not rec.path.is_dir():
            continue
        if _is_stale_repo_root_skill_dir(rec.path, root_resolved):
            continue
        if _is_duplicate_generated_skill(rec.path, root_resolved, canonical_skill_ids, skill_name=rec.name):
            continue
        seen.add(rec.path.resolve())
        # rec.hub is always "" after the ADR-802 hub teardown — partition by
        # source root (project-brain | private-vault | ...) instead of "unknown".
        discovered.append((rec.hub or rec.source_root or "unknown", rec.path, rec))

    for managed_dir in _active_managed_skill_source_dirs(root):
        if not managed_dir.is_dir():
            continue
        for skill_dir in sorted(managed_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            if _is_stale_repo_root_skill_dir(skill_dir, root_resolved):
                continue
            resolved = skill_dir.resolve()
            if resolved in seen:
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue
            seen.add(resolved)
            meta, _ = parse_frontmatter(skill_md)
            if _is_duplicate_generated_skill(
                skill_dir,
                root_resolved,
                canonical_skill_ids,
                skill_name=str(meta.get("name") or ""),
            ):
                continue
            hub = "unknown"  # x-augur-hub removed by ADR-802
            discovered.append((hub, skill_dir, None))

    if discovered:
        return discovered

    results: list[tuple[str, Path, Any | None]] = []
    seen: set[Path] = set()
    managed_roots = [Path(skills_dir) for skills_dir in _active_managed_skill_source_dirs(root)]
    candidate_roots = [*managed_roots, *(root / "plugins").glob("*/skills")]
    candidate_roots.extend(root / first / second for first, second in _CLIENT_LOCAL_SKILL_PREFIXES)
    for skills_dir in candidate_roots:
        if not skills_dir.is_dir():
            continue
        allow_outside_root = any(skills_dir.resolve() == managed_root.resolve() for managed_root in managed_roots)
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            if _is_stale_repo_root_skill_dir(skill_dir, root_resolved):
                continue
            resolved = skill_dir.resolve()
            if resolved in seen or (not allow_outside_root and not _is_under_root(resolved, root_resolved)):
                continue
            seen.add(resolved)
            contract = load_skill_contract(skill_dir)
            if _is_duplicate_generated_skill(
                skill_dir,
                root_resolved,
                canonical_skill_ids,
                skill_name=str(contract.get("name") or ""),
            ):
                continue
            inferred_bundle = "unknown"
            try:
                rel = skill_dir.relative_to(root)
                if len(rel.parts) >= 4 and rel.parts[0] == "plugins" and rel.parts[2] == "skills":
                    inferred_bundle = rel.parts[1]
            except ValueError:
                pass
            hub = contract.get("hub") or contract.get("contributes_to") or inferred_bundle
            results.append((str(hub), skill_dir, None))

    return results


def _discover_skill_dirs(root: Path) -> list[tuple[str, Path]]:
    """Return (bundle_name, skill_dir) pairs via canonical skill discovery."""
    return [(bundle, skill_dir) for bundle, skill_dir, _record in _discover_skill_entries(root)]


def _is_under_root(path: Path, root_resolved: Path) -> bool:
    try:
        path.resolve().relative_to(root_resolved)
        return True
    except ValueError:
        return False


def _discover_bundles(root: Path) -> list[str]:
    """Return unique bundle names for backwards-compatible scanner imports."""
    bundles = {bundle for bundle, _skill_dir in _discover_skill_dirs(root)}
    return sorted(bundles)


def _read_skill_config(skill_md: Path) -> dict:
    """Read canonical x-augur-config data from a skill's SKILL.md contract."""
    contract = load_skill_contract(skill_md)
    config = contract.get("config")
    return config if isinstance(config, dict) else {}
