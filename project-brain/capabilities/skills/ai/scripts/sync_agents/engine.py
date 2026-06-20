"""
sync_agents/engine.py

Core sync orchestration engine for the sync_agents package.

ADR-186: Extracted from monolithic sync_agents.py.

Contains:
    - Adapter helpers: _get_all_adapters, _load_ide_integrations, _is_adapter_enabled
    - _get_enabled_rule_targets(): Rule target resolution per enabled adapters.
    - sync_all(): Main orchestration logic (extracted from main()).

Delegates to submodules:
    - generators.py: write_generated_file, clean_directory, generate_ide_manifest
    - vault.py: _feed_memory_review_queue, sync_vaults
    - modes.py: check_mode, validate_mode, fix_mode
    - skill_sync.py: per-skill sync dataclasses, helpers, and _sync_skill_stubs
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
import shutil
from pathlib import Path

from .constants import (
    PROJECT_ROOT,
    SOURCE_RULES,
    SOURCE_WORKFLOWS,
    CLAUDE_PLUGINS_CACHE,
    ASSEMBLED_PLUGINS_PATH,
    GENERATED_FILES,
    logger,
)

# Re-export from submodules so existing importers continue to work.
# discovery.py lazy-imports write_generated_file and _is_adapter_enabled from
# .engine, so these re-exports are load-bearing.
from .generators import write_generated_file, clean_directory, generate_ide_manifest  # noqa: F401
from .modes import check_mode, validate_mode, fix_mode, clean_mode, clean_hygiene_mode, purge_mode  # noqa: F401
from .vault import sync_vaults  # noqa: F401
from .skill_sync import (  # noqa: F401
    _resolve_client_skill_dirs,
    _SkillFileInfo,
    _missing,
    _scan_all_skill_files,
    _build_synced_master_set,
    restamp_unmarked_copies,
    cleanup_orphan_adapted_copies,
    auto_tag_master,
    _resolve_master_path,
    _sync_skill_stubs,
    _sync_prompt_stubs,
    _sync_command_stubs,
)

from .templates import resolve_placeholders  # noqa: F401
from .discovery import (
    discover_claude_plugins,
    assemble_claude_plugins,
    resolve_overlaps,
    distribute_imported_agents,
)

IDE_INTEGRATIONS_PATH = PROJECT_ROOT / "config" / "agents" / "ide_integrations.yaml"

# ── Dispatch Target Group Gating (Task 7) ──────────────────────────────
# Maps adapter_name → dispatch group name (from cli_agents.yaml).
# Adapters not in this map (e.g. CoworkAdapter, CodexPluginAdapter) always sync.
_ADAPTER_TO_GROUP: dict[str, str] = {
    "claude_code": "claude",
    "claude_desktop": "claude",
    "codex": "codex",
    "cursor": "cursor",
    "gemini": "gemini",
    "gemini_plugin": "gemini",
    "opencode": "opencode",
    "kimi": "kimi",
    "copilot": "copilot",
    "copilot_plugin": "copilot",
    "windsurf": "windsurf",
    "cline": "cline",
    "antigravity": "antigravity",
}

_LEGACY_UNSUPPORTED_EXPORTS: tuple[Path, ...] = (
    PROJECT_ROOT / ".codebuddy",
    PROJECT_ROOT / ".continue",
)


def _load_enabled_groups() -> set[str] | None:
    """Load enabled dispatch groups from user preferences.

    Returns None when all groups are enabled (first-run default or prefs
    unreadable).  Returns a set of group name strings when the user has
    explicitly configured which groups are active.
    """
    try:
        # Prefer the canonical config path used by the MCP preferences module.
        prefs_path = PROJECT_ROOT / "config" / "preferences.yaml"
        if not prefs_path.exists():
            # Fallback: runtime config via src.config.paths
            try:
                from src.config.paths import get_runtime_dir
                prefs_path = Path(get_runtime_dir()).parent / "config" / "preferences.yaml"
            except Exception:
                pass
        if not prefs_path.exists():
            import os
            home = os.environ.get("HOME", "")
            prefs_path = Path(home) / ".augur" / "config" / "preferences.yaml"
        if not prefs_path.exists():
            return None

        import yaml
        with open(prefs_path, encoding="utf-8") as f:
            prefs = yaml.safe_load(f) or {}

        dt = prefs.get("dispatch_targets", {})
        groups = dt.get("enabled_groups")
        return set(groups) if groups is not None else None
    except Exception:
        return None


def _cleanup_legacy_unsupported_exports() -> list[Path]:
    """Remove stale legacy client export directories no longer managed by adapters."""
    removed: list[Path] = []
    for path in _LEGACY_UNSUPPORTED_EXPORTS:
        if not path.exists():
            continue
        try:
            shutil.rmtree(path)
            removed.append(path)
            logger.info("🧹 Removed legacy unsupported export: %s", path.relative_to(PROJECT_ROOT))
        except OSError as e:
            logger.warning("Failed to remove legacy unsupported export %s: %s", path, e)
    return removed


_RULE_TARGETS_BY_ADAPTER: dict[str, list[Path]] = {
    "claude_code": [PROJECT_ROOT / "CLAUDE.md"],
    "claude_desktop": [PROJECT_ROOT / "CLAUDE.md"],
    "kimi": [PROJECT_ROOT / "AGENTS.md"],
    "codex": [PROJECT_ROOT / "CODEX.md", PROJECT_ROOT / "AGENTS.md"],
    "cursor": [PROJECT_ROOT / ".cursorrules"],
    "gemini": [PROJECT_ROOT / ".antigravity" / "ANTIGRAVITY.md"],
    "windsurf": [PROJECT_ROOT / ".windsurfrules"],
    "copilot": [PROJECT_ROOT / ".github" / "copilot-instructions.md"],
    "opencode": [PROJECT_ROOT / ".opencode" / "AGENTS.md"],
    "antigravity": [PROJECT_ROOT / ".antigravity" / "instructions.md"],
}


def _normalize_client_filter(client_name: str) -> str:
    return client_name.strip().lower().replace("-", "_")


def _is_adapter_active(
    adapter,
    config: dict,
    enabled_groups: set[str] | None,
    selected_clients: set[str] | None = None,
) -> bool:
    adapter_name = getattr(adapter, "adapter_name", "")
    if selected_clients is not None and adapter_name not in selected_clients:
        return False
    if adapter_name and not _is_adapter_enabled(adapter_name, config):
        return False
    adapter_group = _ADAPTER_TO_GROUP.get(adapter_name)
    if adapter_group and enabled_groups is not None and adapter_group not in enabled_groups:
        return False
    return True


def _get_active_managed_paths(
    adapters: list,
    config: dict,
    enabled_groups: set[str] | None,
    selected_clients: set[str] | None = None,
) -> set[Path]:
    managed_paths: set[Path] = set()
    for adapter in adapters:
        if not _is_adapter_active(adapter, config, enabled_groups, selected_clients):
            continue
        for path_str in adapter.get_managed_files():
            path = Path(path_str)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            try:
                managed_paths.add(path.resolve())
            except OSError:
                managed_paths.add(path)
    return managed_paths


def _get_all_adapters():
    """Lazily import and instantiate all adapters."""
    from .adapters.claude_code import ClaudeCodeAdapter
    from .adapters.claude_desktop import ClaudeDesktopAdapter
    from .adapters.cline import ClineAdapter
    from .adapters.cursor import CursorAdapter
    from .adapters.windsurf import WindsurfAdapter
    from .adapters.copilot import CopilotAdapter
    from .adapters.gemini import GeminiAdapter
    from .adapters.gemini_plugin import GeminiPluginAdapter
    from .adapters.opencode import OpenCodeAdapter
    from .adapters.kimi import KimiAdapter
    from .adapters.antigravity import AntigravityAdapter
    from .adapters.codex import CodexAdapter
    from .adapters.cowork import CoworkAdapter
    from .adapters.codex_plugin import CodexPluginAdapter
    from .adapters.copilot_plugin import CopilotPluginAdapter

    return [
        ClaudeCodeAdapter(),
        ClaudeDesktopAdapter(),
        ClineAdapter(),
        CursorAdapter(),
        WindsurfAdapter(),
        CopilotAdapter(),
        GeminiAdapter(),
        GeminiPluginAdapter(),
        OpenCodeAdapter(),
        KimiAdapter(),
        AntigravityAdapter(),
        CodexAdapter(),
        CoworkAdapter(),
        CodexPluginAdapter(),
        CopilotPluginAdapter(),
    ]


def _get_enabled_rule_targets(config: dict, enabled_groups: set[str] | None = None) -> list[Path]:
    """Return rule targets required for currently enabled adapters."""
    targets: list[Path] = []
    seen: set[str] = set()
    for adapter_name, adapter_targets in _RULE_TARGETS_BY_ADAPTER.items():
        if not _is_adapter_enabled(adapter_name, config):
            continue
        adapter_group = _ADAPTER_TO_GROUP.get(adapter_name)
        if adapter_group and enabled_groups is not None and adapter_group not in enabled_groups:
            continue
        for target in adapter_targets:
            key = str(target.resolve())
            if key in seen:
                continue
            seen.add(key)
            targets.append(target)
    return targets


def _load_ide_integrations(
    project_root: Path | None = None,
) -> dict:
    """Load IDE integration config from YAML.

    Args:
        project_root: Optional root to resolve config from. Defaults to
            the package PROJECT_ROOT.
    """
    root = project_root or PROJECT_ROOT
    integrations_path = root / "config" / "agents" / "ide_integrations.yaml"

    try:
        import yaml as pyyaml
    except ImportError:
        return {"integrations": {}}
    if not integrations_path.exists():
        return {"integrations": {}}
    try:
        with open(integrations_path, encoding="utf-8") as f:
            data = pyyaml.safe_load(f) or {}
        return data if "integrations" in data else {"integrations": {}}
    except Exception as e:
        logger.warning(f"Failed to load ide_integrations.yaml: {e}")
        return {"integrations": {}}


def _is_adapter_enabled(adapter_name: str, config: dict) -> bool:
    """Check if an adapter is enabled in the integration config.

    Defaults to True if the adapter isn't listed or has no enabled key.
    """
    integrations = config.get("integrations", {})
    entry = integrations.get(adapter_name, {})
    return entry.get("enabled", True)


def _ensure_brain_mounts() -> list[str]:
    """Ensure root BRAIN.yaml exists in every registered brain root."""
    from src.lib.brain_mount import ensure_mount
    from src.lib.brain_registry import get_registry

    registry = get_registry()
    written: list[str] = []
    for brain_id in registry.ids():
        brain = registry.get(brain_id)
        if brain is None:
            continue
        # brain.data_root may be a PurePosixPath (Stage 1 registries can carry
        # roots that live on another machine). Wrap in Path so `.is_dir()` works
        # and resolves to False for remote/non-existent roots instead of raising.
        if not Path(brain.data_root).is_dir():
            # Stage 1 registries may include roots that live on another machine.
            continue
        ensure_mount(brain)
        written.append(brain_id)
    return written


def sync_all(
    do_rules: bool = True,
    do_subagents: bool = True,
    do_memory: bool = True,
    do_plugins: bool = True,
    do_mcp_config: bool = True,
    do_vaults: bool = True,
    do_skill_exports: bool = True,
    do_prompt_exports: bool = True,
    do_command_exports: bool = True,
    selected_clients: set[str] | None = None,
) -> int:
    """Main orchestration logic for syncing all agent files.

    Extracted from main() so it can be called programmatically from __init__.py
    or other entry points without going through argparse.

    Args:
        do_rules: Sync global rules to all IDE/CLI configs.
        do_subagents: Sync subagent profiles.
        do_memory: Sync canonical memory to all agent-specific locations.
        do_plugins: Run Phase 3 bidirectional plugin sync (ADR-171).
        do_mcp_config: Generate resolved MCP config for all adapters.
        do_vaults: Run bidirectional vault adapter sync.
        do_skill_exports: Sync skill bundle exports.
        do_prompt_exports: Sync prompt mirror exports.
        do_command_exports: Sync command docs exports.
        selected_clients: Optional set of normalized adapter names to target.

    Returns:
        0 on success, 1 on critical failure.
    """
    from .vault import _feed_memory_review_queue, sync_vaults as _sync_vaults

    effective_plugins = do_plugins and selected_clients is None
    logger.info(
        f"Starting Sync Agents (Rules={do_rules}, "
        f"Subagents={do_subagents}, Plugins={effective_plugins})"
    )
    logger.info(f"Project Root: {PROJECT_ROOT}")

    # 1. Read Source Rules
    if not SOURCE_RULES.exists():
        logger.error(f"CRITICAL: Rules source not found at {SOURCE_RULES}")
        return 1

    try:
        rules_content = SOURCE_RULES.read_text(encoding="utf-8")
    except OSError as e:
        logger.error(f"Failed to read rules: {e}")
        return 1

    # 2. Read Source Workflows (optional legacy fallback)
    if not SOURCE_WORKFLOWS.exists():
        logger.debug(
            "Legacy workflows source not found at %s; using distributed command "
            "registry only",
            SOURCE_WORKFLOWS,
        )

    # 3. Initialize Adapters
    adapters = _get_all_adapters()

    # Load integration config for enabled gating (ADR-219)
    ide_config = _load_ide_integrations()

    # Load dispatch target groups for group-level gating (Task 7)
    enabled_groups = _load_enabled_groups()
    active_managed_paths = _get_active_managed_paths(
        adapters,
        ide_config,
        enabled_groups,
        selected_clients,
    )

    # 3b. Surface client memory as review candidates before per-adapter sync_memory.
    # ADR-772: no auto-promotion of raw client memory — review-gated promotion only.
    if do_memory:
        _feed_memory_review_queue()

    # 3c. Vault adapter sync (ADR-436)
    if do_vaults:
        _sync_vaults()

    _cleanup_legacy_unsupported_exports()

    enabled_sync_adapters = []

    # 4. Execute Sync
    for adapter in adapters:
        name = adapter.__class__.__name__
        if selected_clients is not None and getattr(adapter, "adapter_name", "") not in selected_clients:
            logger.info("⏭️  Skipping adapter %s (not selected)", name)
            continue
        # Gate on enabled flag (ADR-219)
        if hasattr(adapter, 'adapter_name') and adapter.adapter_name:
            if not _is_adapter_enabled(adapter.adapter_name, ide_config):
                logger.info(f"⏭️  Skipping disabled adapter: {name}")
                # Clean up managed files for disabled adapters (ADR-219)
                try:
                    deleted = adapter.cleanup(exclude_paths=active_managed_paths)
                    if deleted:
                        logger.info(f"  🧹 Cleaned up {len(deleted)} stale files/dirs for {name}")
                except Exception as e:
                    logger.error(f"Failed cleanup for disabled adapter {name}: {e}")
                continue

        # Gate on dispatch target group (Task 7)
        adapter_group = _ADAPTER_TO_GROUP.get(getattr(adapter, 'adapter_name', ''))
        if adapter_group and enabled_groups is not None and adapter_group not in enabled_groups:
            logger.info(f"⏭️  Skipping adapter {name} (group '{adapter_group}' disabled)")
            try:
                deleted = adapter.cleanup(exclude_paths=active_managed_paths)
                if deleted:
                    logger.info(f"  🧹 Cleaned up {len(deleted)} stale files/dirs for {name}")
            except Exception as e:
                logger.error(f"Failed cleanup for disabled group adapter {name}: {e}")
            continue

        enabled_sync_adapters.append(adapter)

        if do_rules:
            try:
                adapter.sync_rules(rules_content)
            except Exception as e:
                logger.error(f"Failed rules sync for {name}: {e}")

        if do_mcp_config:
            try:
                adapter.generate_mcp_config()
            except Exception as e:
                logger.error(f"Failed MCP config generation for {name}: {e}")

        if do_subagents:
            try:
                adapter.sync_subagents()
            except Exception as e:
                logger.error(f"Failed subagent sync for {name}: {e}")

        if do_memory:
            try:
                adapter.sync_memory()
            except Exception as e:
                logger.error(f"Failed memory sync for {name}: {e}")

    # 4b. ADR-605 Phase 3: Distribute vendored external skill bundles.
    try:
        from .external_skills import load_external_bundles
        external_bundles = load_external_bundles()
    except Exception as e:
        logger.error(f"Failed to load external skill bundles: {e}")
        external_bundles = []

    if external_bundles:
        for adapter in enabled_sync_adapters:
            try:
                adapter.distribute_external_skills(external_bundles)
            except Exception as e:
                logger.error(
                    f"Failed external-skill distribution for {adapter.__class__.__name__}: {e}"
                )

    # 5. Phase 3: Bidirectional Plugin Sync (ADR-171)
    if effective_plugins:
        logger.info("--- Phase 3: Bidirectional Plugin Sync (ADR-171) ---")
        try:
            # Step 1: Discover installed Claude plugins
            claude_plugins = discover_claude_plugins(CLAUDE_PLUGINS_CACHE)

            # Step 2: Write assembled cache
            if claude_plugins:
                assemble_claude_plugins(claude_plugins, ASSEMBLED_PLUGINS_PATH)

            # Step 3: Resolve overlaps via augur.yaml declarations
            resolved_imports = resolve_overlaps(claude_plugins, PROJECT_ROOT)

            # Step 4: Distribute imported agents to all IDE adapters
            if resolved_imports:
                distribute_imported_agents(resolved_imports, PROJECT_ROOT)
        except Exception as e:
            logger.error(f"Failed Phase 3 (Plugin Sync): {e}")

    # 5b. Skill stub sync — render and write skill files via MCP.
    if do_skill_exports:
        try:
            _sync_skill_stubs(enabled_sync_adapters, cleanup_disabled=selected_clients is None)
        except Exception as e:
            logger.error(f"Failed skill export sync: {e}")

    if do_prompt_exports:
        try:
            _sync_prompt_stubs(enabled_sync_adapters, cleanup_disabled=selected_clients is None)
        except Exception as e:
            logger.error(f"Failed prompt export sync: {e}")

    if do_command_exports:
        try:
            _sync_command_stubs(enabled_sync_adapters, cleanup_disabled=selected_clients is None)
        except Exception as e:
            logger.error(f"Failed command export sync: {e}")

    # 6. Re-stamp unmarked copies, then remove orphans
    try:
        restamped = restamp_unmarked_copies(PROJECT_ROOT)
        if restamped:
            logger.info(f"Re-stamped {len(restamped)} unmarked copies: {restamped}")
    except Exception as e:
        logger.error(f"Failed re-stamp: {e}")
    try:
        orphans = cleanup_orphan_adapted_copies(PROJECT_ROOT)
        if orphans:
            logger.info(f"Removed {len(orphans)} orphan adapted copies: {orphans}")
    except Exception as e:
        logger.error(f"Failed orphan cleanup: {e}")

    # 6b. Repo-root llms.txt / llms-full.txt (ADR-746). Client-neutral peer of
    # the per-client constitution files generated above.
    if do_rules:
        try:
            from .llms_txt import generate_llms_files

            llms_concise, llms_full = generate_llms_files(PROJECT_ROOT)
            for path in (llms_concise, llms_full):
                if path.exists() and path not in GENERATED_FILES:
                    GENERATED_FILES.append(path)
        except Exception as e:
            logger.error(f"Failed llms.txt generation: {e}")

    # 6c. Full per-tool capability surface map (docs/generated). The client
    # instruction files carry only the policy + a pointer to this doc, so it must
    # be regenerated here whenever the rules projections are rebuilt.
    if do_rules:
        try:
            from .templates import (
                CAPABILITY_EXPOSURE_REF,
                build_capability_exposure_doc,
            )

            capability_doc = build_capability_exposure_doc()
            if capability_doc is not None:
                cap_path = PROJECT_ROOT / CAPABILITY_EXPOSURE_REF
                cap_path.parent.mkdir(parents=True, exist_ok=True)
                cap_path.write_text(capability_doc, encoding="utf-8")
                if cap_path not in GENERATED_FILES:
                    GENERATED_FILES.append(cap_path)
        except Exception as e:
            logger.error(f"Failed capability-exposure.md generation: {e}")

    brain_ids = _ensure_brain_mounts()
    if brain_ids:
        logger.info("Ensured root BRAIN.yaml for brains: %s", ", ".join(brain_ids))

    logger.info(f"Sync Complete ({len(GENERATED_FILES)} files generated)")

    # 7. Generate Antigravity manifest only when this run could have changed it.
    if (do_rules or do_subagents or do_memory or do_plugins or do_mcp_config) and (
        selected_clients is None or "antigravity" in selected_clients
    ):
        generate_ide_manifest()

    return 0
