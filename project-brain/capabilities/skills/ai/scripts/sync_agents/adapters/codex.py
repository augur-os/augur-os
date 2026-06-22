"""sync_agents/adapters/codex.py — Codex adapter."""
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
import json
import os
import re
from pathlib import Path
from typing import Any

from src.cli_config.manifest import ServerEntry, load_manifest
from src.cli_config.codex_runtime import (
    build_codex_mcp_entry,
    _load_toml,
    codex_runtime_config_issues as _codex_runtime_config_issues,
)
from src.config.paths import get_project_brain_skills_dir
from src.config.runtime_identity import (
    GlobalIdentityLock,
    GlobalMutationGuard,
    default_global_identity_lock_path,
    resolve_runtime_identity,
)

from .base import BaseAdapter
from ..constants import (
    PROJECT_ROOT,
    CODEX_HOME,
    SOURCE_RULES_LABEL,
    GENERATED_FILES,
    logger,
)
from ..engine import write_generated_file
from ..model_mapping import get_tier_model, resolve_model
from ..templates import global_mcp_project_root, render_rules_projection


def _codex_app_paths() -> list[Path]:
    """Return standard macOS install locations for the Codex app."""
    home = Path.home()
    system_root = Path(home.anchor or "/")
    return [
        home / "Applications" / "Codex.app",
        system_root / "Applications" / "Codex.app",
    ]


def _should_sync_global_codex_home() -> bool:
    """Return whether this checkout should write shared ~/.codex files."""
    return os.environ.get("AUGUR_SYNC_REPO_LOCAL_ONLY") != "1"


def should_check_global_codex_runtime_config() -> bool:
    """Return whether check mode should validate shared ~/.codex runtime config."""
    return _should_sync_global_codex_home()


def _rewrite_codex_agent_model_labels(
    body: str,
    *,
    master_client: str,
    source_model: str,
) -> str:
    """Rewrite visible master-client model labels to Codex model labels."""
    codex_model = resolve_model(master_client, "codex", source_model)
    if codex_model:
        body = re.sub(
            r"(\*\*Model\*\*:\s*)[^|\n]*?(\s*\|)",
            lambda match: f"{match.group(1)}{codex_model}{match.group(2)}",
            body,
            count=1,
        )

    def replace_tier_model(match: re.Match[str]) -> str:
        tier = match.group("tier").strip()
        mapped_model = get_tier_model(tier, "codex")
        if not mapped_model:
            return match.group(0)
        return f"{match.group(1)}{mapped_model}{match.group(3)}"

    return re.sub(
        r"(-\s+\*\*(?P<tier>[^*]+)\*\*:\s*`)[^`]+(`)",
        replace_tier_model,
        body,
    )


def _codex_args_for_entry(entry: ServerEntry) -> list[str]:
    args = list(entry.args)
    args.extend(entry.per_client_args.get("codex", []))
    return args


def _build_codex_mcp_entry(
    entry: ServerEntry | None = None,
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    """Return a worktree-aware Codex MCP entry."""
    server_args = _codex_args_for_entry(entry) if entry else [
        "-m",
        "augur_core",
        "--client-id",
        "codex",
    ]
    root = project_root or global_mcp_project_root(PROJECT_ROOT)
    return build_codex_mcp_entry(
        server_args,
        configured_root=root,
        startup_timeout_sec=entry.startup_timeout_sec if entry else None,
    )


def _load_manifest_entries(
    *,
    existing_server_ids: set[str] | None = None,
    include_project_scoped: bool = False,
) -> list[ServerEntry]:
    manifest = load_manifest(PROJECT_ROOT / "config" / "system" / "mcp_servers.yaml")
    return manifest.all_augur_servers_for_client(
        "codex",
        existing_server_ids=existing_server_ids,
        include_project_scoped=include_project_scoped,
    )


def _build_codex_mcp_servers(
    *,
    existing_server_ids: set[str] | None = None,
    project_root: Path | None = None,
    include_project_scoped: bool = False,
) -> dict[str, dict[str, object]]:
    root = project_root or global_mcp_project_root(PROJECT_ROOT)
    return {
        entry.id: _build_codex_mcp_entry(entry, project_root=root)
        for entry in _load_manifest_entries(
            existing_server_ids=existing_server_ids,
            include_project_scoped=include_project_scoped,
        )
    }


def codex_runtime_config_issues(config_path: Path | None = None) -> list[str]:
    """Return stale or missing Augur entries in the active Codex runtime config.

    Thin sync_agents wrapper around src.cli_config.codex_runtime.codex_runtime_config_issues
    that fills in PROJECT_ROOT and CODEX_HOME from sync_agents constants. The
    library function is the source of truth; cross-skill consumers (e.g. the
    onboard skill's windows_one_click) import it from src.cli_config directly.
    """
    return _codex_runtime_config_issues(
        config_path,
        project_root=PROJECT_ROOT,
        codex_home=CODEX_HOME,
    )


class CodexAdapter(BaseAdapter):
    adapter_name = "codex"
    _PROMPTS_MANIFEST = ".augur-generated-prompts.json"

    def get_managed_files(self) -> list[str]:
        codex_home = str(CODEX_HOME)
        return [
            "CODEX.md",
            "AGENTS.md",
            ".codex/config.toml",
            ".codex/agents/",
            ".codex/prompts/",
            ".codex/skills/",
            f"{Path.home()}/.agents/skills/augur",
            f"{Path.home()}/.codex/prompts/",
            f"{codex_home}/AGENTS.md",
            f"{codex_home}/instructions.md",
            f"{codex_home}/augur-memory.md",
        ]

    def get_state_files(self) -> list[str]:
        codex_home = str(CODEX_HOME)
        return [
            f"{codex_home}/sessions/",
            f"{codex_home}/history/",
            f"{codex_home}/transcripts/",
            f"{codex_home}/.tmp/",
            f"{codex_home}/.codex-global-state.json",
        ]

    def detect_installed(self) -> bool:
        import shutil
        # Check CLI binary in PATH
        if shutil.which("codex") is not None:
            return True
        # Check macOS app bundle (Codex.app shares configs with CLI)
        if any(app_path.exists() for app_path in _codex_app_paths()):
            return True
        return False

    def sync_rules(self, content: str) -> None:
        resolved = render_rules_projection(content)
        write_generated_file(
            PROJECT_ROOT / "CODEX.md",
            resolved,
            source=SOURCE_RULES_LABEL,
        )
        # Codex surfaces repository-local AGENTS.md in the status header, so keep
        # it aligned with CODEX.md instead of relying only on ~/.codex/AGENTS.md.
        write_generated_file(
            PROJECT_ROOT / "AGENTS.md",
            resolved,
            source=SOURCE_RULES_LABEL,
        )
        if not _should_sync_global_codex_home():
            return
        # Codex CLI uses ~/.codex/AGENTS.md and ~/.codex/instructions.md
        # for global instructions; keep them in sync with agent-rules.
        codex_dir = CODEX_HOME
        codex_dir.mkdir(parents=True, exist_ok=True)
        write_generated_file(
            codex_dir / "AGENTS.md",
            resolved,
            source=SOURCE_RULES_LABEL,
        )
        # Keep global instructions short; project-root CODEX.md/AGENTS.md stays canonical.
        minimal_global_instructions = (
            "# Codex Global Instructions\n\n"
            "Prefer repository-local `CODEX.md` or `AGENTS.md` when present.\n"
            "For Augur MCP/plugin wiring, confirm `~/.codex/config.toml` has `[marketplaces.augur-local]` and `[plugins.\"augur@augur-local\"]`, then inspect `~/.codex/plugins/cache/augur-local/augur/skills-latest/.mcp.json`.\n"
            "Treat this file as a global bootstrap only.\n"
        )
        write_generated_file(
            codex_dir / "instructions.md",
            minimal_global_instructions,
            source=SOURCE_RULES_LABEL,
        )

    def distribute_external_skills(self, bundles: list) -> None:
        """Copy external skill bundles wholesale into ``.codex/skills/`` (ADR-605)."""
        from ..external_skills import _distribute_via_file_copy
        target_root = PROJECT_ROOT / ".codex" / "skills"
        _distribute_via_file_copy(
            bundles,
            adapter_name=self.adapter_name,
            target_root=target_root,
            label="Codex",
        )

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        """Remove managed files and surgically remove the augur MCP entry from config.toml."""
        deleted: list[str] = []
        excluded = {path.resolve() for path in (exclude_paths or set())}

        config_path = CODEX_HOME / "config.toml"
        try:
            config_resolved = config_path.resolve()
        except OSError:
            config_resolved = config_path

        if config_resolved not in excluded and config_path.exists():
            try:
                current = _load_toml(config_path)
                changed = False

                mcp_servers = current.get("mcp_servers")
                if isinstance(mcp_servers, dict):
                    remaining = {
                        k: v for k, v in mcp_servers.items()
                        if not str(k).startswith("augur")
                    }
                    if remaining != mcp_servers:
                        changed = True
                    else:
                        remaining = mcp_servers
                else:
                    remaining = None

                if changed and isinstance(mcp_servers, dict):
                    if remaining:
                        current["mcp_servers"] = remaining
                    else:
                        del current["mcp_servers"]

                marketplaces = current.get("marketplaces")
                if isinstance(marketplaces, dict) and "augur-local" in marketplaces:
                    remaining = {k: v for k, v in marketplaces.items() if k != "augur-local"}
                    if remaining:
                        current["marketplaces"] = remaining
                    else:
                        del current["marketplaces"]
                    changed = True

                plugins = current.get("plugins")
                if isinstance(plugins, dict) and "augur@augur-local" in plugins:
                    remaining = {k: v for k, v in plugins.items() if k != "augur@augur-local"}
                    if remaining:
                        current["plugins"] = remaining
                    else:
                        del current["plugins"]
                    changed = True

                if changed:
                    deleted.append(str(config_path))
                    if not dry_run:
                        config_path.write_text(_toml_dump_simple(current), encoding="utf-8")
                        logger.info(f"Removed augur Codex entries from {config_path}")
            except OSError as e:
                logger.warning(f"Failed to clean {config_path}: {e}")

        base_paths = self.get_managed_files()

        class _Delegate(BaseAdapter):
            def get_managed_files(self_inner) -> list[str]:
                return base_paths

        deleted.extend(_Delegate().cleanup(exclude_paths=exclude_paths, dry_run=dry_run))
        return deleted

    def generate_mcp_config(self) -> None:
        """Ensure ~/.codex/config.toml has the Augur MCP entry and write project config."""
        if _should_sync_global_codex_home():
            identity = resolve_runtime_identity(PROJECT_ROOT)
            authority_root = global_mcp_project_root(PROJECT_ROOT)
            with GlobalIdentityLock(default_global_identity_lock_path()):
                with GlobalMutationGuard(
                    identity,
                    target_root=authority_root,
                    operation="sync_agents:codex-global",
                    allow_delegated=True,
                ):
                    self._write_global_codex_config(authority_root)

            self._sync_routine_automations()
            self._sync_dev_loop_automations()
            self._sync_dream_automations()

        # Local: .codex/config.toml — project-level Codex settings
        self._sync_local_codex_config()

    def _write_global_codex_config(self, authority_root: Path) -> None:
        """Write shared Codex MCP config using the authority checkout root."""
        config_path = CODEX_HOME / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        desired_marketplace = {
            "source": authority_root.expanduser().resolve().as_posix(),
            "source_type": "local",
        }

        current = _load_toml(config_path)
        changed = False

        # Codex expects tui.model_availability_nux to be a u32, but unquoted
        # model names with dots can be parsed as a nested dict. Delete the
        # corrupted entry so Codex regenerates it with the correct scalar type.
        tui = current.get("tui")
        if isinstance(tui, dict) and isinstance(tui.get("model_availability_nux"), dict):
            del tui["model_availability_nux"]
            if not tui:
                del current["tui"]
            changed = True

        mcp_servers = current.get("mcp_servers")
        if not isinstance(mcp_servers, dict):
            mcp_servers = {}
            current["mcp_servers"] = mcp_servers
        desired_servers = _build_codex_mcp_servers(
            existing_server_ids={
                str(server_id)
                for server_id in mcp_servers
                if str(server_id).startswith("augur")
            },
            project_root=authority_root,
            include_project_scoped=True,
        )
        marketplaces = current.get("marketplaces")
        if not isinstance(marketplaces, dict):
            marketplaces = {}
            current["marketplaces"] = marketplaces
        plugins = current.get("plugins")
        if not isinstance(plugins, dict):
            plugins = {}
            current["plugins"] = plugins

        for server_id in list(mcp_servers):
            if str(server_id).startswith("augur") and server_id not in desired_servers:
                del mcp_servers[server_id]
                changed = True

        for server_id, desired_entry in desired_servers.items():
            if mcp_servers.get(server_id) != desired_entry:
                mcp_servers[server_id] = desired_entry
                changed = True

        if marketplaces.get("augur-local") != desired_marketplace:
            marketplaces["augur-local"] = desired_marketplace
            changed = True

        plugin_entry = plugins.get("augur@augur-local")
        if isinstance(plugin_entry, dict):
            if plugin_entry.get("enabled") is not True:
                plugin_entry["enabled"] = True
                changed = True
        else:
            plugins["augur@augur-local"] = {"enabled": True}
            changed = True

        if changed:
            config_path.write_text(_toml_dump_simple(current), encoding="utf-8")
            GENERATED_FILES.append(config_path)
            logger.info("✅ Generated %s (Codex MCP config)", config_path)

    def _sync_dev_loop_automations(self) -> None:
        """Deprecated transition shim for tiered routine schedules."""
        logger.warning(
            "Codex dev-loop automation sync is deprecated; using routine projection"
        )
        self._sync_routine_automations(
            execution_models={"tiered"},
            label="dev-loop",
            prune=False,
        )

    def _sync_dream_automations(self) -> None:
        """Deprecated transition shim for the dream routine schedule."""
        logger.warning("Codex dream automation sync is deprecated; using routine projection")
        self._sync_routine_automations(
            routine_ids={"dream"},
            label="dream",
            prune=False,
        )

    def _sync_routine_automations(
        self,
        *,
        routine_ids: set[str] | None = None,
        execution_models: set[str] | None = None,
        label: str = "routine",
        prune: bool = True,
    ) -> None:
        """Materialize Codex automations from skill-local routine schedules."""
        try:
            self._ensure_routine_orchestrator_importable()
            from routine_orchestrator import registry
            from src.lib.runtime.codex_automations import load_codex_schedule_seed
        except Exception as exc:
            logger.error("Failed to load routine automation registry: %s", exc)
            return

        try:
            routines = registry.list_routines(skills_roots=self._routine_registry_roots())
        except Exception as exc:
            logger.error("Failed to discover routine automation schedules: %s", exc)
            return

        schedules: list[dict[str, Any]] = []
        seen_schedule_ids: set[str] = set()
        for routine in routines:
            if routine_ids is not None and routine.id not in routine_ids:
                continue
            if execution_models is not None and routine.execution not in execution_models:
                continue
            seed_path = Path(routine.skill_root) / "assets" / "seeds" / "routine-schedule.yaml"
            if not seed_path.is_file():
                continue
            try:
                seed_schedules = load_codex_schedule_seed(
                    seed_path,
                    project_root=PROJECT_ROOT,
                )
            except Exception as exc:
                logger.error("Failed to load Codex routine seed %s: %s", seed_path, exc)
                continue
            for schedule in seed_schedules:
                if not self._routine_schedule_matches(routine, schedule):
                    continue
                schedule_id = str(schedule["id"])
                if schedule_id in seen_schedule_ids:
                    continue
                seen_schedule_ids.add(schedule_id)
                schedules.append(schedule)

        self._sync_codex_schedules(schedules, label=label, prune=prune)

    def _routine_registry_roots(self) -> list[Path]:
        """Return skill roots used for routine declaration discovery."""
        roots: list[Path] = []
        try:
            from src.config.paths import get_managed_skill_source_dirs

            roots.extend(Path(root) for root in get_managed_skill_source_dirs())
        except Exception:
            pass

        shared_root = get_project_brain_skills_dir(PROJECT_ROOT)
        roots.append(shared_root)

        unique: list[Path] = []
        seen: set[Path] = set()
        for root in roots:
            try:
                resolved = root.resolve()
            except OSError:
                resolved = root
            if resolved in seen or not root.is_dir():
                continue
            seen.add(resolved)
            unique.append(root)
        return unique

    def _ensure_routine_orchestrator_importable(self) -> None:
        daemon_scripts = Path(__file__).resolve().parents[4] / "daemon" / "scripts"
        if daemon_scripts.is_dir() and str(daemon_scripts) not in _augur_sys.path:
            _augur_sys.path.insert(0, str(daemon_scripts))

    def _routine_schedule_matches(self, routine: Any, schedule: dict[str, Any]) -> bool:
        loop_name = str(getattr(routine, "loop", None) or routine.id)
        schedule_loop = str(schedule.get("loop") or "")
        return not schedule_loop or schedule_loop in {routine.id, loop_name}

    def _sync_codex_seed(self, seed_path, *, label: str, prune: bool = True) -> None:
        """Shared materialization path for any Codex schedule-seed yaml."""
        if not seed_path.is_file():
            logger.debug("Skipping Codex %s automation sync; seed missing: %s",
                         label, seed_path)
            return
        try:
            from src.lib.runtime.codex_automations import load_codex_schedule_seed

            schedules = load_codex_schedule_seed(
                seed_path,
                project_root=PROJECT_ROOT,
            )
        except Exception as exc:
            logger.error("Failed Codex %s automation sync: %s", label, exc)
            return

        self._sync_codex_schedules(schedules, label=label, prune=prune)

    def _sync_codex_schedules(
        self,
        schedules: list[dict[str, Any]],
        *,
        label: str,
        prune: bool = True,
    ) -> None:
        """Materialize a normalized Codex schedule set."""
        if not schedules:
            logger.debug("Skipping Codex %s automation sync; no schedules", label)
            return
        try:
            from src.lib.runtime.codex_automations import sync_codex_automations

            written = sync_codex_automations(
                schedules,
                apply=True,
                home=CODEX_HOME.parent,
                prune=prune,
            )
        except Exception as exc:
            logger.error("Failed Codex %s automation sync: %s", label, exc)
            return

        GENERATED_FILES.extend(written)
        logger.info("✅ Synced %s Codex %s automations", len(written), label)

    def _sync_local_codex_config(self) -> None:
        """Write .codex/config.toml with project-level Codex settings."""
        local_config = PROJECT_ROOT / ".codex" / "config.toml"
        local_config.parent.mkdir(parents=True, exist_ok=True)

        current = _load_toml(local_config)
        desired = {
            "approval_policy": "never",
            "sandbox_mode": "danger-full-access",
        }

        changed = any(current.get(k) != v for k, v in desired.items())
        if not changed and local_config.exists():
            return

        current.update(desired)
        local_config.write_text(_toml_dump_simple(current), encoding="utf-8")
        GENERATED_FILES.append(local_config)
        logger.info("✅ Generated %s (Codex project config)", local_config)

    def _load_generated_prompts(self, manifest_path: Path) -> set[str]:
        if not manifest_path.exists():
            return set()
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = payload.get("files", [])
            if not isinstance(files, list):
                return set()
            return {
                name
                for name in files
                if isinstance(name, str) and Path(name).name == name
            }
        except (OSError, json.JSONDecodeError):
            return set()

    def _save_generated_prompts(self, manifest_path: Path, files: set[str]) -> None:
        payload = {"files": sorted(files)}
        if manifest_path.exists():
            current_mode = manifest_path.stat().st_mode
            if not (current_mode & 0o200):
                manifest_path.chmod(current_mode | 0o200)
        manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        manifest_path.chmod(0o444)
        GENERATED_FILES.append(manifest_path)

    def sync_subagents(self) -> None:
        """Generate Codex subagent profiles from master agents (ADR-464)."""
        from ..agent_parser import (
            ADAPTED_COPY_COMMENT,
            collect_masters,
            scan_agent_dirs,
            scan_plugin_agents,
            scan_project_agents,
        )

        agents = (
            scan_project_agents(PROJECT_ROOT)
            + scan_agent_dirs(PROJECT_ROOT)
            + scan_plugin_agents()
        )
        masters = collect_masters(agents)
        if not masters:
            return

        agents_dir = PROJECT_ROOT / ".codex" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        generated_names: set[str] = set()
        for name, master in sorted(masters.items()):
            if master.master_client == "codex":
                continue

            description = master.description or f"{name} agent"

            body = master.body
            if master.mode == "plan" and "MUST NOT modify files" not in body:
                body = "You MUST NOT modify files. Only analyze, recommend, and report.\n\n" + body
            body = _rewrite_codex_agent_model_labels(
                body,
                master_client=master.master_client,
                source_model=master.model,
            )

            marker = ADAPTED_COPY_COMMENT.format(master_client=master.master_client)
            content = f"---\ndescription: \"{description}\"\n---\n{marker}\n\n{body}"

            target = agents_dir / f"{name}.md"
            try:
                source_ref = str(master.path.relative_to(PROJECT_ROOT))
            except ValueError:
                source_ref = f"{master.client_dir}/{master.name}.md"
            write_generated_file(target, content, source=source_ref)
            generated_names.add(name)
            logger.info(f"  → Codex agent: {name}")

        self._cleanup_orphan_agents(agents_dir, generated_names)

    def sync_memory(self) -> None:
        """Sync canonical memory to ~/.codex/augur-memory.md (ADR-057)."""
        try:
            memory_content = self.get_projected_memory_content()
            if not memory_content:
                return
            target = CODEX_HOME / "augur-memory.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(memory_content, encoding="utf-8")
            logger.info(f"✅ Synced memory to {target}")
        except Exception as e:
            logger.error(f"Failed to sync memory for Codex: {e}")


def _toml_format_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_format_value(item) for item in value) + "]"
    return json.dumps(str(value))


def _toml_format_key(key: str) -> str:
    if re.match(r"^[A-Za-z0-9_-]+$", key):
        return key
    return json.dumps(key)


def _toml_join_key(parts: tuple[str, ...]) -> str:
    return ".".join(_toml_format_key(part) for part in parts)


def _toml_dump_table(prefix: tuple[str, ...], data: dict) -> list[str]:
    lines: list[str] = []
    scalar_items = [(k, v) for k, v in data.items() if not isinstance(v, dict)]
    lines.append(f"[{_toml_join_key(prefix)}]")
    for key, value in sorted(scalar_items, key=lambda item: item[0]):
        lines.append(f"{_toml_format_key(key)} = {_toml_format_value(value)}")
    lines.append("")

    for key, value in sorted(data.items(), key=lambda item: item[0]):
        if isinstance(value, dict):
            lines.extend(_toml_dump_table((*prefix, key), value))

    return lines


def _toml_dump_simple(config: dict) -> str:
    lines: list[str] = []
    scalar_items = [(k, v) for k, v in config.items() if not isinstance(v, dict)]
    for key, value in sorted(scalar_items, key=lambda item: item[0]):
        lines.append(f"{_toml_format_key(key)} = {_toml_format_value(value)}")

    table_items = [(k, v) for k, v in config.items() if isinstance(v, dict)]
    for key, value in sorted(table_items, key=lambda item: item[0]):
        lines.extend(_toml_dump_table((key,), value))

    return "\n".join(lines).rstrip() + "\n"
