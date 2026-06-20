"""
Centralized path configuration for Augur.

ADR-270 splits Augur into independent storage layers:
- Engine + plugins (repo)
- User data vault
- Binary documents
- Central RAG indexes
- Persistent state
- Logs
- Caches
- LaunchAgents

All code should resolve filesystem locations through this module.
"""

# TODO_CLEANUP: This file is 894 lines — consider splitting into smaller modules

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from src.config import path_primitives

if TYPE_CHECKING:
    from src.config.path_config import PathConfig
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_stack import BrainStack


# Re-export primitives as module-private names for internal use
_expand = path_primitives.expand_path
_env_path = path_primitives.env_path
_is_macos = path_primitives.is_macos


import yaml as _yaml_mod

_project_name_cache: str | None = None


def get_project_name() -> str:
    """Read project name from project.yaml at repo root. Cached after first read."""
    global _project_name_cache
    if _project_name_cache is not None:
        return _project_name_cache
    project_yaml = get_project_root() / "project.yaml"
    if project_yaml.exists():
        data = _yaml_mod.safe_load(project_yaml.read_text(encoding="utf-8"))
        _project_name_cache = data.get("name", "Augur") if isinstance(data, dict) else "Augur"
    else:
        _project_name_cache = "Augur"
    return _project_name_cache


_project_port_cache: int | None = None

_KNOWN_PATH_KEYS = {"vault", "documents"}

_project_paths_cache: dict[str, Path] | None = None


def get_project_paths() -> dict[str, Path]:
    """Read paths: block from project.yaml. Cached after first read."""
    global _project_paths_cache
    if _project_paths_cache is not None:
        return _project_paths_cache
    result: dict[str, Path] = {}
    if not os.environ.get("AUGUR_PATH_LEGACY"):
        project_yaml = get_project_root() / "project.yaml"
        try:
            data = _yaml_mod.safe_load(project_yaml.read_text(encoding="utf-8"))
            paths_block = data.get("paths", {}) if isinstance(data, dict) else {}
            if isinstance(paths_block, dict):
                for key in _KNOWN_PATH_KEYS:
                    value = paths_block.get(key)
                    if value and isinstance(value, str):
                        result[key] = Path(os.path.expanduser(value)).resolve()
        except Exception:
            import logging

            logging.getLogger(__name__).warning("Failed to read paths from %s", project_yaml, exc_info=True)
    _project_paths_cache = result
    return _project_paths_cache


def get_project_port() -> int:
    """Read dashboard port from project.yaml. Cached after first read. Defaults to 3000."""
    global _project_port_cache
    if _project_port_cache is not None:
        return _project_port_cache
    project_yaml = get_project_root() / "project.yaml"
    if project_yaml.exists():
        data = _yaml_mod.safe_load(project_yaml.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            _project_port_cache = int(data.get("port", 3000))
        else:
            _project_port_cache = 3000
    else:
        _project_port_cache = 3000
    return _project_port_cache


def invalidate_project_cache() -> None:
    """Clear all cached project config."""
    global _project_name_cache, _project_port_cache, _project_paths_cache
    _project_name_cache = None
    _project_port_cache = None
    _project_paths_cache = None
    _dir_cache.clear()


def _application_support_dir() -> Path:
    return _env_path("AUGUR_APP_SUPPORT") or path_primitives.application_support_dir(get_project_name())


def _state_home_dir() -> Path:
    return _env_path("AUGUR_STATE") or (
        _application_support_dir() / "state"
        if path_primitives.is_macos()
        else path_primitives.state_home_dir(get_project_name())
    )


def _logs_home_dir() -> Path:
    return _env_path("AUGUR_LOGS") or path_primitives.logs_home_dir(get_project_name())


def _cache_home_dir() -> Path:
    return _env_path("AUGUR_CACHE_DIR", "AUGUR_CACHE_PATH") or path_primitives.cache_home_dir(get_project_name())


def _vault_home_dir() -> Path:
    env = _env_path("AUGUR_VAULT")
    if env:
        return env
    yaml_path = get_project_paths().get("vault")
    if yaml_path:
        return yaml_path
    return path_primitives.vault_home_dir(get_project_name())


def _documents_home_dir() -> Path:
    env = _env_path("AUGUR_DOCUMENTS")
    if env:
        return env
    yaml_path = get_project_paths().get("documents")
    if yaml_path:
        return yaml_path
    return path_primitives.documents_home_dir(get_project_name())


def _rag_home_dir() -> Path:
    override = _env_path("AUGUR_RAG")
    if override:
        return override
    return _application_support_dir() / "rag"


def _launch_agents_dir() -> Path:
    override = _env_path("AUGUR_LAUNCH_AGENTS")
    if override:
        return override
    if _is_macos():
        return _expand("~/Library/LaunchAgents")
    return _state_home_dir() / "launch-agents"


def _windows_roaming_dir() -> Path:
    """Return the Windows roaming AppData directory."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata)
    return Path.home() / "AppData" / "Roaming"


def _windows_local_dir() -> Path:
    """Return the Windows local AppData directory."""
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata)
    return Path.home() / "AppData" / "Local"


def _project_root_from_file() -> Path:
    # src/config/paths.py -> src/config -> src -> repo root
    return Path(__file__).resolve().parents[2]


def _project_root_from_cwd() -> Path | None:
    """Resolve the active Augur repo/worktree root from the current cwd."""
    try:
        current = Path.cwd().resolve()
    except OSError:
        return None

    for candidate in (current, *current.parents):
        if not (candidate / "project.yaml").is_file():
            continue
        git_entry = candidate / ".git"
        if git_entry.exists():
            return candidate
    return None


def get_project_root() -> Path:
    """Return the Augur engine/plugins repository root."""
    cwd_root = _project_root_from_cwd()
    env_root = _env_path("AUGUR_ROOT", "AUGUR_CORE", "AUGUR_REPO")
    if env_root is not None:
        if cwd_root is not None and env_root != cwd_root:
            return cwd_root
        return env_root
    return cwd_root or _project_root_from_file()


def get_core_repo() -> Path:
    """Alias for the engine/plugins repository root."""
    return get_project_root()


def get_user_repo() -> Path:
    """Alias retained for older callers that treated the monorepo as the user repo."""
    return get_project_root()


def get_skills_dir() -> Path:
    """Canonical shared/team skills directory."""
    return get_project_brain_skills_dir()


def get_client_cache_dirs() -> dict[str, Path]:
    """Client cache directories for multi-source skill discovery."""
    home = Path.home()
    return {
        "claude-code": home / ".claude" / "plugins" / "cache",
        "codex": home / ".codex" / "prompts",
        "cursor": home / ".cursor" / "rules",
        "gemini": home / ".gemini" / "skills",
        "opencode": home / ".config" / "opencode" / "skills",
    }


def _get_claude_plugin_cache_dir() -> Path:
    """Return the Claude Code plugin cache directory."""
    override = _env_path("AUGUR_CLAUDE_PLUGIN_CACHE")
    if override:
        return override
    return _expand("~/.claude/plugins/cache")


def _version_key(version_dir: Path) -> tuple[int, ...]:
    """Parse a version directory name into a sortable tuple."""
    try:
        return tuple(int(x) for x in version_dir.name.split("."))
    except (ValueError, AttributeError):
        return (0,)


def get_claude_plugin_skill_dirs() -> list[Path]:
    """Discover skill directories from Claude Code plugin cache.

    Prefer Claude's installed plugin registry so project-scoped installs and
    non-standard plugin layouts are represented accurately. Falls back to
    scanning ~/.claude/plugins/cache/{publisher}/{plugin}/{version}/skills/.
    """
    cache_dir = _get_claude_plugin_cache_dir()
    if not cache_dir.is_dir():
        return []

    registry_dirs = _claude_installed_plugin_skill_dirs(cache_dir)
    if registry_dirs:
        return registry_dirs

    dirs: list[Path] = []
    for publisher_dir in cache_dir.iterdir():
        if not publisher_dir.is_dir() or publisher_dir.name.startswith("."):
            continue
        for plugin_dir in publisher_dir.iterdir():
            if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
                continue
            # Find the highest version with a skills/ directory
            versions = sorted(
                (v for v in plugin_dir.iterdir() if v.is_dir() and _claude_plugin_skill_parent_dirs(v)),
                key=_version_key,
                reverse=True,
            )
            if versions:
                dirs.extend(_claude_plugin_skill_parent_dirs(versions[0]))
    return dirs


def _claude_installed_plugin_skill_dirs(cache_dir: Path) -> list[Path]:
    plugins_dir = cache_dir.parent
    installed_path = plugins_dir / "installed_plugins.json"
    if not installed_path.is_file():
        return []

    try:
        payload = json.loads(installed_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    plugins = payload.get("plugins")
    if not isinstance(plugins, dict):
        return []

    enabled_plugins = _claude_enabled_plugins(plugins_dir.parent / "settings.json")
    current_project = str(get_project_root())
    dirs: list[Path] = []
    seen: set[Path] = set()

    for plugin_id, installs in plugins.items():
        plugin_id_text = str(plugin_id)
        if not _claude_plugin_is_active_for_inventory(
            plugin_id_text,
            enabled_plugins,
        ):
            continue
        if not isinstance(installs, list):
            continue
        for install in installs:
            if not isinstance(install, dict):
                continue
            project_path = str(install.get("projectPath") or "").strip()
            if project_path and project_path != current_project:
                continue
            install_path = _expand(str(install.get("installPath") or ""))
            if not install_path.is_dir():
                continue
            for skills_dir in _claude_plugin_skill_parent_dirs(install_path):
                resolved = skills_dir.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    dirs.append(skills_dir)
    return dirs


def _claude_enabled_plugins(settings_path: Path) -> dict[str, bool]:
    if not settings_path.is_file():
        return {}
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    enabled = payload.get("enabledPlugins")
    if not isinstance(enabled, dict):
        return {}
    return {str(key): bool(value) for key, value in enabled.items()}


def _claude_plugin_is_active_for_inventory(
    plugin_id: str,
    enabled_plugins: dict[str, bool],
) -> bool:
    if plugin_id in enabled_plugins:
        return enabled_plugins[plugin_id]
    marketplace = plugin_id.rsplit("@", 1)[-1]
    return marketplace != "claude-plugins-official"


def _claude_plugin_skill_parent_dirs(plugin_root: Path) -> list[Path]:
    candidates = (plugin_root / "skills", plugin_root / ".claude" / "skills")
    return [candidate for candidate in candidates if candidate.is_dir()]


def _read_skill_frontmatter(skill_dir: Path) -> dict | None:
    """Read YAML frontmatter from a skill's SKILL.md."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    try:
        content = skill_md.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return None
        end = content.find("---", 3)
        if end == -1:
            return None
        import yaml as _yaml

        fm = _yaml.safe_load(content[3:end])
        return fm if isinstance(fm, dict) else None
    except Exception:
        return None


def _read_skill_plugin(skill_dir: Path) -> str | None:
    """Read x-augur-plugin from a skill's SKILL.md frontmatter.

    Plugin name (e.g. 'augur-dev') is the stable identifier for vault paths.
    Hub names are a UI concept that can change; plugin names remain stable.
    """
    fm = _read_skill_frontmatter(skill_dir)
    return fm.get("x-augur-plugin") if fm else None


def find_skill_root(skill_name: str) -> Path | None:
    """Resolve a managed skill by name from repo or vault skill roots."""
    normalized_name = str(skill_name).strip()
    if not normalized_name:
        return None

    for skills_dir in get_managed_skill_source_dirs():
        skill_path = skills_dir / normalized_name
        if skill_path.exists():
            return skill_path
    return None


def get_skill_root(skill_name: str) -> Path:
    """Resolve a managed skill by name from repo or vault skill roots."""
    skill_path = find_skill_root(skill_name)
    if skill_path is not None:
        return skill_path

    looked_in = get_managed_skill_source_dirs()
    if not looked_in:
        looked_in = [get_skills_dir()]
    looked_in_text = ", ".join(str(path) for path in looked_in)
    raise ValueError(f"Skill not found: {skill_name} (looked in {looked_in_text})")


def get_skill_augur_dir(skill_name: str) -> Path:
    return get_skill_root(skill_name) / "augur"


def get_skill_assets_dir(skill_name: str) -> Path:
    return get_skill_root(skill_name) / "assets"


import logging as _logging

_dir_cache: dict[str, Path] = {}


def _resolve_with_discovery(path_type: str, resolved: Path) -> Path:
    """Return resolved path, falling back to self-discovery if it doesn't exist."""
    if resolved.exists():
        return resolved
    try:
        from src.config.path_discovery import discover_path

        discovered = discover_path(path_type, configured=resolved, skills_dir=get_skills_dir())
        if discovered:
            _logging.getLogger(__name__).info(
                "%s not at configured %s, using discovered %s. " "Run 'augur config fix' to update project.yaml.",
                path_type.title(),
                resolved,
                discovered,
            )
            return discovered
    except Exception:
        _logging.getLogger(__name__).debug("Discovery failed for %s", path_type, exc_info=True)
    return resolved


def get_vault_dir() -> Path:
    cached = _dir_cache.get("vault")
    if cached is not None:
        return cached
    result = _resolve_with_discovery("vault", _vault_home_dir())
    _dir_cache["vault"] = result
    return result


def get_vault_drafts_dir() -> Path:
    # deferred import: paths.py must stay importable before src.lib (avoid cycle at module init)
    from src.lib.brain_layout import vault_machine_dir

    return vault_machine_dir(get_vault_dir(), "drafts")


def get_vault_staging_dir() -> Path:
    return get_vault_drafts_dir() / "staging"


def get_vault_archive_dir() -> Path:
    from src.lib.brain_layout import vault_machine_dir

    return vault_machine_dir(get_vault_dir(), "archive")


# TODO_CLEANUP: no in-repo production callers since the domains-layout
# migration (writers/scanners route through brain_capture_dir); kept as a
# public helper for external/client callers — candidate for removal.
def get_vault_notes_dir() -> Path:
    from src.lib.brain_layout import brain_notes_root

    return brain_notes_root(get_vault_dir())


def get_vault_prompts_dir() -> Path:
    from src.lib.brain_layout import vault_machine_dir

    return vault_machine_dir(get_vault_dir(), "prompts")


def get_vault_config_dir() -> Path:
    from src.lib.brain_layout import vault_machine_dir

    return vault_machine_dir(get_vault_dir(), "config")


def get_vault_skills_dir() -> Path:
    from src.lib.brain_layout import vault_machine_dir

    return vault_machine_dir(get_vault_dir(), "capabilities") / "skills"


# ADR-770 note: the deprecated get_shared_vault_* / get_shared_wiki_dir
# compatibility wrappers expired (one-release grace period ended with v1.6.0)
# and were removed — use the get_project_brain_* helpers directly.


def get_private_vault_dir() -> Path:
    """Alias for the configured user-owned vault root."""
    return get_vault_dir()


def get_private_vault_skills_dir() -> Path:
    return get_vault_skills_dir()


def get_private_wiki_dir() -> Path:
    return get_wiki_dir()


def get_vault_source_roots(project_root: Path | None = None) -> list[tuple[str, Path]]:
    """Return shared and private vault roots in read-precedence order."""
    if project_root is None:
        return [
            ("project", get_project_brain_dir()),
            ("private", get_private_vault_dir()),
        ]
    root = project_root.resolve()
    return [
        ("project", get_project_brain_dir(root)),
        ("private", get_configured_vault_dir(root)),
    ]


_VAULT_FIRST_SKILL_VAULT_DIRS: dict[str, Path] = {
    "advisor": Path("augur/advisor"),
    "ai": Path("config/ai"),
    "apple": Path("lifestyle/apple"),
    "attention": Path("config/attention"),
    "books": Path("books"),
    "career": Path("career"),
    "career-ops": Path("career"),
    "channels": Path("config/attention"),
    "content": Path("venture/content"),
    "dashboard": Path("config/dashboard"),
    "daemon": Path("config/daemon"),
    "document-extractor": Path("config/document-extractor"),
    "eisenhower": Path("lifestyle/eisenhower"),
    "file-manager": Path("config/file-manager"),
    "finance": Path("finance"),
    "google-workspace": Path("config/google-workspace"),
    "growth": Path("career/growth"),
    "health": Path("health"),
    "lifestyle": Path("lifestyle"),
    "linkedin-writer": Path("venture/content/linkedin"),
    "platform-admin": Path("augur/platform-admin"),
    "reading-list": Path("books"),
    "remote-access": Path("config/remote-access"),
    "updater": Path("config/updater"),
    "venture": Path("venture"),
    "venture-augur": Path("venture"),
    "websites": Path("config/websites"),
}


def get_skill_vault_relative_dir(skill_name: str) -> Path:
    """Return a skill's vault-relative data/config directory."""
    return _VAULT_FIRST_SKILL_VAULT_DIRS.get(skill_name, Path(skill_name))


def _project_yaml_for_root(project_root: Path) -> dict:
    project_yaml = project_root / "project.yaml"
    if not project_yaml.is_file():
        return {}
    try:
        data = _yaml_mod.safe_load(project_yaml.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def get_configured_vault_dir(project_root: Path | None = None) -> Path:
    """Return the configured vault root without discovery fallback probing."""
    if project_root is None:
        env = _env_path("AUGUR_VAULT")
        if env:
            return env
        return _vault_home_dir()

    data = _project_yaml_for_root(project_root.resolve())
    paths_block = data.get("paths", {})
    if isinstance(paths_block, dict):
        value = paths_block.get("vault")
        if value and isinstance(value, str):
            return Path(os.path.expanduser(value)).resolve()

    name = data.get("name", "Augur") if isinstance(data.get("name"), str) else "Augur"
    return path_primitives.vault_home_dir(name)


def get_configured_vault_skills_dir(project_root: Path | None = None) -> Path:
    """Return the configured vault skills directory (capabilities/skills layout)."""
    return get_configured_vault_dir(project_root) / "capabilities" / "skills"


def get_adaptive_loop_skill_dirs(project_root: Path | None = None) -> list[Path]:
    """Return real skill source dirs used for adaptive loop discovery."""
    root = project_root.resolve() if project_root is not None else get_project_root().resolve()
    dirs: list[Path] = []
    seen: set[Path] = set()

    for candidate in (get_project_brain_skills_dir(root), get_configured_vault_skills_dir(root)):
        if not candidate.is_dir():
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        dirs.append(candidate)
        seen.add(resolved)

    return dirs


def get_managed_skill_source_dirs(project_root: Path | None = None) -> list[Path]:
    root = project_root.resolve() if project_root is not None else get_project_root().resolve()
    live_root = get_project_root().resolve()
    has_project_brain_manifest = (root / "project-brain" / "BRAIN.yaml").is_file()
    try:
        from src.lib.brain_layered_projection import layered_skill_source_dirs
        from src.lib.brain_stack import resolve_active_stack

        if root == live_root or has_project_brain_manifest:
            stack = resolve_active_stack(cwd=root, registry_path=get_brain_registry_path())
            roots = [
                Path(candidate)
                for candidate in layered_skill_source_dirs(stack, project_root=root)
                if Path(candidate).is_dir()
            ]
            if roots:
                return roots
    except Exception:
        pass

    dirs: list[Path] = []
    candidates = [
        get_project_brain_skills_dir(root),
        get_configured_vault_skills_dir(root),
    ]

    if root == live_root:
        candidates.append(get_vault_skills_dir())

    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        dirs.append(candidate)
        seen.add(resolved)

    return dirs


def project_tier_skill_source_dirs(project_root: Path | None = None) -> list[Path]:
    """Return managed skill roots that belong to the PROJECT tier only.

    This is ``get_managed_skill_source_dirs`` minus the private/user vault
    skill roots (the configured vault and the legacy vault). The project-tier
    ``augur-framework`` MCP monolith uses this so it never loads private vault
    skills; those are served exclusively by dedicated vault-tier servers
    (``bundle_server``). See ADR-795.

    Filtering by root (rather than by bundle name) keeps the boundary
    structural and future-proof: any new private skill dropped into the vault
    is excluded automatically, with no per-bundle blocklist to maintain.
    """
    root = project_root.resolve() if project_root is not None else get_project_root().resolve()
    private_roots: set[Path] = set()
    for candidate in (get_configured_vault_skills_dir(root), get_vault_skills_dir()):
        try:
            private_roots.add(candidate.resolve())
        except OSError:
            continue

    return [
        skills_dir for skills_dir in get_managed_skill_source_dirs(root) if skills_dir.resolve() not in private_roots
    ]


def get_adr_dir() -> Path:
    """ADR directory — lives in the project brain at project-brain/decisions/adrs/ per ADR-811.

    ADR-608 placed ADRs at docs/adrs/; ADR-811 supersedes that location clause
    so decisions live inside the project brain (plain markdown, including the
    extracted archive). Release exposure is unchanged: the public docs-only
    tree forbids project-brain/** entirely.
    """
    return get_project_root() / "project-brain" / "decisions" / "adrs"


def get_skill_vault_dir(skill_name: str) -> Path:
    """Resolve a skill's vault directory. Validates against skill names and .augur-reserved."""
    from src.lib.brain_layout import join_brain_relative
    from src.lib.dir_alignment import ManagedLocation, validate_dir_name

    vault = get_vault_dir()
    location = ManagedLocation(path=vault)
    if not validate_dir_name(location, skill_name):
        raise ValueError(
            f"'{skill_name}' is not a recognized skill name. " "Add it to .augur-reserved or create a skill first."
        )
    return join_brain_relative(vault, get_skill_vault_relative_dir(skill_name))


def get_skill_vault_dirs(skill_name: str) -> list[Path]:
    """Return active vault dirs for a skill, plus existing legacy/config fallbacks."""
    candidates = [get_skill_vault_dir(skill_name)]

    legacy = get_vault_dir() / skill_name
    if legacy.exists():
        candidates.append(legacy)

    config_candidate = get_vault_config_dir() / skill_name
    if config_candidate.exists():
        candidates.append(config_candidate)

    result: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        result.append(candidate)
        seen.add(resolved)
    return result


def get_documents_dir() -> Path:
    cached = _dir_cache.get("documents")
    if cached is not None:
        return cached
    result = _resolve_with_discovery("documents", _documents_home_dir())
    _dir_cache["documents"] = result
    return result


def get_documents_machine_dir(name: str) -> Path:
    """Machine-output subdir of the documents store (under _augur/ since the
    2026-06-12 reorg): evals, reports, dev, test-security, consulting-template."""
    return get_documents_dir() / "_augur" / name


def get_wiki_dir() -> Path:
    """Durable compiled wiki pages directory stored in the git-tracked vault."""
    from src.lib.brain_layout import brain_wiki_dir

    return brain_wiki_dir(get_vault_dir())


def get_runtime_wiki_dir() -> Path:
    """Runtime wiki state root for compiler state, batches, and transient metadata."""
    return get_runtime_dir() / "wiki"


def get_ide_integration_dir() -> Path:
    """Runtime IDE integration state generated by local sync/discovery."""
    return get_runtime_dir() / "ide-integration"


def get_ide_registry_path() -> Path:
    """Canonical generated IDE registry consumed by context injection."""
    return get_ide_integration_dir() / "registry.yaml"


def get_compiled_wiki_dir(wiki_dir: Path | None = None) -> Path:
    """Durable compiled wiki pages directory.

    The compiled wiki is accumulated long-term knowledge, not disposable runtime
    state. Runtime wiki paths are reserved for compiler mechanics.
    """
    return wiki_dir or get_wiki_dir()


def resolve_wiki_dir(sources: list[str] | None = None) -> Path:
    """Active durable wiki pages directory.

    Routes by the page's subject brain when ``sources`` is given (project sources
    → project-brain wiki, else the personal vault wiki). Without ``sources``,
    honors the AUGUR_WIKI_TARGET_BRAIN=project env override, else defaults to the
    personal vault wiki. Only the durable pages dir is affected; runtime wiki
    state stays global.
    """
    if sources:
        from src.lib.brain_classify.route import target_brain_for_sources

        if target_brain_for_sources(sources) == "project":
            return get_project_brain_wiki_dir()
        return get_wiki_dir()
    target = os.environ.get("AUGUR_WIKI_TARGET_BRAIN", "").strip().lower()
    if target == "project":
        return get_project_brain_wiki_dir()
    return get_wiki_dir()


def get_skill_documents_dir(skill_name: str) -> Path:
    """Resolve a skill's documents directory. Validates against skill names and .augur-reserved."""
    from src.lib.dir_alignment import ManagedLocation, validate_dir_name

    docs = get_documents_dir()
    location = ManagedLocation(path=docs)
    if not validate_dir_name(location, skill_name):
        raise ValueError(
            f"'{skill_name}' is not a recognized skill name. " "Add it to .augur-reserved or create a skill first."
        )
    return docs / skill_name


def get_rag_dir() -> Path:
    return _rag_home_dir()


def get_skill_rag_dir(skill_name: str) -> Path:
    return get_rag_dir() / skill_name


def get_project_index_path() -> Path:
    return get_rag_dir() / "project-index.yaml"


def get_rag_category_dir(category: str) -> Path:
    """Return the RAG index directory for a specific category."""
    return get_rag_dir() / category


def get_state_dir() -> Path:
    return _state_home_dir()


def get_runtime_dir() -> Path:
    """
    Return the persistent runtime state root.

    ADR-270 splits logs and cache out into dedicated platform locations.
    Existing callers that need stateful runtime files should use this root.
    """
    return get_state_dir()


def get_pending_enrichment_queue_path() -> Path:
    return get_runtime_dir() / "pending_enrichment.jsonl"


def get_logs_dir() -> Path:
    return _logs_home_dir()


def get_cache_dir() -> Path:
    return _cache_home_dir()


def get_ipc_dir() -> Path:
    return get_state_dir() / "ipc"


def get_archives_dir() -> Path:
    return get_cache_dir() / "archive"


def get_temp_archive_dir() -> Path:
    return get_archives_dir()


def get_launch_agents_dir() -> Path:
    return _launch_agents_dir()


def get_skill_data_dir(skill_name: str) -> Path:
    """User-editable skill content lives in the external vault."""
    return get_skill_vault_dir(skill_name)


def get_hardening_dir(skill_name: str = "") -> Path:
    """Hardening reports live in runtime state, not user vault (ADR-416).

    Returns: ~/Library/Application Support/Augur/state/hardening/{skill_name}/
    """
    base = get_runtime_dir() / "hardening"
    if skill_name:
        return base / skill_name
    return base


def get_memory_dir() -> Path:
    override = _env_path("AUGUR_MEMORY")
    if override:
        return override
    from src.lib.brain_layout import brain_knowledge_dir

    return brain_knowledge_dir(get_vault_dir()) / "memory"


def get_prompts_dir() -> Path:
    return get_config_dir() / "agents" / "prompts"


def get_config_dir() -> Path:
    return get_project_root() / "config"


def validate_paths() -> bool:
    # Repo-internal dirs — always create
    repo_dirs = [
        get_config_dir(),
        get_skills_dir(),
        get_project_brain_dir(),
        get_project_brain_notes_dir(),
        get_project_brain_sources_dir(),
        get_project_brain_wiki_dir(),
        get_project_brain_skills_dir(),
        get_project_brain_config_dir(),
    ]
    for directory in repo_dirs:
        directory.mkdir(parents=True, exist_ok=True)

    # External dirs — vault is optional for new users (ADR-440)
    external_dirs = [
        get_vault_dir(),
        get_vault_skills_dir(),
        get_vault_staging_dir(),
        get_wiki_dir(),
        get_documents_dir(),
        get_rag_dir(),
        get_state_dir(),
        get_logs_dir(),
        get_cache_dir(),
        get_memory_dir(),
    ]
    for directory in external_dirs:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            import logging

            logging.getLogger(__name__).warning("Could not create %s — vault/external dirs are optional", directory)
    return True


def get_path_config(refresh: bool = False) -> "PathConfig":
    from src.config.path_config import get_path_config as _get_config

    return _get_config(refresh=refresh)


# Client IDE/CLI config directories
_CLIENT_DEFAULTS: dict[str, str] = {
    "claude-code": ".claude",
    "codex": ".codex",
    "copilot": ".github",
    "cursor": ".cursor",
    "gemini": ".gemini",
    "opencode": ".opencode",
}

_CLIENT_ENV_VARS: dict[str, str] = {
    "claude-code": "AUGUR_CLAUDE_CONFIG",
    "codex": "AUGUR_CODEX_CONFIG",
    "copilot": "AUGUR_COPILOT_CONFIG",
    "cursor": "AUGUR_CURSOR_CONFIG",
    "gemini": "AUGUR_GEMINI_CONFIG",
    "opencode": "AUGUR_OPENCODE_CONFIG",
}


def _get_claude_desktop_runtime_dir() -> Path:
    """Return the user-level Claude Desktop support directory."""
    home = Path.home()
    if sys.platform == "win32":
        return _windows_roaming_dir() / "Claude"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "Claude"
    return home / ".config" / "Claude"


def get_all_client_skill_dirs(project_root: Path | None = None) -> list[Path]:
    """Return all managed and external skill directories that exist on disk."""
    dirs: list[Path] = []
    root = project_root.resolve() if project_root is not None else get_project_root().resolve()

    for managed_dir in get_managed_skill_source_dirs(root):
        if not managed_dir.is_dir():
            continue
        dirs.append(managed_dir)

    seen = {path.resolve() for path in dirs}

    live_project_root = get_project_root().resolve()
    if root == live_project_root:
        client_dirs = get_client_skill_dirs().values()
    else:
        client_dirs = [
            root / ".claude" / "skills",
            root / ".codex" / "skills",
            root / ".gemini" / "skills",
            root / ".cursor" / "rules",
            root / ".github" / "instructions",
            root / ".opencode" / "skills",
        ]

    for client_dir in client_dirs:
        if not client_dir.is_dir():
            continue
        resolved = client_dir.resolve()
        if resolved in seen:
            continue
        dirs.append(client_dir)
        seen.add(resolved)

    # Include Claude Code plugin cache skill directories
    for plugin_dir in get_claude_plugin_skill_dirs():
        if not plugin_dir.is_dir():
            continue
        resolved = plugin_dir.resolve()
        if resolved in seen:
            continue
        dirs.append(plugin_dir)
        seen.add(resolved)
    return dirs


def get_client_config_dir(client: str, scope: str = "global") -> Path:
    """Return the config directory for a client IDE/CLI.

    Args:
        client: 'claude-code' | 'codex' | 'gemini'
        scope: 'global' (user-level) | 'project' (cwd-relative)

    Returns:
        Path (may not exist — callers handle non-existence)

    Raises:
        ValueError: If client is not recognized
    """
    if client not in _CLIENT_DEFAULTS:
        raise ValueError(f"Unknown client: {client}. Expected one of: {list(_CLIENT_DEFAULTS.keys())}")

    env_var = _CLIENT_ENV_VARS[client]
    env_val = os.environ.get(env_var)
    if env_val:
        return Path(env_val)

    dir_name = _CLIENT_DEFAULTS[client]
    if scope == "project":
        return Path.cwd() / dir_name

    if client == "opencode":
        return Path.home() / ".config" / "opencode"

    return Path.home() / dir_name


def get_client_runtime_dir(client: str, scope: str = "global") -> Path:
    """Return the runtime/config root folder for a supported client.

    Unlike config file paths, this always resolves to the directory users
    typically inspect when debugging client runtime state.
    """
    if client == "claude-desktop":
        if scope != "global":
            raise ValueError("Claude Desktop supports only global runtime scope")
        return _get_claude_desktop_runtime_dir()
    if client == "antigravity":
        if scope != "global":
            raise ValueError("Antigravity supports only global runtime scope")
        return get_client_config_dir("gemini", scope="global") / "antigravity"
    return get_client_config_dir(client, scope=scope)


def encode_claude_project_path(project_root: Path | str) -> str:
    """Return Claude Code's project-state directory name for a project path."""
    raw = str(project_root.resolve()) if isinstance(project_root, Path) else str(project_root)
    return raw.replace("\\", "-").replace("/", "-").replace(":", "-")


def get_claude_native_memory_dir(
    project_root: Path | str | None = None,
    *,
    create: bool = False,
) -> Path | None:
    """Return Claude Code's project-specific native memory directory.

    Claude Code stores session state under ``~/.claude/projects/<encoded-path>``.
    The encoded path must be a plain directory name on every OS; otherwise a
    Windows drive path can escape the Claude state root and point back into the
    repository.
    """
    root = project_root if project_root is not None else get_project_root()
    project_dir = Path.home() / ".claude" / "projects" / encode_claude_project_path(root)
    memory_dir = project_dir / "memory"
    if memory_dir.is_dir():
        return memory_dir
    if create and project_dir.is_dir():
        memory_dir.mkdir(parents=True, exist_ok=True)
        return memory_dir
    return None


def get_client_skill_dirs() -> dict[str, Path]:
    """Return skill directories for all supported AI clients, keyed by source tag.

    Returns:
        Dict mapping source tags to skill directory paths. Paths may not exist.
    """
    project_root = get_project_root()
    home = Path.home()
    return {
        "claude-local": project_root / ".claude" / "skills",
        "claude-global": home / ".claude" / "skills",
        "codex-local": project_root / ".codex" / "skills",
        "codex-global": home / ".codex" / "skills",
        "codex-global-superpowers": home / ".codex" / "superpowers" / "skills",
        "gemini-local": project_root / ".antigravity" / "plugins",
        "gemini-global": home / ".antigravity" / "plugins",
        "cursor-local": project_root / ".cursor" / "rules",
        "cursor-global": home / ".cursor" / "rules",
        "copilot-local": project_root / ".github" / "instructions",
        "copilot-global": home / ".github" / "instructions",
        "opencode-local": project_root / ".opencode" / "skills",
        "opencode-global": home / ".config" / "opencode" / "skills",
    }


def get_codex_native_skills_dir(scope: str = "global") -> Path:
    """Return the Codex native skills directory for the requested scope."""
    if scope not in {"project", "global"}:
        raise ValueError(f"Unknown Codex native scope: {scope}")

    override_key = "AUGUR_CODEX_NATIVE_SKILLS_PROJECT" if scope == "project" else "AUGUR_CODEX_NATIVE_SKILLS"
    override = os.environ.get(override_key)
    if override:
        return Path(override)

    if scope == "project":
        return get_project_root() / ".codex" / "skills"
    return Path.home() / ".agents" / "skills" / "augur"


def get_codex_prompt_dir(scope: str = "global") -> Path:
    """Return the Codex prompt mirror directory for the requested scope."""
    if scope not in {"project", "global"}:
        raise ValueError(f"Unknown Codex prompt scope: {scope}")

    override_key = "AUGUR_CODEX_PROMPTS_PROJECT" if scope == "project" else "AUGUR_CODEX_PROMPTS"
    override = os.environ.get(override_key)
    if override:
        return Path(override)

    if scope == "project":
        return get_project_root() / ".codex" / "prompts"
    return Path.home() / ".codex" / "prompts"


def get_dynamic_runtime_dir() -> Path:
    return get_path_config().runtime.path


def get_python_executable() -> Path:
    """Resolve the project venv Python, falling back to sys.executable.

    Prevents breakage when scripts are launched by system Python
    (e.g., via #!/usr/bin/env python3 or Claude Code agents) and then
    spawn subprocesses that need project dependencies.
    """
    root = get_project_root()
    if os.name == "nt":
        venv_python = root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = root / ".venv" / "bin" / "python3"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def get_wiki_signals_config_path(project_root: Path | None = None) -> Path:
    """Return the wiki signal priority config path."""
    root = Path(project_root) if project_root is not None else get_project_root()
    return root / "config" / "system" / "wiki_signals.yaml"


def get_augur_state_dir() -> Path:
    """Return the per-user Augur state directory (`~/.augur/` by default).

    Honors AUGUR_STATE_DIR env override for tests.
    """
    override = _env_path("AUGUR_STATE_DIR")
    if override:
        return override
    return Path.home() / ".augur"


def get_brain_registry_path() -> Path:
    """Return the path to `brains.yaml` inside the Augur state directory."""
    return get_augur_state_dir() / "brains.yaml"


def get_project_brain_dir(project_root: Path | None = None) -> Path:
    """Return the repo-local project brain root for the given project root."""
    from src.lib.brain_manifest import project_brain_root_for

    root = project_root.resolve() if project_root is not None else get_project_root().resolve()
    return project_brain_root_for(root)


def get_project_brain_skills_dir(project_root: Path | None = None) -> Path:
    """Return the canonical repo-local project skill capability root."""
    return get_project_brain_dir(project_root) / "capabilities" / "skills"


def get_project_brain_agents_dir(project_root: Path | None = None) -> Path:
    """Return the canonical repo-local project agent capability root."""
    return get_project_brain_dir(project_root) / "capabilities" / "agents"


def get_project_brain_notes_dir(project_root: Path | None = None) -> Path:
    """Return the canonical repo-local project notes root."""
    return get_project_brain_dir(project_root) / "knowledge" / "notes"


def get_project_brain_sources_dir(project_root: Path | None = None) -> Path:
    """Return the canonical repo-local project sources root."""
    return get_project_brain_dir(project_root) / "knowledge" / "sources"


def get_project_brain_wiki_dir(project_root: Path | None = None) -> Path:
    """Return the canonical repo-local project wiki root."""
    return get_project_brain_dir(project_root) / "knowledge" / "wiki"


def get_project_brain_config_dir(project_root: Path | None = None) -> Path:
    """Return the canonical repo-local project config root."""
    return get_project_brain_dir(project_root) / "config"


_DEFAULT_PROJECT_BRAIN_MAPPED_SOURCES: dict[str, Path] = {
    "specs": Path("docs/superpowers/specs"),
    "plans": Path("docs/superpowers/plans"),
    "instructions/topics": Path("docs/agent-topics"),
    "capabilities/agents": Path("plugins/agents"),
    "workflows": Path("docs/agent-topics/WORKFLOWS.md"),
}


def get_project_brain_mapped_sources(project_root: Path | None = None) -> dict[str, Path]:
    """Return governed repo roots that are logically part of the project brain."""
    root = project_root.resolve() if project_root is not None else get_project_root().resolve()
    mappings = dict(_DEFAULT_PROJECT_BRAIN_MAPPED_SOURCES)
    config_path = get_project_brain_config_dir(root) / "mapped-sources.yaml"
    if config_path.is_file():
        try:
            data = _yaml_mod.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        configured = data.get("mapped_sources") if isinstance(data, dict) else None
        if isinstance(configured, dict):
            for logical_path, source_path in configured.items():
                if not isinstance(logical_path, str) or not isinstance(source_path, str):
                    continue
                mappings[logical_path.strip("/")] = Path(source_path)

    resolved: dict[str, Path] = {}
    for logical_path, source_path in mappings.items():
        expanded = Path(os.path.expanduser(str(source_path)))
        resolved[logical_path] = expanded if expanded.is_absolute() else root / expanded
    return resolved


def get_project_brain_mapped_source(
    logical_path: str,
    project_root: Path | None = None,
) -> Path:
    """Resolve one logical project-brain mapped source path."""
    key = logical_path.strip("/")
    sources = get_project_brain_mapped_sources(project_root)
    if key not in sources:
        raise KeyError(f"project-brain mapped source not found: {logical_path}")
    return sources[key]


def get_brain_dir(brain_id: str) -> Path:
    """Return the data_root for the given brain id.

    Raises KeyError if the brain is not registered.
    """
    from src.lib.brain_registry import get_registry

    registry = get_registry()
    brain = registry.get(brain_id)
    if brain is None:
        raise KeyError(f"brain not registered: {brain_id}")
    return brain.data_root


def list_brain_ids() -> list[str]:
    """Return all registered brain ids."""
    from src.lib.brain_registry import get_registry

    return get_registry().ids()


def get_active_brain_context(
    *,
    cwd: Path | None = None,
    brain_id: str | None = None,
    project: Path | None = None,
) -> ActiveBrainContext:
    """Return the active brain context for path-helper callers."""
    from src.lib.brain_context import resolve_active_context

    return resolve_active_context(
        cwd=cwd,
        explicit_brain=brain_id,
        explicit_project=project,
        registry_path=get_brain_registry_path(),
    )


def get_active_brain_stack(
    *,
    cwd: Path | None = None,
    brain_id: str | None = None,
    project: Path | None = None,
) -> BrainStack:
    """Return the ordered Global -> User -> Project brain stack for callers."""
    from src.lib.brain_stack import resolve_active_stack

    return resolve_active_stack(
        cwd=cwd,
        explicit_brain=brain_id,
        explicit_project=project,
        registry_path=get_brain_registry_path(),
    )


if __name__ == "__main__":
    from src.logging import get_entity_logger

    logger = get_entity_logger("paths")
    logger.info("Augur - Path Configuration")
    logger.info("=" * 60)
    logger.info("  Project Root:   %s", get_project_root())
    logger.info("  Vault:          %s", get_vault_dir())
    logger.info("  Documents:      %s", get_documents_dir())
    logger.info("  RAG:            %s", get_rag_dir())
    logger.info("  State:          %s", get_state_dir())
    logger.info("  Logs:           %s", get_logs_dir())
    logger.info("  Cache:          %s", get_cache_dir())
    logger.info("  LaunchAgents:   %s", get_launch_agents_dir())
    logger.info("  Memory:         %s", get_memory_dir())
    logger.info("  Skills:         %s", get_skills_dir())
    validate_paths()
    logger.info("✅ Path configuration is valid")
