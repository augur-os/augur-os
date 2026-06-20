"""
sync_agents/skill_sync.py

Per-skill sync logic for the sync_agents package.

Contains:
    - _resolve_client_skill_dirs(): Resolve client skill directories from CLIENT_FORMATS.
    - _SkillFileInfo / _missing: Dataclasses for skill file scanning.
    - _scan_all_skill_files(): Single-pass scan of all client skill dirs.
    - _build_synced_master_set(): Build set of synced master skill names.
    - restamp_unmarked_copies(): No-op post ADR-479.
    - cleanup_orphan_adapted_copies(): No-op post ADR-479.
    - auto_tag_master(): Persist inferred x-augur-master to SKILL.md.
    - _resolve_master_path(): Resolve a skill's master directory.
    - _sync_skill_stubs(): Sync managed SKILL.md files to all enabled client dirs.
"""

from __future__ import annotations

import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
# TODO_CLEANUP: This file is 892 lines — consider splitting into smaller modules

import json
import re
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import re as _re
import yaml as _yaml

from src.config.paths import (
    get_brain_registry_path,
    get_codex_native_skills_dir,
    get_codex_prompt_dir,
    get_managed_skill_source_dirs,
    get_project_root,
)
from src.lib.capabilities.export_filter import filter_named_sources

from .constants import (
    PROJECT_ROOT,
    CLAUDE_PLUGINS_CACHE,
    logger,
)
from .agent_parser import ADAPTED_COPY_MARKER
from .standard_skill_projection import iter_standard_skill_sources, _render_client_skill

_ADAPTED_MARKERS = (ADAPTED_COPY_MARKER, "AUGUR-STUB")
_ADAPTED_SOURCE_RE = _re.compile(r"AUGUR-ADAPTED-COPY\s+source=(\S+)")
_SKILL_SYNC_CONFIG_PATH = PROJECT_ROOT / "config" / "agents" / "ide_integrations.yaml"
_GENERATED_MARKER = "<!-- AUGUR-GENERATED -->"
_PROMPTS_MANIFEST = ".augur-generated-prompts.json"
_COMMANDS_MANIFEST = ".augur-generated-commands.json"


def _resolve_client_skill_dirs(repo_root: Path) -> list[tuple[str, Path, bool]]:
    """Resolve all client skill directories from CLIENT_FORMATS.

    Returns list of (client_id, resolved_path, has_subdirs) tuples.
    Handles both project-relative and home-relative paths.
    """
    try:
        from src.config.paths import get_client_skill_dirs
    except ImportError:
        get_client_skill_dirs = None

    path_map = get_client_skill_dirs() if get_client_skill_dirs else {
        "claude-local": repo_root / ".claude" / "skills",
        "claude-global": Path.home() / ".claude" / "skills",
        "codex-local": repo_root / ".codex" / "skills",
        "codex-global": Path.home() / ".codex" / "skills",
        "codex-global-superpowers": Path.home()
        / ".codex"
        / "superpowers"
        / "skills",
        "gemini-local": repo_root / ".antigravity" / "plugins",
        "gemini-global": Path.home() / ".antigravity" / "plugins",
        "cursor-local": repo_root / ".cursor" / "rules",
        "cursor-global": Path.home() / ".cursor" / "rules",
        "copilot-local": repo_root / ".github" / "instructions",
        "copilot-global": Path.home() / ".github" / "instructions",
        "opencode-local": repo_root / ".opencode" / "skills",
        "opencode-global": Path.home() / ".config" / "opencode" / "skills",
    }

    subdir_clients = {
        "claude-local", "claude-global",
        "codex-local", "codex-global", "codex-global-superpowers",
        "gemini-local", "gemini-global",
        "opencode-local", "opencode-global",
    }
    return [
        (source_tag, path, source_tag in subdir_clients)
        for source_tag, path in path_map.items()
    ]


def _render_codex_prompt(name: str, description: str, body: str) -> str:
    """Render a Codex prompt file with workflow-style frontmatter."""
    frontmatter = _yaml.safe_dump(
        {"name": name, "description": description},
        sort_keys=False,
        allow_unicode=True,
    ).strip()
    rendered = f"---\n{frontmatter}\n---\n{_GENERATED_MARKER}\n"
    if body:
        rendered += f"\n{body.rstrip()}\n"
    return rendered


def _strip_frontmatter(raw: str) -> str:
    return re.sub(r"^---\n.*?\n---\n*", "", raw, count=1, flags=re.DOTALL).strip()


def _load_yaml_frontmatter(raw: str) -> dict:
    if not raw.startswith("---"):
        return {}
    try:
        frontmatter_end = raw.index("---", 3)
        frontmatter = _yaml.safe_load(raw[3:frontmatter_end]) or {}
    except (ValueError, _yaml.YAMLError):
        return {}
    return frontmatter if isinstance(frontmatter, dict) else {}


def _render_native_skill_md(raw: str, fallback_name: str = "") -> str:
    """Render a clean native Claude Agent Skill SKILL.md from an Augur source.

    Strips all `x-augur-*` (and any other) frontmatter, keeping only the native
    contract — `name`, `description`, `allowed-tools` — plus the body. Used for
    every native-`SKILL.md` client target (ADR-805).
    """
    fm = _load_yaml_frontmatter(raw)
    name = str(fm.get("name") or fallback_name)
    description = str(fm.get("description") or "")
    allowed = fm.get("allowed-tools")
    if isinstance(allowed, str):
        allowed = [allowed]
    return _render_client_skill(
        name, description, _strip_frontmatter(raw), allowed_tools=allowed
    )


def _load_skill_sources(skills_dir: Path) -> list[tuple[str, Path, str, str, str, bool]]:
    """Load canonical skill exports from a managed ``*/SKILL.md`` root."""
    sources: list[tuple[str, Path, str, str, str, bool]] = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        raw = skill_md.read_text(encoding="utf-8")
        body = _strip_frontmatter(raw)
        description = ""
        frontmatter = _load_yaml_frontmatter(raw)
        if frontmatter:
            description = str(frontmatter.get("description") or "")
        if body:
            sources.append((name, skill_md.parent, raw, body, description, False))
    existing_names = {source[0] for source in sources}
    for source in iter_standard_skill_sources(skills_dir):
        if source[0] not in existing_names:
            sources.append(source)
            existing_names.add(source[0])
    return sources


def _managed_skill_root_layers(project_root: Path):
    from src.lib.brain_effective_skills import LogicalSkillRootLayer

    root = Path(project_root).resolve()
    try:
        live_root = get_project_root().resolve()
        has_project_brain_manifest = (root / "project-brain" / "BRAIN.yaml").is_file()
        if root == live_root or has_project_brain_manifest:
            from src.lib.brain_stack import resolve_active_stack

            stack = resolve_active_stack(cwd=root, registry_path=get_brain_registry_path())
            layers = []
            for brain in stack.ordered():
                skills_root = Path(brain.data_root) / "capabilities" / "skills"
                if skills_root.is_dir():
                    layers.append(
                        LogicalSkillRootLayer(
                            tier=brain.type.value,
                            brain_id=brain.id,
                            root=skills_root,
                        )
                    )
            if layers:
                return layers
    except Exception:
        logger.debug("Failed to resolve logical managed skill root layers", exc_info=True)

    return [
        LogicalSkillRootLayer(
            tier="managed",
            brain_id=f"managed-{index}",
            root=skills_root,
        )
        for index, skills_root in enumerate(get_managed_skill_source_dirs(project_root))
    ]


def _choose_managed_root_sources(
    project_root: Path,
    loader,
):
    from src.lib.brain_effective_skills import build_effective_skill_report

    report = build_effective_skill_report(
        _managed_skill_root_layers(project_root),
        loader,
        physical_roots=get_managed_skill_source_dirs(project_root),
        name_getter=lambda source: source[0],
        path_getter=lambda source: source[1],
    )
    return [choice.source for choice in report.choices]


def _load_managed_skill_sources(project_root: Path) -> list[tuple[str, Path, str, str, str, bool]]:
    return _choose_managed_root_sources(project_root, _load_skill_sources)


def _load_managed_command_sources(project_root: Path) -> list[tuple[str, Path, str]]:
    return _choose_managed_root_sources(project_root, _load_command_sources)


def _load_skill_command_metadata(skills_dir: Path) -> dict[tuple[str, str], str]:
    """Load command descriptions declared in skill frontmatter."""
    metadata: dict[tuple[str, str], str] = {}
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        raw = skill_md.read_text(encoding="utf-8")
        frontmatter = _load_yaml_frontmatter(raw)
        commands = frontmatter.get("x-augur-commands")
        if not isinstance(commands, list):
            continue
        skill_name = skill_md.parent.name
        for command in commands:
            if not isinstance(command, dict):
                continue
            command_id = str(command.get("id") or "").strip()
            description = str(command.get("description") or "").strip()
            if not command_id or not description:
                continue
            metadata[(skill_name, command_id)] = description
    return metadata


def _load_prompt_sources(skills_dir: Path) -> list[tuple[str, Path, str, str, str, bool]]:
    """Load prompt templates from command docs and legacy prompt seed files."""
    sources: list[tuple[str, Path, str, str, str, bool]] = []
    skill_command_metadata = _load_skill_command_metadata(skills_dir)

    for prompt_file in sorted(skills_dir.glob("*/prompts/*.md")):
        raw = prompt_file.read_text(encoding="utf-8")
        frontmatter = _load_yaml_frontmatter(raw)
        body = _strip_frontmatter(raw)
        if not body:
            continue
        prompt_id = str(frontmatter.get("id") or prompt_file.stem)
        description = str(frontmatter.get("description") or "").strip()
        if not description:
            description = f"Prompt template for {prompt_file.parent.parent.name}"
        sources.append(
            (
                prompt_id,
                prompt_file,
                raw,
                body,
                description,
                False,
            )
        )

    for prompt_file in sorted(skills_dir.glob("*/commands/*.md")):
        raw = prompt_file.read_text(encoding="utf-8")
        frontmatter = _load_yaml_frontmatter(raw)
        prompt_id = str(frontmatter.get("id") or prompt_file.stem)
        body = _strip_frontmatter(raw)
        description = str(frontmatter.get("description") or "").strip()
        skill_name = prompt_file.parent.parent.name
        if "skill" not in frontmatter:
            description = skill_command_metadata.get((skill_name, prompt_id), description)
        if not description:
            continue
        if body:
            sources.append(
                (
                    prompt_id,
                    prompt_file,
                    raw,
                    body,
                    description,
                    False,
                )
            )

    for prompt_file in sorted(skills_dir.glob("*/assets/seeds/prompts/*.md")):
        raw = prompt_file.read_text(encoding="utf-8")
        body = _strip_frontmatter(raw) if raw.startswith("---") else raw.strip()
        if not body:
            continue
        prompt_id = prompt_file.stem
        skill_name = prompt_file.parent.parent.parent.name
        sources.append(
            (
                prompt_id,
                prompt_file,
                raw,
                body,
                f"Prompt template for {skill_name}",
                False,
            )
        )

    return sources


def _load_command_sources(skills_dir: Path) -> list[tuple[str, Path, str]]:
    """Load explicit command docs from a managed ``*/commands/*.md`` root."""
    sources: list[tuple[str, Path, str]] = []
    for command_file in sorted(skills_dir.glob("*/commands/*.md")):
        raw = command_file.read_text(encoding="utf-8")
        frontmatter = _load_yaml_frontmatter(raw)
        if not _is_truthy_frontmatter(frontmatter.get("x-augur-export-command")):
            continue
        sources.append((command_file.stem, command_file, raw))
    return sources


def _render_command_skill(name: str, raw: str) -> str:
    """Render a command doc as a thin client-local skill wrapper."""
    frontmatter = _load_yaml_frontmatter(raw)
    body = _strip_frontmatter(raw)
    description = str(frontmatter.get("description") or "").strip()
    if not description:
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            description = stripped
            break
    if not description:
        description = f"Run /{name}"
    skill_frontmatter = _yaml.safe_dump(
        {"name": name, "description": description},
        sort_keys=False,
        allow_unicode=True,
    ).strip()
    rendered = f"---\n{skill_frontmatter}\n---\n"
    if body:
        rendered += f"\n{body.rstrip()}\n"
    return rendered


def _ensure_directory_root(target_dir: Path) -> None:
    """Ensure a directory root exists, replacing file/symlink placeholders."""
    if target_dir.is_symlink() or target_dir.is_file():
        target_dir.unlink()
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)


def _is_truthy_frontmatter(value: object) -> bool:
    """Parse common YAML truthy values used in SKILL.md frontmatter."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _load_manifest_entries(manifest_path: Path, key: str) -> set[str]:
    if not manifest_path.exists():
        return set()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        items = payload.get(key, [])
    except (OSError, json.JSONDecodeError):
        return set()
    entries: set[str] = set()
    for name in items:
        if not isinstance(name, str):
            continue
        path = Path(name)
        if not path.parts:
            continue
        if path.is_absolute() or ".." in path.parts:
            continue
        entries.add(name)
    return entries


def _generated_entry_name(entry: str) -> str:
    """Return the capability name represented by a managed manifest entry."""
    cleaned = str(entry or "").strip()
    if not cleaned:
        return ""
    first_part = cleaned.split("/", 1)[0]
    if first_part == cleaned:
        return Path(cleaned).stem
    return first_part


def _generated_entry_names(entries: Iterable[str]) -> set[str]:
    return {name for entry in entries if (name := _generated_entry_name(entry))}


def _save_manifest_entries(manifest_path: Path, key: str, entries: set[str]) -> None:
    manifest_path.write_text(
        json.dumps({key: sorted(entries)}, indent=2) + "\n",
        encoding="utf-8",
    )


def _clear_readonly(path: Path) -> None:
    """Clear the read-only bit so a generated file/dir can be deleted on Windows."""
    try:
        path.chmod(0o777 if path.is_dir() else 0o666)
    except OSError:
        pass


def _force_remove(path: Path) -> None:
    """Delete a generated file or directory tree, clearing the read-only bit first.

    ``write_generated_file`` writes generated outputs read-only (0o444); on Windows
    ``Path.unlink``/``shutil.rmtree`` raise ``PermissionError`` (WinError 5) on a
    read-only target, which previously aborted orphan pruning and stranded
    de-exported command files. Mirrors the clear-then-delete idiom in
    ``generators.py``.
    """
    if path.is_dir() and not path.is_symlink():
        for child in path.rglob("*"):
            _clear_readonly(child)
        _clear_readonly(path)
        shutil.rmtree(path)
        return
    try:
        path.unlink()
    except PermissionError:
        _clear_readonly(path)
        path.unlink()


def _reconcile_generated_orphans(
    target_dir: Path, manifest_path: Path, written: set[str]
) -> None:
    """Prune previously-generated entries no longer written, then persist the manifest.

    Orphan removal runs BEFORE the manifest is rewritten: if a removal fails, the
    manifest still names the un-removed files so the next run retries, instead of
    silently orphaning them (the failure mode that froze a stale slash-command
    surface). Read-only safe via :func:`_force_remove`.
    """
    old_files = _load_manifest_entries(manifest_path, "files")
    for orphan in old_files - written:
        orphan_path = target_dir / orphan
        if orphan_path.exists() or orphan_path.is_symlink():
            _force_remove(orphan_path)
    if written:
        _save_manifest_entries(manifest_path, "files", written)
    elif manifest_path.exists():
        _force_remove(manifest_path)


def _load_codex_native_manifest(export_dir: Path) -> set[str]:
    return _load_manifest_entries(export_dir / ".augur-managed.json", "skills")


def _save_codex_native_manifest(export_dir: Path, skills: set[str]) -> None:
    _save_manifest_entries(export_dir / ".augur-managed.json", "skills", skills)


def _sync_codex_native_skills(
    sources: list[tuple[str, Path, str, str, str, bool]],
    *,
    scope: str,
) -> int:
    """Copy eligible Augur skills into the Codex native discovery directory for a scope."""
    export_dir = get_codex_native_skills_dir(scope)
    if scope == "global" and (export_dir.is_symlink() or export_dir.is_file()):
        export_dir.unlink()
    _ensure_directory_root(export_dir)

    old_skills = _load_codex_native_manifest(export_dir)
    new_skills: set[str] = set()

    exported = 0
    for name, source_dir, _raw, _body, _description, codex_native in sources:
        if not codex_native:
            continue
        target_dir = export_dir / name
        if target_dir.is_symlink() or target_dir.is_file():
            target_dir.unlink()
        elif target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(source_dir, target_dir)
        new_skills.add(name)
        exported += 1

    for removed in old_skills - new_skills:
        target_dir = export_dir / removed
        if target_dir.is_symlink() or target_dir.is_file():
            target_dir.unlink()
        elif target_dir.is_dir():
            shutil.rmtree(target_dir)

    _save_codex_native_manifest(export_dir, new_skills)
    logger.info("Synced %s native Codex skills to %s", exported, export_dir)
    return exported


def _sync_codex_prompt_dir(
    cdir: Path,
    sources: list[tuple[str, Path, str, str, str, bool]],
    *,
    native_only: bool = False,
) -> int:
    """Write Codex prompt mirrors to a single prompt directory."""
    cdir.mkdir(parents=True, exist_ok=True)
    manifest_path = cdir / _PROMPTS_MANIFEST
    old_files = _load_manifest_entries(manifest_path, "files")

    written: list[str] = []
    for name, _source_path, _raw, body, description, codex_native in sources:
        if native_only and not codex_native:
            continue
        target_file = cdir / f"{name}.md"
        target_file.write_text(
            _render_codex_prompt(name, description, body),
            encoding="utf-8",
        )
        written.append(f"{name}.md")

    _save_manifest_entries(manifest_path, "files", set(written))

    for orphan in old_files - set(written):
        orphan_path = cdir / orphan
        if orphan_path.exists():
            orphan_path.unlink()

    if written:
        logger.info("Synced %s prompts to codex (%s)", len(written), cdir)
    return len(written)


def _source_tag_to_adapter_name(source_tag: str) -> str:
    if source_tag.startswith("claude-"):
        return "claude-code"
    if source_tag.startswith("codex-"):
        return "codex"
    if source_tag.endswith("-local") or source_tag.endswith("-global"):
        return source_tag.rsplit("-", 1)[0]
    return source_tag


def _adapter_name_aliases(adapter_name: str) -> set[str]:
    cleaned = str(adapter_name or "").strip()
    if not cleaned:
        return set()
    aliases = {cleaned}
    aliases.add(cleaned.replace("_", "-"))
    aliases.add(cleaned.replace("-", "_"))
    return aliases


def _enabled_adapter_ids(adapters: list) -> set[str]:
    enabled: set[str] = set()
    for adapter in adapters:
        enabled.update(_adapter_name_aliases(getattr(adapter, "adapter_name", "")))
    return enabled


def _source_tag_scope(source_tag: str) -> str:
    if source_tag.endswith("-local") or "-local-" in source_tag:
        return "project"
    if source_tag.endswith("-global") or "-global-" in source_tag:
        return "global"
    return "project"


def _load_skill_scopes() -> dict[str, str]:
    """Load per-adapter skill sync scope from ide_integrations.yaml.

    ADR-524 narrows managed skill export to repo-scoped targets by default.
    Global and both-scope values are ignored for normal sync.
    """
    if not _SKILL_SYNC_CONFIG_PATH.exists():
        return {}
    try:
        data = _yaml.safe_load(_SKILL_SYNC_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

    integrations = data.get("integrations", {})
    scopes: dict[str, str] = {}
    for adapter_name, config in integrations.items():
        if not isinstance(config, dict):
            continue
        scope = config.get("skill_scope")
        if scope == "project":
            scopes[adapter_name.replace("_", "-")] = scope
    return scopes


def _default_skill_scope(adapter_name: str) -> str:
    """Return the default sync scope for a client when config omits it."""
    return "project"


def _is_skill_projection_tag(source_tag: str) -> bool:
    return source_tag.endswith("-local") or source_tag.endswith("-global")


def _source_tag_to_projection_client(source_tag: str) -> str:
    if source_tag.startswith("claude-"):
        return "claude"
    if source_tag.startswith("codex-"):
        return "codex"
    if source_tag.endswith("-local") or source_tag.endswith("-global"):
        return source_tag.rsplit("-", 1)[0]
    return source_tag


def _projection_client_to_adapter_name(client: str) -> str:
    if client == "claude":
        return "claude-code"
    return client


def _skill_target_dir(
    name: str,
    client: str,
    client_dirs: dict[str, Path],
    home_skills: set[str],
    repo_skills: set[str],
) -> Path:
    """Choose the concrete client dir for one skill under the 3→2 collapse."""
    from src.lib.brain_home_sync import home_sync_enabled

    if home_sync_enabled() and name in home_skills:
        return client_dirs[f"{client}-global"]
    return client_dirs[f"{client}-local"]


def _skill_target_sets(
    sources: list[tuple[str, Path, str, str, str, bool]],
) -> tuple[set[str], set[str]]:
    """Return HOME/REPO skill-name sets, defaulting safely to REPO-only."""
    source_names = {str(source[0]) for source in sources}
    try:
        from src.lib.brain_home_sync import home_sync_enabled, partition_skills_by_target

        if not home_sync_enabled():
            return set(), source_names
        from src.config.paths import get_brain_registry_path
        from src.lib.brain_stack import resolve_active_stack

        stack = resolve_active_stack(
            cwd=PROJECT_ROOT,
            registry_path=get_brain_registry_path(),
        )
        home, repo = partition_skills_by_target(stack, project_root=PROJECT_ROOT)
    except Exception:
        return set(), source_names

    home &= source_names
    repo &= source_names
    repo |= source_names - home - repo
    return home, repo


def _cleanup_managed_skill_dir(cdir: Path, has_subdirs: bool) -> int:
    """Delete only Augur-managed skills from a client dir, preserving user content."""
    manifest_path = cdir / _PROMPTS_MANIFEST
    removed = 0

    if not cdir.exists():
        return 0

    managed_entries = _load_manifest_entries(manifest_path, "files")

    if managed_entries:
        for entry in managed_entries:
            target = cdir / entry
            if not target.exists():
                continue
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
                parent = target.parent
                if parent != cdir:
                    try:
                        parent.rmdir()
                    except OSError:
                        pass
            removed += 1
    else:
        # Fallback for older syncs without a manifest: remove only marker-tagged files.
        for entry in cdir.iterdir():
            if has_subdirs:
                skill_md = entry / "SKILL.md"
                if not entry.is_dir() or not skill_md.exists():
                    continue
                try:
                    header = skill_md.read_text(encoding="utf-8")[:2000]
                except (OSError, UnicodeDecodeError):
                    continue
                if "AUGUR-GENERATED" in header:
                    shutil.rmtree(entry)
                    removed += 1
            else:
                if not entry.is_file() or entry.name == manifest_path.name:
                    continue
                try:
                    header = entry.read_text(encoding="utf-8")[:2000]
                except (OSError, UnicodeDecodeError):
                    continue
                if "AUGUR-GENERATED" in header:
                    entry.unlink()
                    removed += 1

    if manifest_path.exists():
        manifest_path.unlink()
    return removed


def _cleanup_codex_native_skills(export_dir: Path) -> int:
    """Delete only Augur-managed Codex native exports, preserving user content."""
    manifest_path = export_dir / ".augur-managed.json"
    if export_dir.is_symlink() or export_dir.is_file():
        export_dir.unlink()
        return 1
    if not export_dir.exists():
        return 0

    removed = 0
    managed_entries = _load_manifest_entries(manifest_path, "skills")

    for entry in managed_entries:
        target = export_dir / entry
        if not target.exists():
            continue
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        removed += 1

    if manifest_path.exists():
        manifest_path.unlink()
    return removed


def _cleanup_generated_command_dir(cdir: Path) -> int:
    """Delete only Augur-managed command docs, preserving user content."""
    manifest_path = cdir / _COMMANDS_MANIFEST
    if not cdir.exists():
        return 0

    removed = 0
    managed_entries = _load_manifest_entries(manifest_path, "files")
    for entry in managed_entries:
        target = cdir / entry
        if not target.exists():
            continue
        if target.is_dir() and not target.is_symlink():
            _force_remove(target)
        else:
            _force_remove(target)
            parent = target.parent
            if parent != cdir:
                try:
                    parent.rmdir()
                except OSError:
                    pass
        removed += 1

    if manifest_path.exists():
        manifest_path.unlink()
    return removed


def _sync_command_skill_dir(
    cdir: Path,
    commands: list[tuple[str, Path, str]],
    *,
    write_generated_file,
) -> int:
    """Write exported command wrappers into a client skill directory."""
    _ensure_directory_root(cdir)
    manifest_path = cdir / _COMMANDS_MANIFEST
    written: set[str] = set()

    for name, source_path, raw in commands:
        target_dir = cdir / name
        if target_dir.is_symlink() or target_dir.is_file():
            target_dir.unlink()
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / "SKILL.md"
        try:
            source_ref = str(source_path.relative_to(PROJECT_ROOT))
        except ValueError:
            source_ref = str(source_path)
        write_generated_file(
            target_file,
            _render_command_skill(name, raw),
            source=source_ref,
        )
        written.add(name)

    _reconcile_generated_orphans(cdir, manifest_path, written)

    return len(written)


def _remove_skill_manifest_orphan(
    cdir: Path,
    orphan: str,
    *,
    command_entry_names: set[str] | None = None,
) -> None:
    """Remove a stale skill export unless another manifest still owns it."""
    if command_entry_names and _generated_entry_name(orphan) in command_entry_names:
        return

    orphan_path = cdir / orphan
    if not orphan_path.exists() and not orphan_path.is_symlink():
        return
    _force_remove(orphan_path)
    parent = orphan_path.parent
    if parent != cdir:
        try:
            parent.rmdir()
        except OSError:
            pass


def _cleanup_disabled_client_outputs(
    client_dirs: list[tuple[str, Path, bool]],
    enabled_ids: set[str],
) -> int:
    """Remove only Augur-managed outputs for disabled non-Codex adapters."""
    removed = 0
    for source_tag, target_dir, has_subdirs in client_dirs:
        adapter_name = _source_tag_to_adapter_name(source_tag)
        if adapter_name == "codex" or adapter_name in enabled_ids:
            continue
        removed += _cleanup_managed_skill_dir(target_dir, has_subdirs)
    return removed


# ---------------------------------------------------------------------------
# Single-pass skill sync: restamp + cleanup in one scan
# ---------------------------------------------------------------------------


@dataclass
class _SkillFileInfo:
    """Cached metadata for a single skill file discovered during scan."""

    name: str
    path: Path
    client_id: str
    has_subdirs: bool
    header: str
    is_adapted: bool
    source: str | None  # parsed from AUGUR-ADAPTED-COPY source=...
    is_synced_master: bool


class _missing:
    """Sentinel for unchecked sync status."""


def _scan_all_skill_files(
    repo_root: Path,
) -> tuple[list[tuple[str, Path, bool]], list[_SkillFileInfo]]:
    """Scan all client dirs once and return cached file info.

    Returns:
        (client_dirs, files) where files contains one entry per skill file
        with header, adapted status, and source already parsed.
    """
    client_dirs = _resolve_client_skill_dirs(repo_root)
    files: list[_SkillFileInfo] = []

    for cid, cdir, has_subdirs in client_dirs:
        if not cdir.exists():
            continue
        if has_subdirs:
            for d in cdir.iterdir():
                if not d.is_dir():
                    continue
                skill_md = d / "SKILL.md"
                if not skill_md.exists():
                    continue
                try:
                    header = skill_md.read_text(encoding="utf-8")[:2000]
                except (OSError, UnicodeDecodeError):
                    continue
                adapted = any(m in header for m in _ADAPTED_MARKERS)
                source = None
                if adapted:
                    sm = _ADAPTED_SOURCE_RE.search(header)
                    source = sm.group(1).rstrip(" ->") if sm else None
                files.append(_SkillFileInfo(
                    name=d.name, path=skill_md, client_id=cid,
                    has_subdirs=True, header=header,
                    is_adapted=adapted, source=source,
                    is_synced_master=False,  # filled below
                ))
        else:
            for f in cdir.iterdir():
                if not f.is_file() or f.suffix != ".md":
                    continue
                try:
                    header = f.read_text(encoding="utf-8")[:2000]
                except (OSError, UnicodeDecodeError):
                    continue
                adapted = any(m in header for m in _ADAPTED_MARKERS)
                source = None
                if adapted:
                    sm = _ADAPTED_SOURCE_RE.search(header)
                    source = sm.group(1).rstrip(" ->") if sm else None
                files.append(_SkillFileInfo(
                    name=f.stem, path=f, client_id=cid,
                    has_subdirs=False, header=header,
                    is_adapted=adapted, source=source,
                    is_synced_master=False,
                ))

    # Mark synced masters — native files (not adapted) with x-augur-sync: true
    for info in files:
        if info.is_adapted:
            continue
        try:
            text = info.path.read_text(encoding="utf-8")
            if text.startswith("---"):
                end = text.index("---", 3)
                fm = _yaml.safe_load(text[3:end])
                if isinstance(fm, dict) and fm.get("x-augur-sync"):
                    info.is_synced_master = True
        except Exception:
            pass

    return client_dirs, files


def _build_synced_master_set(
    files: list[_SkillFileInfo],
) -> set[str]:
    """Build set of skill names that have a synced master somewhere."""
    names: set[str] = set()
    for f in files:
        if f.is_synced_master:
            names.add(f.name)
    # Plugin cache skills are always considered synced
    if CLAUDE_PLUGINS_CACHE.exists():
        for d in CLAUDE_PLUGINS_CACHE.iterdir():
            if d.is_dir():
                names.add(d.name)
    return names


def restamp_unmarked_copies(repo_root: Path) -> list[str]:
    """No-op after ADR-479 skill migration.

    Post-migration, managed skill roots are the source and _sync_skill_stubs
    copies to all clients. The master/adapted-copy model is retired.

    Returns:
        Empty list (no re-stamping needed).
    """
    return []


def cleanup_orphan_adapted_copies(repo_root: Path) -> list[str]:
    """No-op after ADR-479 skill migration.

    Post-migration, _sync_skill_stubs handles orphan cleanup per-client
    via manifests. The master/adapted-copy model is retired.
    """
    return []


def auto_tag_master(skill_md_path: Path, inferred_master: str) -> bool:
    """Persist inferred x-augur-master to SKILL.md if not already set.

    If the skill's path is inside CLAUDE_PLUGINS_CACHE, infers ``claude-code``
    as the master regardless of the caller-supplied value.

    Uses frontmatter_utils to read/write YAML frontmatter. Returns True
    if the tag was written, False if already present or on error.
    """
    try:
        from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter
    except ImportError:
        return False
    # Override inferred master for plugin cache skills
    try:
        skill_md_path.resolve().relative_to(CLAUDE_PLUGINS_CACHE.resolve())
        inferred_master = "claude-code"
    except ValueError:
        pass  # Not inside plugin cache — keep caller-supplied value
    fm, body = parse_frontmatter(skill_md_path)
    if fm.get("x-augur-master"):
        return False
    fm["x-augur-master"] = inferred_master
    write_frontmatter(skill_md_path, fm, body)
    return True


def _resolve_master_path(skill) -> Path | None:
    """Resolve a skill's master directory from its x-augur-master value.

    All skills are now in client dirs. For any master value, looks in the
    corresponding client's skill directory.

    Args:
        skill: Object with .master and .id attributes.

    Returns:
        Path to the master directory, or None if not found.
    """
    # Legacy augur-mastered skills should have been migrated to a client dir.
    # Fall through to client dir lookup with claude-code as the default.
    master = skill.master
    if master == "augur":
        master = "claude-code"
    for cid, cdir, has_subdirs in _resolve_client_skill_dirs(PROJECT_ROOT):
        if cid != master:
            continue
        path = cdir / skill.id if has_subdirs else cdir
        return path if path.exists() else None
    return None


def _sync_skill_stubs(adapters: list, *, cleanup_disabled: bool = True) -> int:
    """Sync canonical skill exports from managed skill roots across enabled clients."""
    managed_sources = _load_managed_skill_sources(PROJECT_ROOT)
    return _sync_skill_exports(
        adapters,
        managed_sources,
        cleanup_disabled=cleanup_disabled,
    )


def _sync_skill_exports(
    adapters: list,
    sources: list[tuple[str, Path, str, str, str, bool]],
    *,
    include_client_skills: bool = True,
    cleanup_disabled: bool = True,
) -> int:
    """Sync skill-derived exports across enabled clients."""

    client_dirs = _resolve_client_skill_dirs(PROJECT_ROOT)
    enabled_ids = _enabled_adapter_ids(adapters)
    skill_scopes = _load_skill_scopes()
    client_dir_map = {
        cid: cdir for cid, cdir, _has_subdirs in client_dirs if _is_skill_projection_tag(cid)
    }
    client_has_subdirs = {
        cid: has_subdirs
        for cid, _cdir, has_subdirs in client_dirs
        if _is_skill_projection_tag(cid)
    }
    projection_clients = sorted(
        {
            _source_tag_to_projection_client(cid)
            for cid in client_dir_map
            if f"{_source_tag_to_projection_client(cid)}-local" in client_dir_map
        }
    )
    home_skills, repo_skills = _skill_target_sets(sources)
    total = 0
    if cleanup_disabled:
        disabled_cleanup_count = _cleanup_disabled_client_outputs(client_dirs, enabled_ids)
        if disabled_cleanup_count:
            logger.info(
                "Removed %s Augur-managed exports for disabled adapters",
                disabled_cleanup_count,
            )

    for client in projection_clients:
        adapter_name = _projection_client_to_adapter_name(client)
        if not include_client_skills:
            continue
        if adapter_name not in enabled_ids:
            continue
        configured_scope = skill_scopes.get(adapter_name, _default_skill_scope(adapter_name))
        target_sources: dict[str, list[tuple[str, Path, str, str, str, bool]]] = {
            f"{client}-local": [],
            f"{client}-global": [],
        }

        for source in sources:
            name = str(source[0])
            try:
                target_dir = _skill_target_dir(
                    name,
                    client,
                    client_dir_map,
                    home_skills,
                    repo_skills,
                )
            except KeyError:
                continue
            target_tag = next(
                tag
                for tag, path in client_dir_map.items()
                if tag.startswith(f"{client}-") and path == target_dir
            )
            target_sources.setdefault(target_tag, []).append(source)

        for cid in (f"{client}-local", f"{client}-global"):
            cdir = client_dir_map.get(cid)
            if cdir is None:
                continue
            has_subdirs = client_has_subdirs[cid]
            source_scope = _source_tag_scope(cid)
            from src.lib.brain_home_sync import home_sync_enabled

            if (
                not home_sync_enabled()
                and configured_scope != "both"
                and source_scope != configured_scope
            ):
                removed = _cleanup_managed_skill_dir(cdir, has_subdirs)
                if removed:
                    logger.info(
                        "Removed %s Augur-managed skills from %s (%s) due to skill_scope=%s",
                        removed,
                        cid,
                        cdir,
                        configured_scope,
                    )
                continue

            client_sources = target_sources.get(cid, [])
            if not client_sources and not cdir.exists():
                continue

            cdir.mkdir(parents=True, exist_ok=True)
            manifest_path = cdir / _PROMPTS_MANIFEST
            old_files = _load_manifest_entries(manifest_path, "files")
            existing_names = _generated_entry_names(old_files)
            client_sources = list(
                filter_named_sources(
                    "skill",
                    client_sources,
                    target=adapter_name,
                    existing_names=existing_names,
                )
            )

            written: list[str] = []
            for name, _source_dir, raw, body, _description, _codex_native in client_sources:
                if has_subdirs:
                    target_dir = cdir / name
                    target_file = target_dir / "SKILL.md"
                    entry_name = f"{name}/SKILL.md"
                    if entry_name not in old_files and target_file.exists():
                        continue
                    target_dir.mkdir(parents=True, exist_ok=True)
                    if target_file.exists():
                        target_file.unlink()
                    # ADR-805: project a clean native SKILL.md (x-augur-* stripped)
                    # to every native-SKILL.md client (claude/codex/gemini/opencode).
                    target_file.write_text(
                        _render_native_skill_md(raw, name), encoding="utf-8"
                    )
                    written.append(entry_name)
                else:
                    target_file = cdir / f"{name}.md"
                    entry_name = f"{name}.md"
                    if entry_name not in old_files and target_file.exists():
                        continue
                    if target_file.exists():
                        target_file.unlink()
                    target_file.write_text(body + "\n", encoding="utf-8")
                    written.append(entry_name)

            if written:
                _save_manifest_entries(manifest_path, "files", set(written))
            elif manifest_path.exists():
                manifest_path.unlink()

            command_entry_names = _generated_entry_names(
                _load_manifest_entries(cdir / _COMMANDS_MANIFEST, "files")
            )
            for orphan in old_files - set(written):
                _remove_skill_manifest_orphan(
                    cdir,
                    orphan,
                    command_entry_names=command_entry_names,
                )

            total += len(written)
            if written:
                logger.info(f"Synced {len(written)} skills to {cid} ({cdir})")

    if "codex" in enabled_ids and "codex" not in projection_clients:
        for scope in ("project", "global"):
            prompt_dir = get_codex_prompt_dir(scope)
            removed = _cleanup_managed_skill_dir(prompt_dir, has_subdirs=False)
            if removed:
                logger.info(
                    "Removed %s Augur-managed prompts from %s due to legacy Codex cleanup",
                    removed,
                    prompt_dir,
                )
            native_dir = get_codex_native_skills_dir(scope)
            removed = _cleanup_codex_native_skills(native_dir)
            if removed:
                logger.info(
                    "Removed %s Augur-managed native exports from %s due to legacy Codex cleanup",
                    removed,
                    native_dir,
                )
    else:
        if cleanup_disabled:
            for scope in ("project", "global"):
                prompt_dir = get_codex_prompt_dir(scope)
                removed = _cleanup_managed_skill_dir(prompt_dir, has_subdirs=False)
                if removed:
                    logger.info(
                        "Removed %s Augur-managed prompts from %s because Codex is disabled",
                        removed,
                        prompt_dir,
                    )

                native_dir = get_codex_native_skills_dir(scope)
                removed = _cleanup_codex_native_skills(native_dir)
                if removed:
                    logger.info(
                        "Removed %s Augur-managed native exports from %s because Codex is disabled",
                        removed,
                        native_dir,
                    )

    return total


def _sync_prompt_stubs(adapters: list, *, cleanup_disabled: bool = True) -> int:
    """Clean Codex prompt legacy surfaces; no prompt export writes remain."""
    if not cleanup_disabled:
        return 0
    for scope in ("project", "global"):
        prompt_dir = get_codex_prompt_dir(scope)
        removed = _cleanup_managed_skill_dir(prompt_dir, has_subdirs=False)
        if removed:
            logger.info(
                "Removed %s Augur-managed prompts from %s due to legacy Codex cleanup",
                removed,
                prompt_dir,
            )

    return 0


def _sync_command_stubs(adapters: list, *, cleanup_disabled: bool = True) -> int:
    """Sync explicit command docs to client command surfaces."""
    commands = _load_managed_command_sources(PROJECT_ROOT)

    from .generators import write_generated_file

    enabled_ids = _enabled_adapter_ids(adapters)
    total = 0

    claude_commands_dir = PROJECT_ROOT / ".claude" / "commands"
    manifest_path = claude_commands_dir / _COMMANDS_MANIFEST

    if "claude_code" in enabled_ids:
        claude_commands_dir.mkdir(parents=True, exist_ok=True)
        old_files = _load_manifest_entries(manifest_path, "files")
        existing_names = _generated_entry_names(old_files)
        claude_commands = filter_named_sources(
            "command",
            commands,
            target="claude_code",
            existing_names=existing_names,
        )
        written: set[str] = set()

        for name, source_path, raw in claude_commands:
            target_file = claude_commands_dir / f"{name}.md"
            try:
                source_ref = str(source_path.relative_to(PROJECT_ROOT))
            except ValueError:
                source_ref = str(source_path)
            write_generated_file(
                target_file, _render_command_skill(name, raw), source=source_ref
            )
            written.add(target_file.name)
            total += 1

        _reconcile_generated_orphans(claude_commands_dir, manifest_path, written)

        if written:
            logger.info(
                "Synced %s command docs to %s", len(written), claude_commands_dir
            )
    elif cleanup_disabled:
        removed = _cleanup_generated_command_dir(claude_commands_dir)
        if removed:
            logger.info(
                "Removed %s Augur-managed command docs from %s because Claude Code is disabled",
                removed,
                claude_commands_dir,
            )

    for adapter_name, client_dir in (
        ("codex", PROJECT_ROOT / ".codex" / "skills"),
        ("gemini", PROJECT_ROOT / ".antigravity" / "plugins"),
    ):
        if adapter_name in enabled_ids:
            existing_names = _generated_entry_names(
                _load_manifest_entries(
                    client_dir / _COMMANDS_MANIFEST,
                    "files",
                )
            )
            client_commands = filter_named_sources(
                "command",
                commands,
                target=adapter_name,
                existing_names=existing_names,
            )
            written = _sync_command_skill_dir(
                client_dir,
                client_commands,
                write_generated_file=write_generated_file,
            )
            total += written
            if written:
                logger.info(
                    "Synced %s command skill wrappers to %s (%s)",
                    written,
                    adapter_name,
                    client_dir,
                )
            continue
        if cleanup_disabled:
            removed = _cleanup_generated_command_dir(client_dir)
            if removed:
                logger.info(
                    "Removed %s Augur-managed command wrappers from %s because %s is disabled",
                    removed,
                    client_dir,
                    adapter_name,
                )
    return total


def detect_command_stub_drift(adapters: list) -> list[str]:
    """Return drift descriptions for command-stub exports across enabled clients.

    Flags two conditions check mode previously missed:
    - Commands the capability policy approves for export to a client surface
      that have no on-disk file (e.g. a newly classified policy entry).
    - On-disk files for commands no longer approved (orphans).

    Content drift on existing files is corrected silently at sync time and is
    not flagged here.
    """
    drift: list[str] = []
    commands = _load_managed_command_sources(PROJECT_ROOT)
    enabled_ids = _enabled_adapter_ids(adapters)

    if "claude_code" in enabled_ids:
        claude_dir = PROJECT_ROOT / ".claude" / "commands"
        manifest_entries = _load_manifest_entries(
            claude_dir / _COMMANDS_MANIFEST, "files"
        )
        existing_names = _generated_entry_names(manifest_entries)
        allowed = filter_named_sources(
            "command",
            commands,
            target="claude_code",
            existing_names=existing_names,
        )
        expected = {f"{name}.md" for name, _, _ in allowed}
        for fname in sorted(expected):
            if not (claude_dir / fname).exists():
                drift.append(f".claude/commands/{fname} (missing)")
        for orphan in sorted(manifest_entries - expected):
            if (claude_dir / orphan).exists():
                drift.append(f".claude/commands/{orphan} (orphan)")

    for adapter_name, client_dir in (
        ("codex", PROJECT_ROOT / ".codex" / "skills"),
        ("gemini", PROJECT_ROOT / ".antigravity" / "plugins"),
    ):
        if adapter_name not in enabled_ids:
            continue
        manifest_entries = _load_manifest_entries(
            client_dir / _COMMANDS_MANIFEST, "files"
        )
        existing_names = _generated_entry_names(manifest_entries)
        allowed = filter_named_sources(
            "command",
            commands,
            target=adapter_name,
            existing_names=existing_names,
        )
        expected = {name for name, _, _ in allowed}
        for name in sorted(expected):
            if not (client_dir / name / "SKILL.md").exists():
                drift.append(
                    f".{adapter_name}/skills/{name}/SKILL.md (missing)"
                )
        for orphan in sorted(manifest_entries - expected):
            if (client_dir / orphan).exists():
                drift.append(f".{adapter_name}/skills/{orphan}/ (orphan)")

    return drift


def detect_skill_stub_drift(adapters: list) -> list[str]:
    """Return drift descriptions for skill-stub exports across enabled clients.

    Mirrors ``detect_command_stub_drift`` for the skill surface (ADR-734 C3).
    Flags:
    - Skills the capability policy approves for export to a client surface
      that have no on-disk SKILL.md (newly classified policy entry not synced).
    - On-disk SKILL.md files for skills no longer approved (orphans).

    Codex skills are tracked via the native ``.augur-managed.json`` manifest
    rather than ``.augur-generated-prompts.json``; checked separately if needed.
    Content drift on existing files is corrected silently at sync time and is
    not flagged here.
    """
    drift: list[str] = []
    enabled_ids = _enabled_adapter_ids(adapters)
    skill_sources = _load_managed_skill_sources(PROJECT_ROOT)
    skill_names = [name for name, *_ in skill_sources]

    for adapter_name, client_dir in (
        ("claude_code", PROJECT_ROOT / ".claude" / "skills"),
        ("gemini", PROJECT_ROOT / ".antigravity" / "plugins"),
        ("opencode", PROJECT_ROOT / ".opencode" / "skills"),
    ):
        if adapter_name not in enabled_ids:
            continue
        target = "claude_code" if adapter_name == "claude_code" else adapter_name
        manifest_path = client_dir / _PROMPTS_MANIFEST
        manifest_entries = _load_manifest_entries(manifest_path, "files")
        existing_names = _generated_entry_names(manifest_entries)
        allowed = filter_named_sources(
            "skill",
            [(name,) for name in skill_names],
            target=target,
            existing_names=existing_names,
        )
        expected = {name for (name,) in allowed}
        client_label = ".claude" if adapter_name == "claude_code" else f".{adapter_name}"
        for name in sorted(expected):
            if not (client_dir / name / "SKILL.md").exists():
                drift.append(f"{client_label}/skills/{name}/SKILL.md (missing)")
        for orphan in sorted(manifest_entries):
            if _generated_entry_name(orphan) in expected:
                continue
            orphan_path = client_dir / orphan
            if orphan_path.exists():
                drift.append(f"{client_label}/skills/{orphan} (orphan)")

    return drift
