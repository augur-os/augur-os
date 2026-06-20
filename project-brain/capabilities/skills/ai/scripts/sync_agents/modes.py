"""
sync_agents/modes.py

CLI mode implementations for the sync_agents package.

Contains:
    - check_mode(): Check if generated files match what would be generated.
    - validate_mode(): Validate skill directory structure (ADR-252).
    - fix_mode(): Auto-fix mode for pre-commit hooks (ADR-177).
    - clean_mode(): Remove sync-managed generated artifacts.
    - clean_hygiene_mode(): Remove repo-local integration scaffolding clutter.
    - command_surfaces_mode(): Report duplicate Augur command surfaces.
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
import os
import re
import subprocess
from pathlib import Path

from src.config.paths import get_project_brain_skills_dir

from .adapters.cowork import _find_cowork_plugin_dirs
from .command_surface import (
    find_duplicate_commands,
    format_duplicate_report,
    inventory_augur_command_surfaces,
)
from .constants import (
    PROJECT_ROOT,
    SOURCE_RULES,
    SOURCE_WORKFLOWS,
    SOURCE_RULES_LABEL,
    HEADER_TEMPLATE,
    GENERATED_FILES,
    CLAUDE_PLUGINS_CACHE,
    ASSEMBLED_PLUGINS_PATH,
    logger,
)
from .generators import generate_ide_manifest
from .templates import render_rules_projection
from .discovery import (
    discover_claude_plugins,
    assemble_claude_plugins,
    resolve_overlaps,
    distribute_imported_agents,
)

_HYGIENE_REMOVABLE_PATHS: tuple[str, ...] = (
    ".agent/",
    ".claude/launch.json",
    ".claude/settings.json.example",
    ".claude/plans/",
    ".claude/projects/",
    ".codex/INSTALL.md",
    ".antigravity/INSTALL.md",
    ".opencode/INSTALL.md",
    ".cowork/INSTALL.md",
    ".claude-plugin/",
    ".cursor-plugin/",
    ".agents/plugins/marketplace.json",
    ".playwright-mcp/",
)

_STATE_PURGE_CLIENT_ALIASES: dict[str, tuple[str, ...]] = {
    "claude": ("claude_code", "claude_desktop"),
}


def _strip_gemini_memory_import_section(content: str) -> str:
    return re.sub(r"\n## Augur Memories\n.*?(?=\n## |\Z)", "", content, flags=re.DOTALL)


def _rules_content_matches_target(target: Path, current: str, expected: str) -> bool:
    if target.name == "ANTIGRAVITY.md" and target.parent.name == ".antigravity":
        current = _strip_gemini_memory_import_section(current)
    return current == expected


def _remove_file_and_empty_parents(path: Path, stop_at: Path) -> bool:
    """Remove a file plus any newly-empty parents up to ``stop_at``."""
    if not path.exists():
        return False

    path.unlink()

    current = path.parent
    stop = stop_at.resolve()
    while current.exists():
        try:
            current_resolved = current.resolve()
        except OSError:
            break
        if current_resolved == stop:
            break
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent

    return True


def _remove_path_and_empty_parents(path: Path, stop_at: Path) -> bool:
    """Remove a file or directory plus any newly-empty parents up to ``stop_at``."""
    if not path.exists():
        return False

    if path.is_dir():
        import shutil

        for item in path.rglob("*"):
            if item.is_file() and not os.access(item, os.W_OK):
                item.chmod(0o666)
        shutil.rmtree(path)
    else:
        if not os.access(path, os.W_OK):
            path.chmod(0o666)
        path.unlink()

    current = path.parent
    stop = stop_at.resolve()
    while current.exists():
        try:
            current_resolved = current.resolve()
        except OSError:
            break
        if current_resolved == stop:
            break
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent

    return True


def check_mode() -> int:
    """
    Check if generated files match what would be generated.

    Returns:
        0 if all files match, 1 if any would change
    """
    from .adapters.codex import (
        CodexAdapter,
        codex_runtime_config_issues,
        should_check_global_codex_runtime_config,
    )
    from .engine import _load_ide_integrations, _get_enabled_rule_targets, _load_enabled_groups

    logger.info("🔍 Running in check mode...")

    if not SOURCE_RULES.exists():
        logger.error(f"❌ Missing source rules: {SOURCE_RULES}")
        return 1

    try:
        rules_content = SOURCE_RULES.read_text(encoding="utf-8")
    except OSError as e:
        logger.error(f"❌ Failed to read source rules: {e}")
        return 1

    expected_rules = HEADER_TEMPLATE.format(
        source=SOURCE_RULES_LABEL
    ) + render_rules_projection(rules_content)

    ide_config = _load_ide_integrations()
    enabled_groups = _load_enabled_groups()
    key_rule_targets = _get_enabled_rule_targets(ide_config, enabled_groups)

    has_errors = False
    for target in key_rule_targets:
        try:
            display = target.relative_to(PROJECT_ROOT)
        except ValueError:
            display = target

        if not target.exists():
            logger.error(f"❌ Missing generated file: {display}")
            has_errors = True
            continue

        try:
            current = target.read_text(encoding="utf-8")
        except OSError as e:
            logger.error(f"❌ Failed to read generated file {display}: {e}")
            has_errors = True
            continue

        if not _rules_content_matches_target(target, current, expected_rules):
            logger.error(
                "❌ Stale generated file: %s "
                "(run `PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync all`)",
                display,
            )
            has_errors = True

    if should_check_global_codex_runtime_config():
        codex_adapter = CodexAdapter()
        if codex_adapter.detect_installed():
            for issue in codex_runtime_config_issues():
                logger.error(
                    "❌ Stale Codex runtime config: %s "
                    "(run `PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync all codex`)",
                    issue,
                )
                has_errors = True

    from .engine import _get_all_adapters, _is_adapter_enabled
    from .skill_sync import detect_command_stub_drift, detect_skill_stub_drift

    all_adapters = _get_all_adapters()
    enabled_adapters = [
        adapter
        for adapter in all_adapters
        if not getattr(adapter, "adapter_name", "")
        or _is_adapter_enabled(adapter.adapter_name, ide_config)
    ]
    for drift_msg in detect_command_stub_drift(enabled_adapters):
        logger.error(
            "❌ Command stub drift: %s "
            "(run `PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync commands`)",
            drift_msg,
        )
        has_errors = True
    for drift_msg in detect_skill_stub_drift(enabled_adapters):
        logger.error(
            "❌ Skill stub drift: %s "
            "(run `PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync skills`)",
            drift_msg,
        )
        has_errors = True

    # ADR-746: repo-root llms.txt / llms-full.txt drift detection.
    try:
        from .llms_txt import llms_files_drift

        for stale in llms_files_drift(PROJECT_ROOT):
            try:
                display = stale.relative_to(PROJECT_ROOT)
            except ValueError:
                display = stale
            logger.error(
                "❌ Stale generated file: %s "
                "(run `PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync agents`)",
                display,
            )
            has_errors = True
    except Exception as e:
        logger.error(f"❌ Failed llms.txt drift check: {e}")
        has_errors = True

    if has_errors:
        return 1

    logger.info("✅ Generated agent files are up to date")
    return 0


def validate_mode() -> int:
    """Validate skill directory structure (ADR-252).

    Returns:
        0 if all skills valid, 1 if errors found.
    """
    logger.info("🔍 Validating skill structure (ADR-252)...")
    # ADR-252: Skills are now validated via SKILL.md frontmatter discovery
    # rather than augur.yaml command parity checks.
    try:
        from src.plugins.command_discovery import discover_commands
        cmds = discover_commands()
        if not cmds:
            logger.warning("No commands discovered from SKILL.md frontmatter")
        else:
            logger.info(f"Discovered {len(cmds)} commands from SKILL.md frontmatter")
    except Exception as e:
        logger.error(f"Failed to discover commands: {e}")
        return 1

    logger.info("✅ Skill structure is valid")
    return 0


def clean_mode() -> int:
    """Remove sync-managed generated files without touching repository sources."""
    from .engine import _cleanup_legacy_unsupported_exports, _get_all_adapters
    from .llms_txt import llms_txt_paths

    logger.info("🧹 Running in clean mode...")

    removed = 0

    for manifest in (PROJECT_ROOT / ".antigravity" / "ide-manifest.json",):
        if _remove_file_and_empty_parents(manifest, PROJECT_ROOT):
            logger.info("🧹 Removed sync manifest: %s", manifest.relative_to(PROJECT_ROOT))
            removed += 1

    # ADR-746: llms.txt and llms-full.txt are managed generated artifacts.
    for llms_path in llms_txt_paths(PROJECT_ROOT):
        if _remove_file_and_empty_parents(llms_path, PROJECT_ROOT):
            logger.info("🧹 Removed sync artifact: %s", llms_path.relative_to(PROJECT_ROOT))
            removed += 1

    removed += len(_cleanup_legacy_unsupported_exports())

    for adapter in _get_all_adapters():
        try:
            deleted = adapter.cleanup()
        except Exception as e:
            logger.error("Failed cleanup for %s: %s", adapter.__class__.__name__, e)
            continue
        if deleted:
            removed += len(deleted)
            logger.info(
                "🧹 Cleaned %s (%d managed artifacts)",
                adapter.__class__.__name__,
                len(deleted),
            )

    logger.info("✅ Cleanup complete (%d managed artifacts removed)", removed)
    return 0


def purge_mode(dry_run: bool = True) -> int:
    """Remove all Augur-written files from all clients."""
    from .engine import _get_all_adapters
    from .llms_txt import llms_txt_paths

    label = "DRY RUN" if dry_run else "EXECUTING"
    separator = "─" * 52

    if dry_run:
        print(f"\nAUGUR PURGE — {label} (pass --confirm to execute)\n")
    else:
        print(f"\nAUGUR PURGE — {label}\n")

    total_files = 0
    total_dirs = 0
    total_edits = 0
    clients_with_output = 0

    # ADR-746: report the repo-root llms.txt / llms-full.txt under a synthetic
    # "augur-llms" client so the purge dry-run mentions them and --confirm
    # removes them along with everything else.
    llms_present = [p for p in llms_txt_paths(PROJECT_ROOT) if p.exists()]
    if llms_present:
        clients_with_output += 1
        print("augur-llms")
        for path in llms_present:
            try:
                rel = path.relative_to(PROJECT_ROOT).as_posix()
            except ValueError:
                rel = str(path)
            print(f"  local   DELETE  {rel}")
            total_files += 1
            if not dry_run:
                try:
                    path.unlink()
                except OSError as e:
                    logger.warning("Failed to remove %s: %s", path, e)
        print()

    for adapter in _get_all_adapters():
        try:
            reported = adapter.cleanup(dry_run=dry_run)
        except Exception as e:
            logger.error("Failed purge for %s: %s", adapter.__class__.__name__, e)
            continue

        if not reported:
            continue

        clients_with_output += 1
        print(f"{adapter.adapter_name}")

        for path_str in reported:
            path = Path(path_str)
            is_global = path.is_absolute()
            scope = "global" if is_global else "local "

            _is_edit = (
                "opencode.json" in path_str
                or "installed_plugins.json" in path_str
                or "known_marketplaces.json" in path_str
                or "claude_desktop_config.json" in path_str
                or (is_global and path_str.endswith("config.toml"))
            )
            if path_str.endswith("/"):
                total_dirs += 1
            elif _is_edit:
                total_edits += 1
            else:
                total_files += 1

            action = "EDIT  " if _is_edit else "DELETE"
            print(f"  {scope}  {action}  {path_str}")

        print()

    print(separator)
    parts = []
    if total_files:
        parts.append(f"{total_files} files")
    if total_dirs:
        parts.append(f"{total_dirs} dirs")
    if total_edits:
        parts.append(f"{total_edits} edits")
    parts.append(f"{clients_with_output} clients")
    print(f"TOTAL  {' · '.join(parts)}")

    if dry_run:
        print("Run with --confirm to execute.")
    else:
        print("\n✅ PURGE COMPLETE")

    return 0


def purge_state_mode(selected_clients: set[str] | None = None, dry_run: bool = True) -> int:
    """Remove adapter state files from selected clients."""
    from .engine import _get_all_adapters

    selected_adapter_names: set[str] | None = None
    if selected_clients is not None:
        selected_adapter_names = set()
        for client_name in selected_clients:
            selected_adapter_names.update(_STATE_PURGE_CLIENT_ALIASES.get(client_name, (client_name,)))

    label = "DRY RUN" if dry_run else "EXECUTING"
    separator = "─" * 52

    print(f"\nAUGUR STATE PURGE — {label}\n")

    total_files = 0
    total_dirs = 0
    total_edits = 0
    clients_with_output = 0

    for adapter in _get_all_adapters():
        adapter_name = getattr(adapter, "adapter_name", "") or adapter.__class__.__name__
        if selected_adapter_names is not None and adapter_name not in selected_adapter_names:
            continue

        try:
            reported = adapter.cleanup_state(dry_run=dry_run)
        except Exception as e:
            logger.error("Failed state purge for %s: %s", adapter.__class__.__name__, e)
            continue

        if not reported:
            continue

        clients_with_output += 1
        print(f"{adapter_name}")

        for path_str in reported:
            path = Path(path_str)
            is_global = path.is_absolute()
            scope = "global" if is_global else "local "

            _is_edit = (
                "opencode.json" in path_str
                or "installed_plugins.json" in path_str
                or "known_marketplaces.json" in path_str
                or "claude_desktop_config.json" in path_str
                or (is_global and path_str.endswith("config.toml"))
            )
            if path_str.endswith("/"):
                total_dirs += 1
            elif _is_edit:
                total_edits += 1
            else:
                total_files += 1

            action = "EDIT  " if _is_edit else "DELETE"
            print(f"  {scope}  {action}  {path_str}")

        print()

    print(separator)
    parts = []
    if total_files:
        parts.append(f"{total_files} files")
    if total_dirs:
        parts.append(f"{total_dirs} dirs")
    if total_edits:
        parts.append(f"{total_edits} edits")
    parts.append(f"{clients_with_output} clients")
    print(f"TOTAL  {' · '.join(parts)}")

    if dry_run:
        print("Run with --confirm to execute.")
    else:
        print("\n✅ STATE PURGE COMPLETE")

    return 0


def clean_hygiene_mode() -> int:
    """Remove repo-local install scaffolding and runtime clutter outside sync ownership."""
    logger.info("🧽 Running hygiene cleanup mode...")

    removed = 0
    for relative_path in _HYGIENE_REMOVABLE_PATHS:
        target = PROJECT_ROOT / relative_path
        if _remove_path_and_empty_parents(target, PROJECT_ROOT):
            logger.info("🧽 Removed hygiene artifact: %s", relative_path)
            removed += 1

    logger.info("✅ Hygiene cleanup complete (%d artifacts removed)", removed)
    return 0


def _active_command_surfaces_root() -> Path:
    """Resolve the checkout root command-surfaces should inspect."""
    if os.environ.get("AUGUR_SYNC_PROJECT_ROOT"):
        return PROJECT_ROOT

    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (
            (candidate / "pyproject.toml").exists()
            and get_project_brain_skills_dir(candidate).exists()
        ):
            return candidate
    return PROJECT_ROOT


def command_surfaces_mode() -> int:
    """Print duplicate Augur command surfaces and return nonzero when any exist."""
    cowork_plugin_dirs = _find_cowork_plugin_dirs()
    project_root = _active_command_surfaces_root()
    entries = inventory_augur_command_surfaces(
        project_root,
        cowork_plugin_dirs=cowork_plugin_dirs,
    )
    duplicates = find_duplicate_commands(entries)
    print(format_duplicate_report(duplicates))
    return 1 if duplicates else 0


def fix_mode() -> int:
    """
    Auto-fix mode for pre-commit hooks (ADR-177).

    Runs the same checks as ``check`` mode. If any drift is detected,
    automatically regenerates all files (same as ``sync all``) and stages
    the generated targets via git add. Exits 0 so pre-commit passes.

    Returns:
        0 always (auto-fixes or no-op)
    """
    from .engine import (
        _get_all_adapters,
        _cleanup_legacy_unsupported_exports,
        _load_ide_integrations,
        _load_enabled_groups,
        _is_adapter_enabled,
        _get_active_managed_paths,
        _get_enabled_rule_targets,
        _sync_skill_stubs,
        _sync_command_stubs,
    )

    logger.info("🔧 Running in fix mode (ADR-177)...")

    # Run the check logic first
    check_result = check_mode()

    if check_result == 0:
        logger.info("✅ No drift detected, nothing to fix")
        return 0

    # Drift detected — run full sync (equivalent to `sync all`)
    logger.info("🔄 Drift detected, regenerating all agent files...")

    # Clear GENERATED_FILES so we track only this run's output
    GENERATED_FILES.clear()

    # Simulate `sync all` by calling main logic inline
    if not SOURCE_RULES.exists():
        logger.error(f"CRITICAL: Rules source not found at {SOURCE_RULES}")
        return 0  # Still exit 0 for pre-commit; check_mode already logged the error

    try:
        rules_content = SOURCE_RULES.read_text(encoding="utf-8")
    except OSError as e:
        logger.error(f"Failed to read rules: {e}")
        return 0

    if not SOURCE_WORKFLOWS.exists():
        logger.debug(
            "Legacy workflows source not found at %s; using distributed command "
            "registry only",
            SOURCE_WORKFLOWS,
        )

    adapters = _get_all_adapters()
    ide_config = _load_ide_integrations()
    enabled_groups = _load_enabled_groups()
    active_managed_paths = _get_active_managed_paths(adapters, ide_config, enabled_groups)

    _cleanup_legacy_unsupported_exports()

    enabled_sync_adapters = []

    for adapter in adapters:
        name = adapter.__class__.__name__
        # Gate on enabled flag (ADR-219)
        if hasattr(adapter, 'adapter_name') and adapter.adapter_name:
            if not _is_adapter_enabled(adapter.adapter_name, ide_config):
                logger.info(f"⏭️  Skipping disabled adapter: {name}")
                # Clean up managed files for disabled adapters (ADR-219)
                try:
                    adapter.cleanup(exclude_paths=active_managed_paths)
                except Exception as e:
                    logger.error(f"Failed cleanup for disabled adapter {name}: {e}")
                continue
        enabled_sync_adapters.append(adapter)
        try:
            adapter.sync_rules(rules_content)
        except Exception as e:
            logger.error(f"Failed rules sync for {name}: {e}")
        try:
            adapter.generate_mcp_config()
        except Exception as e:
            logger.error(f"Failed MCP config generation for {name}: {e}")
        try:
            adapter.sync_subagents()
        except Exception as e:
            logger.error(f"Failed subagent sync for {name}: {e}")
        try:
            adapter.sync_memory()
        except Exception as e:
            logger.error(f"Failed memory sync for {name}: {e}")

    # Plugin sync
    try:
        claude_plugins = discover_claude_plugins(CLAUDE_PLUGINS_CACHE)
        if claude_plugins:
            assemble_claude_plugins(claude_plugins, ASSEMBLED_PLUGINS_PATH)
        resolved_imports = resolve_overlaps(claude_plugins, PROJECT_ROOT)
        if resolved_imports:
            distribute_imported_agents(resolved_imports, PROJECT_ROOT)
    except Exception as e:
        logger.error(f"Failed Phase 3 (Plugin Sync): {e}")

    # Skill stub sync — render and write skill files via MCP.
    try:
        _sync_skill_stubs(enabled_sync_adapters)
    except Exception as e:
        logger.error(f"Failed skill stub sync: {e}")

    # Command stub sync — render and write .claude/commands/*.md and
    # .{codex,gemini}/skills/<name>/SKILL.md from managed command sources.
    try:
        _sync_command_stubs(enabled_sync_adapters)
    except Exception as e:
        logger.error(f"Failed command stub sync: {e}")

    # Repo-root llms.txt / llms-full.txt (ADR-746).
    try:
        from .llms_txt import generate_llms_files

        llms_concise, llms_full = generate_llms_files(PROJECT_ROOT)
        for path in (llms_concise, llms_full):
            if path.exists() and path not in GENERATED_FILES:
                GENERATED_FILES.append(path)
    except Exception as e:
        logger.error(f"Failed llms.txt generation: {e}")

    generate_ide_manifest()

    logger.info(f"Regeneration complete ({len(GENERATED_FILES)} files generated)")

    # Stage the specific generated files that check_mode() validates.
    key_rule_targets = _get_enabled_rule_targets(_load_ide_integrations(), enabled_groups)

    # Collect all files to stage: check_mode targets + any additional generated files
    # Only stage files inside the repo root to avoid git errors for out-of-repo paths
    # (e.g. ~/.config/opencode/opencode.json written by opencode adapter)
    repo_root = PROJECT_ROOT.resolve()
    files_to_stage: list[Path] = []
    seen: set[str] = set()
    for f in key_rule_targets:
        resolved = f.resolve()
        resolved_str = str(resolved)
        if resolved_str not in seen and f.exists() and resolved.is_relative_to(repo_root):
            files_to_stage.append(f)
            seen.add(resolved_str)
    for f in GENERATED_FILES:
        resolved = Path(f).resolve()
        resolved_str = str(resolved)
        if resolved_str not in seen and Path(f).exists() and resolved.is_relative_to(repo_root):
            files_to_stage.append(f)
            seen.add(resolved_str)

    if files_to_stage:
        # Stage each file individually — never git add -A
        stage_paths = [str(f) for f in files_to_stage]
        result = subprocess.run(
            ["git", "add"] + stage_paths,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning(f"git add failed: {result.stderr.strip()}")
        else:
            logger.info(f"Auto-fixed {len(files_to_stage)} stale files")

    return 0
