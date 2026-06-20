"""sync_agents/adapters/gemini.py — Gemini CLI adapter."""
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

import string
from pathlib import Path

import yaml

from src.cli_config.manifest import ServerEntry
from src.cli_config.manifest import load_manifest

from .base import BaseAdapter
from ..constants import (
    PROJECT_ROOT,
    SOURCE_RULES_LABEL,
    SOURCE_TOPICS_LABEL,
    GENERATED_FILES,
    logger,
)
from ..engine import write_generated_file
from ..templates import render_rules_projection


def _agent_source_label(master) -> str:
    """Return a truthful source label for generated Gemini agent headers."""
    if master.client_dir.startswith("plugin:"):
        return f"{master.client_dir}/agents/{master.name}.md"

    source_dirs = {
        "claude-code": ".claude/agents",
        "codex": ".codex/agents",
        "cursor": ".cursor/agents",
        "copilot": ".github/agents",
        "opencode": ".opencode/agents",
        "antigravity": ".subagents",
    }
    source_dir = source_dirs.get(master.client_dir, master.client_dir)
    return f"{source_dir}/{master.name}.md"


def _adapt_body_for_gemini(master) -> str:
    """Translate Claude-oriented agent instructions into Gemini CLI terms."""
    body = master.body

    if "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" in body and master.client_dir.startswith("plugin:"):
        plugin_root = master.path.parent.parent
        companion_script = plugin_root / "scripts" / "codex-companion.mjs"
        body = body.replace(
            '"${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs"',
            f'"{companion_script}"',
        )
        body = body.replace(
            "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs",
            str(companion_script),
        )

    replacements = (
        ("CLAUDE.md", "AGENTS.md"),
        ("main Claude Code thread", "main Gemini thread"),
        ("main Claude thread", "main Gemini thread"),
        ("`Bash` call", "`run_shell_command` call"),
        ("Bash call", "run_shell_command call"),
        ("`Bash`", "`run_shell_command`"),
    )
    for old, new in replacements:
        body = body.replace(old, new)

    return body


def _expand_manifest_value(value: str) -> str:
    return string.Template(value).safe_substitute({"AUGUR_ROOT": str(PROJECT_ROOT)})


def _python_command() -> str:
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python3"
    return str(venv_python) if venv_python.exists() else "python3"


def _render_manifest_entry(entry: ServerEntry, client: str) -> dict:
    args = [_expand_manifest_value(arg) for arg in entry.args]
    args.extend(_expand_manifest_value(arg) for arg in entry.per_client_args.get(client, []))

    command = _expand_manifest_value(entry.command)
    if command == "python":
        command = _python_command()

    rendered = {
        "command": command,
        "args": args,
    }
    if entry.cwd_required:
        rendered["cwd"] = str(PROJECT_ROOT)
    if entry.env:
        rendered["env"] = {
            key: _expand_manifest_value(value)
            for key, value in entry.env.items()
        }
    return rendered


def _load_manifest_mcp_config(
    *,
    existing_server_ids: set[str] | None = None,
) -> dict[str, dict]:
    manifest = load_manifest(PROJECT_ROOT / "config" / "system" / "mcp_servers.yaml")
    return {
        entry.id: _render_manifest_entry(entry, client="gemini")
        for entry in manifest.all_augur_servers_for_client(
            "gemini",
            existing_server_ids=existing_server_ids,
            include_project_scoped=True,
        )
        if not entry.bundle
    }


class GeminiAdapter(BaseAdapter):
    adapter_name = "gemini"

    def sync_memory(self) -> None:
        """Project canonical memory to Gemini's repo-local memory dir."""
        from ..constants import PROJECT_ROOT, logger
        memory_dir = PROJECT_ROOT / ".antigravity" / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        memory_content = self.get_projected_memory_content()
        if memory_content:
            (memory_dir / "augur-memory.md").write_text(memory_content, encoding="utf-8")
        logger.info("✅ Antigravity memory dir ready at %s", memory_dir)

    def get_state_files(self) -> list[str]:
        home = str(Path.home())
        return [
            f"{home}/.antigravity/history/",
            f"{home}/.antigravity/sessions/",
            f"{home}/.antigravity/cache/",
        ]

    def get_managed_files(self) -> list[str]:
        return [
            ".antigravity/ANTIGRAVITY.md",
            ".antigravity/plugins/",
            ".antigravity/config.yaml",
            ".antigravity/unignore",
            ".antigravity/workflows/",
            ".antigravity/topics/",
            ".antigravity/memory/",
            ".antigravity/agents/",
        ]

    def distribute_external_skills(self, bundles: list) -> None:
        """Convert external skills into ``.antigravity/plugins/<name>/`` (ADR-605).

        ``.antigravity/plugins/`` is gitignored — outputs stay local-only and are
        rebuilt on every sync.
        """
        from ..external_skills import _distribute_for_gemini
        _distribute_for_gemini(
            bundles,
            target_root=PROJECT_ROOT / ".antigravity" / "plugins",
        )

    def sync_subagents(self) -> None:
        """Generate Gemini subagent profiles from master agents (ADR-464)."""
        from ..agent_parser import scan_agent_dirs, collect_masters, scan_plugin_agents, ADAPTED_COPY_COMMENT
        from ..model_mapping import resolve_model

        agents = scan_agent_dirs(PROJECT_ROOT) + scan_plugin_agents()
        masters = collect_masters(agents)
        if not masters:
            return

        agents_dir = PROJECT_ROOT / ".antigravity" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        generated_names: set[str] = set()
        for name, master in sorted(masters.items()):
            if master.master_client == "gemini":
                continue  # Skip — this is already the Gemini master

            gemini_model = resolve_model(master.master_client, "gemini", master.model)
            description = master.description or f"{name} agent"

            # Build tools list — map Claude Code tool names to Gemini equivalents
            tool_map = {
                "Read": "read_file",
                "Glob": "glob",
                "Grep": "grep_search",
                "Edit": "replace",
                "Write": "write_file",
                "Bash": "run_shell_command",
            }
            gemini_tools: list[str] = []
            for tool in (master.tools or []):
                if tool in tool_map:
                    gemini_tools.append(tool_map[tool])
            if master.mcp_servers:
                gemini_tools.append("mcp_augur_*")

            # Build frontmatter
            fm: dict[str, object] = {
                "name": name,
                "description": description,
                "kind": "local",
                "model": gemini_model,
                "max_turns": 30,
            }
            if gemini_tools:
                fm["tools"] = gemini_tools

            fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip()

            # Build body — preserve instructions, apply mode translation
            body = _adapt_body_for_gemini(master)
            if master.mode == "plan" and "MUST NOT modify files" not in body:
                body = "You MUST NOT modify files. Only analyze, recommend, and report.\n\n" + body

            marker = ADAPTED_COPY_COMMENT.format(master_client=master.master_client)
            content = f"---\n{fm_str}\n---\n{marker}\n\n{body}"

            target = agents_dir / f"{name}.md"
            write_generated_file(target, content, source=_agent_source_label(master))
            generated_names.add(name)
            logger.info(f"  → Antigravity agent: {name} (model={gemini_model})")

        self._cleanup_orphan_agents(agents_dir, generated_names)

    def sync_topic_docs(self, content: str | None = None) -> None:
        """Sync topic docs to both docs/agent-topics/ and .antigravity/topics/ (ADR-096)."""
        # 1. Standard global sync
        super().sync_topic_docs(content)

        # 2. Gemini-specific local sync for RAG/context
        self._sync_agent_topics(
            PROJECT_ROOT / ".antigravity" / "topics",
            SOURCE_TOPICS_LABEL
        )

    def detect_installed(self) -> bool:
        import shutil
        return shutil.which("gemini") is not None or (Path.home() / ".antigravity").is_dir()

    def sync_rules(self, content: str) -> None:
        resolved = render_rules_projection(content)
        write_generated_file(
            PROJECT_ROOT / ".antigravity" / "ANTIGRAVITY.md",
            resolved,
            source=SOURCE_RULES_LABEL,
        )

    def generate_mcp_config(self) -> None:
        """Generate resolved MCP config for Gemini CLI (.antigravity/config.yaml)."""
        try:
            target = PROJECT_ROOT / ".antigravity" / "config.yaml"
            existing_config = {}
            if target.exists():
                try:
                    existing_config = yaml.safe_load(target.read_text(encoding="utf-8"))
                except (OSError, ValueError, TypeError):
                    existing_config = {}
            existing_mcp = (
                existing_config.get("mcpServers")
                if isinstance(existing_config, dict)
                else {}
            )
            existing_server_ids = (
                {
                    str(server_id)
                    for server_id in existing_mcp
                    if str(server_id).startswith("augur")
                }
                if isinstance(existing_mcp, dict)
                else set()
            )
            config = {
                "mcpServers": _load_manifest_mcp_config(
                    existing_server_ids=existing_server_ids,
                )
            }

            # Ensure Gemini CLI does not load the global augur extension locally
            config.setdefault("extensions", {})
            config["extensions"]["augur"] = False

            # Ensure Gemini CLI can discover generated runtime files despite .gitignore.
            config.setdefault("context", {})
            config["context"].setdefault("fileFiltering", {})
            config["context"]["fileFiltering"]["customIgnoreFilePaths"] = [".antigravity/unignore"]

            target.parent.mkdir(parents=True, exist_ok=True)

            # Don't use write_generated_file (no need for AUTO-GENERATED header on JSON)
            target.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False), encoding="utf-8")
            GENERATED_FILES.append(target)
            logger.info(f"✅ Generated {target.relative_to(PROJECT_ROOT)} (MCP config)")

            # Generate .antigravity/unignore so Gemini can read local generated files.
            unignore_path = PROJECT_ROOT / ".antigravity" / "unignore"
            unignore_path.write_text(
                "!/.antigravity/config.yaml\n"
                "!/.antigravity/unignore\n"
                "!/.antigravity/plugins/\n"
                "!/.antigravity/plugins/**\n",
                encoding="utf-8",
            )
            GENERATED_FILES.append(unignore_path)
            logger.info(f"✅ Generated {unignore_path.relative_to(PROJECT_ROOT)} (unignore rules)")
        except Exception as e:
            logger.error(f"Failed to generate MCP config for Gemini CLI: {e}")
