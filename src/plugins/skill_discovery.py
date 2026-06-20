"""Canonical skill discovery module.

Single source of truth for skill scanning:
  1. Managed canonical skill roots (repo + vault)
  2. External client inventory directories

Consumers should call discover_all_skills() and read from SkillRecord.
The older SkillMetadata / list_skills() API is preserved as a thin wrapper.
"""

# TODO_CLEANUP: This file is 857 lines — consider splitting into smaller modules

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional

import yaml

from src.config.paths import (
    get_claude_plugin_skill_dirs,
    get_configured_vault_skills_dir,
    get_managed_skill_source_dirs,
    get_project_brain_skills_dir,
    get_project_root,
    get_skills_dir,
    get_vault_skills_dir,
)
from src.lib.skill_release import ensure_valid_group, ensure_valid_release
from src.logging import get_entity_logger

logger = get_entity_logger("plugins.skill_discovery")


def _get_client_skill_dirs() -> dict[str, "Path"]:
    """Wrapper for testability."""
    from src.config.paths import get_client_skill_dirs

    return get_client_skill_dirs()


def _get_managed_skill_dirs(project_root: Path | None = None) -> list[Path]:
    """Wrapper for testability around repo + vault managed skill roots."""
    root = project_root or get_project_root()
    return list(get_managed_skill_source_dirs(root))


# List of skill IDs that are considered "core" and cannot be disabled
CORE_SKILLS = {"adr", "ai", "observe", "knowledge", "search"}

# ---------------------------------------------------------------------------
# TTL cache for discover_all_skills()
# ---------------------------------------------------------------------------
_DISCOVERY_CACHE: dict[tuple[object, ...], list] = {}
_DISCOVERY_CACHE_TS: dict[tuple[object, ...], float] = {}
_DISCOVERY_CACHE_TTL: float = 30.0


def invalidate_discovery_cache():
    """Force next discover_all_skills() call to rescan."""
    global _DISCOVERY_CACHE, _DISCOVERY_CACHE_TS
    _DISCOVERY_CACHE = {}
    _DISCOVERY_CACHE_TS = {}


# ---------------------------------------------------------------------------
# SkillRecord — canonical frozen dataclass covering all consumer needs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SkillRecord:
    """Canonical skill metadata record.

    Superset of all consumer needs.  Every ``x-augur-*`` frontmatter field is
    represented here so that downstream code never has to re-parse SKILL.md.
    """

    name: str
    description: str
    path: Path
    author: str  # x-augur-created-by or "bundled"
    hub: str  # legacy, unused after ADR-802 hub teardown; always ""
    visibility: str  # legacy, unused after Track 4; always ""
    loop_config: dict  # x-augur-loop
    dependencies: dict  # x-augur-dependencies
    mcp_tools: list  # x-augur-mcp-tools
    dashboard_pages: list  # x-augur-dashboard-pages
    commands: list  # x-augur-commands
    config: dict  # x-augur-config
    agent: dict | None  # x-augur-agent (provisional, ADR-460)
    skill_type: str  # x-augur-type
    tags: tuple[str, ...]  # x-augur-tags
    tier: int  # 0=managed shared/private vault, 1=plugin-cache
    origin: str = ""  # discovery origin/path tag
    ownership: str = "augur"  # augur | adopted | external
    upstream: dict = field(default_factory=dict)
    source: str = "augur"  # discovery origin tag retained for consumers that still read it
    source_root: str = "project-brain"  # project-brain | private-vault | external-client | plugin-cache
    canonical: bool = True
    client_sources: tuple[str, ...] = ()

    file_intake: dict = field(default_factory=dict)  # x-augur-file-intake

    # Backward-compat aliases — kept so existing code that reads .master
    # or .sync_enabled doesn't break. Will be removed in a follow-up.
    master: str = ""
    sync_enabled: bool = False

    # Extended fields carried over from SkillMetadata for backward compat
    display_name: str = ""
    triggers: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    token_estimate: int = 0
    has_modules: bool = False
    has_scripts: bool = False
    has_references: bool = False
    has_context: bool = False
    aliases: tuple[str, ...] = ()
    layer: str | None = None
    disabled: bool = False
    alias: str | None = None
    group: str | None = None
    release: str | None = None
    plugin: str | None = None
    category: str = ""
    requires_platform: bool = False


# ---------------------------------------------------------------------------
# Legacy SkillMetadata — kept for backward compatibility
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SkillMetadata:
    id: str
    display_name: str
    description: str
    triggers: tuple[str, ...]
    capabilities: tuple[str, ...]
    token_estimate: int
    has_modules: bool
    has_scripts: bool
    has_references: bool
    has_context: bool
    path: Path
    aliases: tuple[str, ...]
    layer: Optional[str] = None
    disabled: bool = False
    dependencies: tuple[str, ...] = ()
    visibility: Optional[str] = None
    loop_config: Optional[dict] = None
    alias: Optional[str] = None
    group: Optional[str] = None
    release: Optional[str] = None
    master: Optional[str] = None
    sync_enabled: bool = False
    origin: str = ""
    plugin: Optional[str] = None
    category: Optional[str] = None
    requires_platform: bool = False
    skill_type: str = ""
    tags: tuple[str, ...] = ()
    client_sources: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_skill_id(name: str) -> str:
    """Normalize a skill name to a canonical ID (lowercase, kebab-case)."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _extract_frontmatter(content: str) -> dict:
    """Inline frontmatter parser — fallback when _parse_fm is unavailable."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return {}


def _extract_triggers(frontmatter: dict, description: str, content: str = "") -> list[str]:
    triggers = frontmatter.get("triggers", [])
    if isinstance(triggers, str):
        triggers = [t.strip() for t in triggers.split(",")]
    elif not isinstance(triggers, list):
        triggers = []

    if not triggers:
        match = re.search(r"Triggers:\s*(.*)", description, re.IGNORECASE)
        if match:
            triggers = [t.strip() for t in match.group(1).split(",")]

    if content:
        heading_match = re.search(r"^#\s+/([a-z0-9_-]+)", content, re.MULTILINE | re.IGNORECASE)
        if heading_match:
            cmd = heading_match.group(1).lower()
            if cmd not in triggers:
                triggers.insert(0, cmd)
                triggers.insert(0, f"/{cmd}")

    return triggers


def _extract_capabilities(content: str) -> list[str]:
    capabilities = []
    match = re.search(r"#+ Capabilities\s*\n((?:\s*-\s*.*\n?)*)", content, re.IGNORECASE)
    if match:
        for line in match.group(1).splitlines():
            line = line.strip()
            if line.startswith("-"):
                capabilities.append(line.lstrip("- ").strip())
    return capabilities


def _extract_dependencies_tuple(frontmatter: dict) -> tuple[str, ...]:
    """Extract dependencies as a tuple of strings (legacy format)."""
    deps = frontmatter.get("dependencies", [])
    if isinstance(deps, str):
        deps = [d.strip() for d in deps.split(",")]
    elif not isinstance(deps, list):
        deps = []
    return tuple(deps)


def _extract_dict_field(frontmatter: dict, key: str) -> dict:
    """Extract a dict-valued frontmatter field, returning {} if absent/wrong type."""
    val = frontmatter.get(key)
    return val if isinstance(val, dict) else {}


def _extract_bool_field(frontmatter: dict, key: str) -> bool:
    """Extract a bool-valued frontmatter field, returning False if absent/wrong type."""
    val = frontmatter.get(key)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        normalized = val.strip().lower()
        if normalized in {"true", "yes", "1", "on"}:
            return True
        if normalized in {"false", "no", "0", "off"}:
            return False
    return False


def _extract_list_field(frontmatter: dict, key: str) -> list:
    """Extract a list-valued frontmatter field, returning [] if absent/wrong type."""
    val = frontmatter.get(key)
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [v.strip() for v in val.split(",") if v.strip()]
    return []


def _extract_optional_group(frontmatter: dict) -> str | None:
    """Extract and validate an optional x-augur-group value."""
    raw_group = frontmatter.get("x-augur-group")
    if raw_group is None or raw_group == "":
        return None
    return ensure_valid_group(str(raw_group).strip())


def _extract_optional_release(frontmatter: dict) -> str | None:
    """Extract and validate an optional x-augur-release value."""
    raw_release = frontmatter.get("x-augur-release")
    if raw_release is None or raw_release == "":
        return None
    return ensure_valid_release(str(raw_release).strip())


def _load_disabled_skills() -> set[str]:
    from src.plugins.skill_ui_state import read_disabled_skills

    return read_disabled_skills()


def _extract_ownership_and_upstream(frontmatter: dict, *, managed: bool) -> tuple[str, dict]:
    """Return ownership and upstream metadata for a discovered skill."""
    if not managed:
        return "external", {}

    ownership = str(frontmatter.get("ownership") or "augur").strip().lower()
    if ownership != "adopted":
        ownership = "augur"

    upstream = frontmatter.get("upstream")
    return ownership, upstream if isinstance(upstream, dict) else {}


def _is_auto_generated(skill_md: Path) -> bool:
    """Check if a SKILL.md is auto-generated (not a source-of-truth).

    Checks all known markers:
      - AUTO-GENERATED FILE
      - Generator:
      - AUGUR-ADAPTED-COPY
      - AUGUR-STUB
      - <!-- AUGUR-GENERATED -->
    """
    try:
        header = skill_md.read_text(encoding="utf-8")[:500]
        return (
            "AUTO-GENERATED FILE" in header
            or "Generator:" in header
            or "AUGUR-ADAPTED-COPY" in header
            or "AUGUR-STUB" in header
            or "<!-- AUGUR-GENERATED -->" in header
        )
    except Exception:
        return False


def _initial_client_sources(origin: str) -> tuple[str, ...]:
    source = str(origin or "").strip()
    return (source,) if source else ()


def _merge_client_sources(*source_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for sources in source_groups:
        for source in sources:
            normalized = str(source).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                merged.append(normalized)
    return tuple(merged)


def _merge_skill_records(primary: SkillRecord, secondary: SkillRecord) -> SkillRecord:
    """Keep primary metadata while recording every installed client source."""
    return replace(
        primary,
        client_sources=_merge_client_sources(primary.client_sources, secondary.client_sources),
    )


def _store_skill_record(
    skills_dict: dict[str, SkillRecord],
    canonical_id: str,
    new_record: SkillRecord,
) -> None:
    """Store a skill record while preserving higher-authority metadata."""
    existing = skills_dict.get(canonical_id)
    if existing and hasattr(existing, "tier"):
        if existing.tier < new_record.tier:
            skills_dict[canonical_id] = _merge_skill_records(existing, new_record)
            return
        if existing.tier == new_record.tier:
            if _source_root_priority(existing.source_root) >= _source_root_priority(new_record.source_root):
                skills_dict[canonical_id] = _merge_skill_records(existing, new_record)
                return
            new_record = _merge_skill_records(new_record, existing)
            skills_dict[canonical_id] = new_record
            return
        new_record = _merge_skill_records(new_record, existing)

    skills_dict[canonical_id] = new_record


def _classify_managed_root(
    skills_dir: Path,
    project_root: Path | None = None,
) -> tuple[str, str, str | None] | None:
    """Return source_root, origin/source tag, and ownership override.

    Unknown managed roots are ignored. In particular, repo-root ``skills/`` was
    a pre-migration location and must not be revived by stale adapters.
    """
    resolved_dir = skills_dir.resolve()
    root = project_root or get_project_root()
    project_brain_skills_dir = get_project_brain_skills_dir(root).resolve()
    private_skills_dir = get_configured_vault_skills_dir(root).resolve()
    live_private_skills_dir = get_vault_skills_dir().resolve() if project_root is None else private_skills_dir

    if resolved_dir == project_brain_skills_dir:
        return "project-brain", "project-brain", None
    if resolved_dir in {private_skills_dir, live_private_skills_dir}:
        return "private-vault", "private-vault", "user"
    return None


def _source_root_priority(source_root: str) -> int:
    """Explicit authority for equal-tier collisions."""
    priorities = {
        "project-brain": 40,
        # ADR-770 compatibility: retained only for stale discovery metadata.
        "shared-vault": 40,
        "private-vault": 35,
        "vault": 30,
        "plugin-cache": 20,
        "external-client": 10,
    }
    return priorities.get(source_root, 0)


# Backward-compat stubs for importers
def infer_master(skill_md_path: Path) -> Optional[str]:
    """Deprecated: master inference removed. Returns None."""
    return None


def _iter_skill_dirs(plugins_dir: Path):
    """Deprecated: replaced by managed skill-root discovery."""
    return iter([])


def _default_plugins_dir() -> Path:
    """Deprecated: returns skills dir."""
    return get_skills_dir()


# ---------------------------------------------------------------------------
# Canonical discovery function
# ---------------------------------------------------------------------------


def discover_all_skills(
    *,
    tiers: tuple[int, ...] | None = None,
    project_root: Path | None = None,
) -> list[SkillRecord]:
    """Single canonical skill discovery. All consumers should use this.

    Args:
        tiers: Which discovery tiers to include. ``None`` (default) scans all
            tiers. Pass ``(0,)`` to scan only Augur-managed canonical skills
            from managed roots, ``(0, 1)`` to include plugin-cache installs,
            etc. Tier 0 = managed canonical skill roots (repo + vault),
            Tier 1 = plugin cache installs,
            Tier 2 = platform/client skills.
        project_root: Explicit project root for managed-root discovery.

    Results are cached per tier-set for ``_DISCOVERY_CACHE_TTL`` seconds
    (default 30s). Call ``invalidate_discovery_cache()`` to force a rescan.
    """
    global _DISCOVERY_CACHE, _DISCOVERY_CACHE_TS
    root_key = str(project_root.resolve()) if project_root is not None else ""
    cache_key = (root_key, tuple(sorted(tiers)) if tiers is not None else ())
    now = time.monotonic()
    cached_ts = _DISCOVERY_CACHE_TS.get(cache_key, 0.0)
    if cache_key in _DISCOVERY_CACHE and (now - cached_ts) < _DISCOVERY_CACHE_TTL:
        return list(_DISCOVERY_CACHE[cache_key])  # return copy to prevent mutation
    result = _discover_all_skills_impl(tiers=tiers, project_root=project_root)
    _DISCOVERY_CACHE[cache_key] = result
    _DISCOVERY_CACHE_TS[cache_key] = now
    return list(result)


def _process_flat_skill_file(
    skill_file: Path,
    origin: str,
    tier: int,
    disabled_ids: set[str],
    skills_dict: dict[str, SkillRecord],
    *,
    source_root: str,
    canonical: bool,
) -> None:
    """Process a flat .md skill file (Codex format) into a SkillRecord."""
    if _is_auto_generated(skill_file):
        return

    try:
        content = skill_file.read_text(encoding="utf-8")
    except Exception:
        return

    frontmatter = _extract_frontmatter(content)
    if not isinstance(frontmatter, dict):
        frontmatter = {}

    canonical_id = normalize_skill_id(str(frontmatter.get("name") or "").strip() or skill_file.stem)
    if not canonical_id:
        return

    description = str(frontmatter.get("description") or "").strip()
    triggers = _extract_triggers(frontmatter, description, content)
    capabilities = _extract_capabilities(content)

    disabled = canonical_id in disabled_ids
    if disabled and canonical_id not in CORE_SKILLS:
        return

    ownership, upstream = _extract_ownership_and_upstream(frontmatter, managed=False)
    group = _extract_optional_group(frontmatter)
    release = _extract_optional_release(frontmatter)

    new_record = SkillRecord(
        name=canonical_id,
        description=description,
        path=skill_file.parent,
        author=str(frontmatter.get("x-augur-created-by") or ""),
        # x-augur-hub was removed in the ADR-802 hub teardown; field stays on
        # SkillRecord for backward compat but is no longer populated.
        hub="",
        # x-augur-visibility was removed in Track 4 of the cross-client
        # bundle migration; field stays on SkillRecord for backward compat
        # but is no longer populated from frontmatter.
        visibility="",
        loop_config={},
        dependencies={},
        mcp_tools=[],
        dashboard_pages=[],
        commands=[],
        config={},
        file_intake={},
        agent=None,
        skill_type=str(frontmatter.get("x-augur-type") or ""),
        tags=(),
        tier=tier,
        origin=origin,
        ownership=ownership,
        upstream=upstream,
        source=origin,
        source_root=source_root,
        canonical=canonical,
        client_sources=_initial_client_sources(origin),
        display_name=str(frontmatter.get("name") or skill_file.stem),
        triggers=tuple(triggers),
        capabilities=tuple(capabilities),
        token_estimate=len(content) // 4,
        group=group,
        release=release,
        category=str(frontmatter.get("x-augur-category") or ""),
        requires_platform=_extract_bool_field(frontmatter, "x-augur-requires-platform"),
    )

    existing = skills_dict.get(canonical_id)
    if existing and hasattr(existing, "tier"):
        if existing.tier <= tier:
            skills_dict[canonical_id] = _merge_skill_records(existing, new_record)
            return
        new_record = _merge_skill_records(new_record, existing)

    skills_dict[canonical_id] = new_record


def _strip_standard_frontmatter(raw: str) -> str:
    if not raw.startswith("---\n"):
        return raw
    try:
        end = raw.index("\n---", 4)
    except ValueError:
        return raw
    return raw[end + 4 :].lstrip("\n")


def _heading_and_summary_from_markdown(path: Path) -> tuple[str, str]:
    body = _strip_standard_frontmatter(path.read_text(encoding="utf-8"))
    title = path.stem
    summary = ""
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            if title == path.stem:
                title = stripped[2:].strip()
            continue
        summary = stripped
        break
    return title, summary


def _discover_all_skills_impl(
    *,
    tiers: tuple[int, ...] | None = None,
    project_root: Path | None = None,
) -> list[SkillRecord]:
    """Internal implementation — always rescans the filesystem.

    Args:
        tiers: Which tiers to scan. ``None`` scans all tiers.
    """
    disabled_ids = _load_disabled_skills()
    skills_dict: dict[str, SkillRecord] = {}
    scan_all = tiers is None
    tier_set = set(tiers) if tiers is not None else set()

    # Source 1 (Tier 0): Canonical managed skill roots.
    if scan_all or 0 in tier_set:
        for managed_dir in _get_managed_skill_dirs(project_root):
            if not managed_dir.is_dir():
                continue
            managed_root = _classify_managed_root(
                managed_dir,
                project_root,
            )
            if managed_root is None:
                continue
            source_root, origin, ownership_override = managed_root
            for skill_dir in managed_dir.iterdir():
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue
                _process_skill_dir(
                    skill_dir,
                    origin,
                    0,
                    disabled_ids,
                    skills_dict,
                    managed=True,
                    source_root=source_root,
                    canonical=True,
                    ownership_override=ownership_override,
                )
                _process_standard_bundle_dir(
                    skill_dir,
                    origin,
                    0,
                    disabled_ids,
                    skills_dict,
                    source_root=source_root,
                    canonical=True,
                    ownership_override=ownership_override,
                )

    # Source 2 (Tier 1): Client cache directories (plugin store installs)
    if scan_all or 1 in tier_set:
        try:
            for skills_parent in get_claude_plugin_skill_dirs():
                if skills_parent.is_dir():
                    for skill_dir in _iter_subdir_skill_dirs(skills_parent):
                        _process_skill_dir(
                            skill_dir,
                            "claude-plugin-cache",
                            1,
                            disabled_ids,
                            skills_dict,
                            managed=False,
                            source_root="plugin-cache",
                            canonical=False,
                        )
        except Exception:
            pass  # Plugin cache discovery is optional

    # Source 3 (Tier 2): AI client skill directories (platform-managed skills)
    # Subdir clients: claude, codex, gemini, opencode (SKILL.md inside {name}/ directory)
    # Flat clients: cursor (.mdc), copilot (.md)
    if scan_all or 2 in tier_set:
        _SUBDIR_CLIENTS = {
            "claude-local",
            "claude-global",
            "codex-local",
            "codex-global",
            "codex-global-superpowers",
            "gemini-local",
            "gemini-global",
            "opencode-local",
            "opencode-global",
        }
        _FLAT_EXTENSIONS = {".md", ".mdc"}
        try:
            for source_tag, skill_parent in _get_client_skill_dirs().items():
                if not skill_parent.is_dir():
                    continue
                if source_tag in _SUBDIR_CLIENTS:
                    for skill_dir in _iter_subdir_skill_dirs(skill_parent):
                        _process_skill_dir(
                            skill_dir,
                            source_tag,
                            2,
                            disabled_ids,
                            skills_dict,
                            managed=False,
                            source_root="external-client",
                            canonical=False,
                        )
                else:
                    for skill_file in skill_parent.iterdir():
                        if not skill_file.is_file() or skill_file.suffix not in _FLAT_EXTENSIONS:
                            continue
                        _process_flat_skill_file(
                            skill_file,
                            source_tag,
                            2,
                            disabled_ids,
                            skills_dict,
                            source_root="external-client",
                            canonical=False,
                        )
        except Exception as exc:
            logger.debug("Client skill discovery failed: %s", exc)  # Client skill discovery is optional

    return sorted(skills_dict.values(), key=lambda s: s.name)


def _iter_subdir_skill_dirs(skills_parent: Path):
    """Yield native skill directories under a client skills parent.

    Most SKILL.md-aware clients store skills directly under the skills parent.
    Codex also uses grouped directories such as ``.system/imagegen`` and
    ``codex-primary-runtime/spreadsheets``. Scan one grouping level so those
    real external skills are visible without recursively treating arbitrary
    reference/example directories as skill roots.
    """
    for child in sorted(skills_parent.iterdir()):
        if not child.is_dir():
            continue
        if (child / "SKILL.md").is_file():
            yield child
            continue
        for nested in sorted(child.iterdir()):
            if nested.is_dir() and (nested / "SKILL.md").is_file():
                yield nested


def _process_skill_dir(
    skill_dir: Path,
    origin: str,
    tier: int,
    disabled_ids: set[str],
    skills_dict: dict[str, SkillRecord],
    *,
    managed: bool,
    source_root: str,
    canonical: bool,
    ownership_override: str | None = None,
) -> None:
    """Process a single skill directory into a SkillRecord."""
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return

    # Generated client wrappers are still installed client skills and should
    # appear in Browse. Generated managed/plugin-cache files are not source of truth.
    if _is_auto_generated(skill_file) and tier != 2:
        return

    try:
        content = skill_file.read_text(encoding="utf-8")
    except Exception:
        return

    # Parse frontmatter — use already-loaded content to avoid a second read
    frontmatter = _extract_frontmatter(content)
    if not isinstance(frontmatter, dict):
        frontmatter = {}

    frontmatter_name = str(frontmatter.get("name") or "").strip()
    display_name = frontmatter_name or skill_dir.name
    canonical_id = normalize_skill_id(display_name or skill_dir.name)
    if not canonical_id:
        canonical_id = normalize_skill_id(skill_dir.name)

    description = str(frontmatter.get("description") or "").strip()

    triggers = _extract_triggers(frontmatter, description, content)
    capabilities = _extract_capabilities(content)

    # Check disabled state
    disabled = canonical_id in disabled_ids
    if disabled and canonical_id not in CORE_SKILLS:
        return

    # Parse x-augur-* extension fields
    # x-augur-visibility was removed in Track 4 of the cross-client bundle
    # migration; field stays on SkillRecord for backward compat but is no
    # longer populated from frontmatter.
    visibility = ""
    loop_config = _extract_dict_field(frontmatter, "x-augur-loop")
    alias = frontmatter.get("x-augur-alias")
    group = _extract_optional_group(frontmatter)
    release = _extract_optional_release(frontmatter)
    # x-augur-hub was removed in the ADR-802 hub teardown; field stays on
    # SkillRecord for backward compat but is no longer populated.
    hub = ""
    plugin_name = frontmatter.get("x-augur-plugin")
    category = str(frontmatter.get("x-augur-category") or "")
    requires_platform = _extract_bool_field(frontmatter, "x-augur-requires-platform")

    dependencies_dict = _extract_dict_field(frontmatter, "x-augur-dependencies")
    mcp_tools = _extract_list_field(frontmatter, "x-augur-mcp-tools")
    dashboard_pages = _extract_list_field(frontmatter, "x-augur-dashboard-pages")
    commands = _extract_list_field(frontmatter, "x-augur-commands")
    config = _extract_dict_field(frontmatter, "x-augur-config")
    file_intake = _extract_dict_field(frontmatter, "x-augur-file-intake")
    agent = frontmatter.get("x-augur-agent")
    if agent is not None and not isinstance(agent, dict):
        agent = None

    skill_type = str(frontmatter.get("x-augur-type") or "")
    raw_tags = frontmatter.get("x-augur-tags")
    tags = tuple(str(t) for t in raw_tags if t) if isinstance(raw_tags, list) else ()

    author = str(frontmatter.get("x-augur-created-by") or "bundled")
    ownership, upstream = _extract_ownership_and_upstream(frontmatter, managed=managed)
    if ownership_override is not None:
        ownership = ownership_override

    new_record = SkillRecord(
        name=canonical_id,
        description=description,
        path=skill_dir,
        author=author,
        hub=hub,
        visibility=visibility,
        loop_config=loop_config,
        dependencies=dependencies_dict,
        mcp_tools=mcp_tools,
        dashboard_pages=dashboard_pages,
        commands=commands,
        config=config,
        file_intake=file_intake,
        agent=agent,
        skill_type=skill_type,
        tags=tags,
        tier=tier,
        origin=origin,
        ownership=ownership,
        upstream=upstream,
        source=origin,
        source_root=source_root,
        canonical=canonical,
        client_sources=_initial_client_sources(origin),
        # Backward-compat
        master="",
        sync_enabled=False,
        display_name=display_name or canonical_id,
        triggers=tuple(triggers),
        capabilities=tuple(capabilities),
        token_estimate=len(content) // 4,
        has_modules=(skill_dir / "modules").exists(),
        has_scripts=(skill_dir / "scripts").exists(),
        has_references=(skill_dir / "references").exists(),
        has_context=(skill_dir / "context.py").exists(),
        aliases=(),
        # ADR-770 compatibility: stale shared-vault records still classify as
        # project-layer metadata during the migration window.
        layer=(
            "project" if source_root in {"project-brain", "shared-vault", "private-vault", "vault"} else "plugin-cache"
        ),
        disabled=disabled,
        alias=alias,
        group=group,
        release=release,
        plugin=plugin_name,
        category=category,
        requires_platform=requires_platform,
    )

    # Don't let lower-authority sources overwrite higher-authority metadata,
    # but keep their installation source so Browse reflects every client.
    _store_skill_record(skills_dict, canonical_id, new_record)


def _process_standard_bundle_dir(
    skill_dir: Path,
    origin: str,
    tier: int,
    disabled_ids: set[str],
    skills_dict: dict[str, SkillRecord],
    *,
    source_root: str,
    canonical: bool,
    ownership_override: str | None = None,
) -> None:
    """Process DESCRIPTION.md plus subskill SKILL.md standard bundles."""
    description_path = skill_dir / "DESCRIPTION.md"
    if not description_path.is_file():
        return

    subskill_paths = sorted(skill_dir.glob("*/SKILL.md"))
    if not subskill_paths:
        return

    _, bundle_description = _heading_and_summary_from_markdown(description_path)

    for subskill_file in subskill_paths:
        if _is_auto_generated(subskill_file):
            continue

        subskill_dir = subskill_file.parent
        canonical_id = normalize_skill_id(subskill_dir.name)
        if not canonical_id:
            continue
        disabled = canonical_id in disabled_ids
        if disabled and canonical_id not in CORE_SKILLS:
            continue

        try:
            raw = subskill_file.read_text(encoding="utf-8")
        except Exception:
            continue

        frontmatter = _extract_frontmatter(raw)
        if not isinstance(frontmatter, dict):
            frontmatter = {}
        title, summary = _heading_and_summary_from_markdown(subskill_file)
        description = str(frontmatter.get("description") or "").strip() or summary or bundle_description
        ownership, upstream = _extract_ownership_and_upstream(frontmatter, managed=True)
        if ownership_override is not None:
            ownership = ownership_override

        new_record = SkillRecord(
            name=canonical_id,
            description=description,
            path=subskill_dir,
            author=str(frontmatter.get("x-augur-created-by") or "bundled"),
            hub="",
            visibility="",
            loop_config={},
            dependencies={},
            mcp_tools=[],
            dashboard_pages=[],
            commands=[],
            config={},
            file_intake={},
            agent=None,
            skill_type="",
            tags=(),
            tier=tier,
            origin=origin,
            ownership=ownership,
            upstream=upstream,
            source=origin,
            source_root=source_root,
            canonical=canonical,
            client_sources=_initial_client_sources(origin),
            master="",
            sync_enabled=False,
            display_name=title or canonical_id,
            triggers=tuple(_extract_triggers(frontmatter, description, raw)),
            capabilities=tuple(_extract_capabilities(raw)),
            token_estimate=len(raw) // 4,
            has_modules=(subskill_dir / "modules").exists(),
            has_scripts=(subskill_dir / "scripts").exists(),
            has_references=(subskill_dir / "references").exists() or (skill_dir / "references").exists(),
            has_context=(subskill_dir / "context.py").exists(),
            aliases=(),
            layer=(
                "project"
                if source_root in {"project-brain", "shared-vault", "private-vault", "vault"}
                else "plugin-cache"
            ),
            disabled=disabled,
            alias=None,
            group=None,
            release=None,
            plugin=None,
            category="",
            requires_platform=False,
        )

        _store_skill_record(skills_dict, canonical_id, new_record)


# ---------------------------------------------------------------------------
# Backward-compatible wrappers
# ---------------------------------------------------------------------------


def _skill_record_to_metadata(record: SkillRecord) -> SkillMetadata:
    """Convert a SkillRecord to the legacy SkillMetadata format."""
    deps = record.dependencies
    if isinstance(deps, dict):
        dep_list = list(deps.keys()) if deps else []
    elif isinstance(deps, (list, tuple)):
        dep_list = list(deps)
    else:
        dep_list = []

    return SkillMetadata(
        id=record.name,
        display_name=record.display_name,
        description=record.description,
        triggers=record.triggers,
        capabilities=record.capabilities,
        token_estimate=record.token_estimate,
        has_modules=record.has_modules,
        has_scripts=record.has_scripts,
        has_references=record.has_references,
        has_context=record.has_context,
        path=record.path,
        aliases=record.aliases,
        layer=record.layer,
        disabled=record.disabled,
        dependencies=tuple(dep_list),
        visibility=record.visibility or None,
        loop_config=record.loop_config or None,
        alias=record.alias,
        group=record.group,
        release=record.release,
        master=record.master or None,
        sync_enabled=record.sync_enabled,
        origin=record.origin,
        plugin=record.plugin,
        category=record.category or None,
        requires_platform=record.requires_platform,
        skill_type=record.skill_type,
        tags=record.tags,
        client_sources=record.client_sources,
    )


def list_skills(*, plugins_dir: Optional[Path] = None, include_disabled: bool = False) -> list[SkillMetadata]:
    """List all skills as SkillMetadata (backward-compatible wrapper)."""
    records = discover_all_skills()
    return [_skill_record_to_metadata(r) for r in records]


def _build_skill_index(skills: list[SkillMetadata]) -> dict[str, SkillMetadata]:
    """Build a searchable index from a list of skills."""
    index: dict[str, SkillMetadata] = {}
    for skill in skills:
        index.setdefault(skill.id, skill)
    return index


def resolve_skill(
    skill_name: str, *, plugins_dir: Optional[Path] = None, include_disabled: bool = False
) -> Optional[SkillMetadata]:
    """Resolve a skill name to its metadata."""
    skills = list_skills(plugins_dir=plugins_dir, include_disabled=include_disabled)
    index = _build_skill_index(skills)
    return index.get(normalize_skill_id(skill_name))


def get_skill_path(
    skill_name: str, *, plugins_dir: Optional[Path] = None, include_disabled: bool = False
) -> Optional[Path]:
    """Get the filesystem path for a skill."""
    entry = resolve_skill(skill_name, plugins_dir=plugins_dir, include_disabled=include_disabled)
    return entry.path if entry else None


__all__ = [
    "SkillRecord",
    "SkillMetadata",
    "discover_all_skills",
    "invalidate_discovery_cache",
    "list_skills",
    "resolve_skill",
    "get_skill_path",
    "normalize_skill_id",
    "infer_master",
    "CORE_SKILLS",
    "_is_auto_generated",
    "_extract_frontmatter",
    "_extract_dependencies_tuple",
    "_iter_skill_dirs",
    "_default_plugins_dir",
]
